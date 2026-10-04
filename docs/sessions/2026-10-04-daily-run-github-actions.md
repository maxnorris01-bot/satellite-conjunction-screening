# Session 2026-10-04: daily run triggered from GitHub Actions (ADR 0012)

Branch: `feat/daily-run-github-actions`. Scope: the 2026-10-04 working-notes entry "Daily run:
Fly's built-in schedule is unreliable; trigger it from GitHub Actions".

## What changed and why

- **`.github/workflows/daily-run.yml` (new).** It triggers on a `schedule` (daily, 10:17 UTC) and
  on `workflow_dispatch`. It installs `flyctl` 0.4.111 and then:
  1. **Cooldown check:** fails before starting anything if `history/index.json` was generated less
     than 2 hours ago, with a message explaining CelesTrak's one-download-per-update limit and the
     time to re-run. That avoids spending a download that would 403.
  2. `flyctl machine start 1850e47cdd43e8`.
  3. `flyctl machine wait --state stopped` for up to 15 minutes (the job timeout is 25).
     **Wrong, fixed in a follow-up below:** each wait request is capped at 60 s client-side and
     `flyctl` doesn't retry the timeout, so this gave up after 60 s on the first real run.
  4. **Exit code** from the Machine's exit event after this run's start (`flyctl machine list
     --json`). Fly omits `exit_code` when it's 0, so a present event without a code counts as
     success. A non-zero exit fails, and if the run's failure line in `fly logs` shows a 403 or
     CelesTrak's "has not updated since your last successful download", the error says it's the
     cooldown.
  5. **Bucket freshness:** fails unless `history/index.json`'s `generated_at_utc` is after this
     run's start. Writes a step summary (run id, exit code, snapshot date, retained dates).

  Other properties:
  - `concurrency: daily-run` stops a dispatch overlapping the scheduled run.
  - `permissions: contents: read`.
  - The only secret is `FLY_API_TOKEN`. `flyctl` reads it from the environment, so it's never in a
    command or log.
- **Why 10:17 UTC.** CelesTrak documents no fixed update times, only a 2-hourly check and one
  download per GROUP per update. So the time is chosen to avoid other downloads (03:17 PDT, when
  manual runs don't happen). It's also far from 00:00 UTC, so GitHub delays can't change the
  snapshot's UTC date, and off the top of the hour, when GitHub delays cron runs most.
- **Retiring Fly's schedule (proposed; not run).** In `flyctl` 0.4.111, `--schedule ""` can't
  clear a schedule: the update path only sets the field when the flag is non-empty (`run.go:771`).
  `--machine-config` is unmarshalled onto the Machine's current config first (`run.go:660`,
  `config.ParseConfig`), so `{"schedule": ""}` empties it in place and keeps the Machine id. That
  command is now `make fly-unschedule`, with `--skip-start`. The fallback (a replacement Machine
  without a schedule) is in ADR 0012.
- **Makefile:** `--schedule daily` is removed from `FLY_MACHINE_FLAGS`. `fly machine update` leaves
  an existing schedule alone when the flag is absent, so routine image updates can't re-schedule
  the Machine. `fly-unschedule` was added.
- **Docs:** ADR 0012 (new); ADR 0009's status now says its trigger is superseded; README's Daily
  run section (now GitHub Actions; token setup, manual dispatch, the cooldown); to-do.

## How I verified (no Fly commands run, per the scope)

- **Workflow lint:** `actionlint` 1.7.12 with `shellcheck` on the PATH reports 0 errors.
- **Exit-code `jq` filter**, tested on synthetic `machine list --json` input:
  - exit event without a code -> `0`
  - exit code 1 -> `1`
  - monitor-event exit 137 -> `137`
  - an exit event from before the run -> `none`
  - another Machine's event -> `none`
- **flyctl behavior** checked against its v0.4.111 source (`internal/command/machine/run.go`,
  `wait.go`, `list.go`, `internal/config/machine.go`) and `fly-go` v0.11.2's `MachineEvent` types.
  Nothing was run against the Fly account.
- `make lint`, `make typecheck` and `make test` (39) are clean. No Python changed.

## Not verified yet (needs Max, in this order, after merge)

1. **Token:** `fly tokens create deploy -a satellite-conjunction-screening`, then `gh secret set
   FLY_API_TOKEN` (paste at the prompt).
2. **Retire Fly's schedule:** `make fly-unschedule FLY_MACHINE_ID=1850e47cdd43e8`, then confirm
   with `fly machine status 1850e47cdd43e8 -d` that `schedule` is gone. If it isn't, use ADR
   0012's fallback.
3. **Manual run:** `gh workflow run daily-run.yml`. It should go green with a fresh snapshot date
   in the step summary and in `history/index.json`. Mind the cooldown: it refuses within 2 hours
   of the last publish.
4. **Deliberate failure:** a throwaway branch with a wrong `FLY_MACHINE_ID`, dispatched with
   `gh workflow run daily-run.yml --ref <branch>` (the workflow must be on `main` first for
   dispatch to find it). It should go red with a clear message. Not on `main`.
5. **Next scheduled run:** it fires at about 10:17 UTC on its own and adds a date to the index.

Two things are unconfirmed until steps 2-3: that `--machine-config '{"schedule": ""}'` clears the
field (inferred from the source), and that `machine list --json` includes `events` for the Machine
(fly-go's type has them; the list endpoint wasn't exercised).

## Eval numbers

Not re-run: no pipeline, prompt or Python code changed.

## Open questions / flag for review

- **The 60-day rule:** GitHub disables scheduled workflows in a public repo after about 60 days
  with no repository activity. That silences the daily run and its failure emails together. The
  only symptom is a stale snapshot date. A manual dispatch or any push re-enables it.
- ~~The `setup-flyctl` action is referenced as `@master`~~. Resolved in the follow-up below.

## Follow-up (2026-10-04, branch `fix/pin-setup-flyctl`): `setup-flyctl` pinned to a commit SHA

`superfly/flyctl-actions/setup-flyctl` is now pinned to
`ed8efb33836e8b2096c7fd3ba1c8afe303ebbff1` instead of `@master`. The `flyctl` binary is still
pinned to 0.4.111.

**Looked up from the action's repo, not memory** (`gh release list`, `gh api .../git/ref/tags/1.5`,
`git ls-remote`, `gh api .../compare/1.5...master`):
- The latest release is **v1.5** (tag `1.5`, lightweight, commit
  `fc53c09e1bc3be6f54706524e3b82c4f462f77be`, 2024-02-02). Its `action.yml` declares `using:
  node20`.
- `master` is `ed8efb3`, the 2026-04-08 merge of PR #108 ("upgrade node runtime"). It's 11
  commits past v1.5: the August 2024 "Revamp", plus the March-April 2026 move to `using: node24`.
  None of that is in any release.
- Both versions accept the same `version` input.

**The SHA doesn't correspond to a release, by Max's choice.** Pinning v1.5 would have rolled the
action back two years, onto the Node 20 runtime upstream moved off. Pinning `master`'s current SHA
keeps exactly what the merged workflow already ran, now immutable. The trailing comment says
`master 2026-04-08 (unreleased; after v1.5, node24)`, and a two-line comment above it gives the
reason. If upstream cuts a release that includes this commit, re-pin to that release's SHA and name
it in the comment.

**Checks:** `actionlint` 1.7.12 reports 0 errors. I confirmed the shellcheck rule ran: with
`shellcheck` on the PATH, only the pyflakes rule is disabled. `make lint`, `make typecheck` and
`make test` (39) are clean. No Python changed.

## Follow-up (2026-10-04, branch `fix/daily-run-wait-loop`): replace `flyctl machine wait` with a polling loop

**What failed.** The first real run, GitHub Actions 37242110531, failed in "Wait for it to stop".
Its log: started waiting at 23:00:08Z, and at 23:01:08Z `Error: machine 1850e47cdd43e8 did not
reach "stopped" within 15m0s: ... deadline_exceeded: machine failed to reach desired state,
stopped, currently started`. That's exactly 60 s, with the Machine still running its job.

**Cause, verified in source** (no Fly commands run):
- `fly-go` v0.11.2, which `flyctl` v0.4.111 uses, clamps each Machines API wait request to 60 s:
  `WithWaitTimeout` sets `max(1s, min(timeout, proxyTimeoutThreshold))` with
  `proxyTimeoutThreshold = 60 * time.Second` (`flaps/flaps_machines_wait.go`:19, 38).
- `flyctl machine wait` makes up to 3 attempts, but `isRetryableWaitError` only retries 429, 5xx,
  "currently replaced" and network-error strings. `deadline_exceeded` isn't retried, so the command
  returns after 60 s whatever `--wait-timeout` says.
- Fly's Machines API docs give the wait endpoint's `timeout` a default of 60 s and no stated
  maximum, so the hard cap is client-side.

My earlier claim in this session ("loops until the whole timeout is used") came from reading the
retry loop without checking the retry predicate or the per-request clamp. It was wrong.

**Fix.**
- `.github/scripts/wait-for-machine.sh` (new, executable) polls `flyctl machine list --json` every
  10 s, with an overall deadline of 900 s (`DEADLINE_S`).
  - It returns once the Machine is `stopped` *and* has an exit event timestamped after this run's
    `start_ms`. That guards against reading the previous run's `stopped` state before the start
    takes effect.
  - A failed poll is logged as a warning and retried.
  - At the deadline it fails with `::error title=Machine did not stop::` naming the last state and
    what to check.
- The workflow calls the script for "Wait for it to stop". That needed `actions/checkout`
  (sparse, `.github/scripts` only), placed as the **first** step: checkout cleans the workspace,
  and the first draft put it after the step that writes `start_ms`, which would have deleted it.
- The exit-code and bucket-check steps are unchanged.

**Tests.** `tests/test_daily_run_workflow.py` (6 tests, part of `make test` and CI) runs the real
script, and the real "Check exit code" step read from the workflow YAML, against a fake `flyctl`
serving scripted `machine list --json` responses:
- still running then stopped OK (exit-code step reports 0)
- stopped with exit 1 (wait finishes, exit-code step fails "Run failed")
- exit 1 with a 403 in the logs (reported as the CelesTrak cooldown)
- never stops (fails at the deadline with the message)
- a stale stop from the previous run (keeps waiting, then times out)
- a transient `flyctl` failure (retried)

Removing the stale-stop guard on purpose makes 2 of them fail; restored afterwards.

**Checks.** actionlint reports 0 errors with the shellcheck rule active, and `shellcheck` passes
the script. `make lint`, `make typecheck` and `make test` (45) are clean.

**ADR 0012** is updated: its Decision describes the polling wait, and an amendment records the
failed run and the verified cause.

**Next:** after merge, Max re-runs the workflow (`gh workflow run daily-run.yml`), minding the
2-hour cooldown from the failed run's download.

## Follow-up (2026-10-04, branch `fix/pin-checkout`): pin checkout, drop its credentials, scope the Fly token

**`actions/checkout` pinned to `11d5960a326750d5838078e36cf38b85af677262` (v4.4.0).**
- Looked up from the action's repo: `git ls-remote` shows the floating `v4` tag and `v4.4.0`
  (released 2026-07-20) on that same commit. Both are lightweight tags (`gh api
  .../git/ref/tags/v4.4.0` -> type `commit`), so there's no annotated-tag object to dereference.
- That's exactly what `@v4` ran, now immutable. Trailing comment: `# v4.4.0`.
- v4.4.0 still declares `using: node20`. Newer majors exist (the latest is v7.0.1), but moving
  majors is a separate, deliberate change and wasn't done here.

**`persist-credentials: false` on the checkout.** Nothing later in the job pushes or fetches, so
the job's `GITHUB_TOKEN` no longer stays in `.git/config` for the later steps.

**`FLY_API_TOKEN` moved from job level to the steps that use it.** Before this, it was in the
job's `env`, so every step had it, including the checkout and the third-party `setup-flyctl`
action, neither of which needs it. Only three steps call `flyctl`:
- "Start the Machine"
- "Wait for it to stop" (through `wait-for-machine.sh`)
- "Check exit code" (`machine list` and `logs`)

The cooldown check and the bucket check only `curl` the public bucket, and installing `flyctl`
needs no token. So it now sits in each of those three steps' `env` and nowhere else. Nothing
requires it at job level.

**Checks.**
- actionlint reports 0 errors with the shellcheck rule active.
- Two new tests in `tests/test_daily_run_workflow.py` read the workflow YAML:
  - the token is absent at job level, and present on exactly the steps that call `flyctl`, which
    must be those three;
  - the checkout is pinned to a 40-hex-character SHA with `persist-credentials: false`.
- `make lint`, `make typecheck` and `make test` (47) are clean.

ADR 0012's "Run" bullet now says the token is per-step, the actions are SHA-pinned and the checkout
drops its credentials.
