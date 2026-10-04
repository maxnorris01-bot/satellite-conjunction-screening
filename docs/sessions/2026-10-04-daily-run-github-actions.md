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
- The `setup-flyctl` action is referenced as `@master`, as in Fly's docs, with the `flyctl` binary
  pinned to 0.4.111. Pin the action to a commit SHA if you want the action itself fixed too.
