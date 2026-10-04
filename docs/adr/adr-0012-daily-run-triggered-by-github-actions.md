# ADR 0012: Trigger the daily run from GitHub Actions, not Fly's built-in schedule

**Status:** Accepted, 2026-10-04. Supersedes ADR 0009's trigger choice (`fly machine run
--schedule daily`). ADR 0009's Machine, bucket layout and failure semantics are unchanged.

## Context

**Evidence.** The scheduled Machine (`1850e47cdd43e8`) still has `schedule: daily` (`fly machine
status -d`) and is healthy: its last run exited 0, on the right image. Even so, the scheduler's
only start was 2026-10-03 04:43Z, with nothing since. By 2026-10-04 22:41Z the bucket's
`history/index.json` still listed only 2026-10-03, about 25 hours after the last run, which was a
manual one. Fly's docs describe the built-in schedule as approximate: anchored to the Machine's
creation, and skipped when the host lacks capacity. Fly's task-scheduling guide recommends it only
where "roughly once a day" is good enough.

The tool promises a catalog refreshed daily, and the globe's time slider (ADR 0011) has a gap for
every missed date. We need a trigger we can see, verify and re-run. (Recorded in the working notes,
2026-10-04.)

## Options considered

1. **A GitHub Actions cron that starts the existing Machine.** Free for a public repository, needs
   no new infrastructure, and has a visible run history. A manual re-run is one click
   (`workflow_dispatch`), and a failed run emails the repo owner. GitHub's cron is itself
   best-effort (runs can start late under load), but a late start is visible and verifiable, which
   is the point.
2. **Fly's Cron Manager.** Fly's own answer to this: a separate always-on app that launches
   Machines on a cron. It's another app to run and pay for, around the clock, to do one start a day.
3. **Wait and see** whether Fly's schedule recovers. That leaves the daily promise with no fix and
   no alert.

## Decision

**Option 1 (Max's choice).** `.github/workflows/daily-run.yml`:

- **Triggers:** `schedule` at **10:17 UTC** daily, and `workflow_dispatch`. Why that time:
  - CelesTrak publishes no fixed update times. It checks for new GP data every 2 hours (upstream
    data changes 2-3 times a day) and enforces one download per GROUP per update. A repeat gets
    HTTP 403, and CelesTrak warns that repeated 403s can firewall an IP.
  - So the time can't be keyed to an update. What matters is staying clear of other downloads of
    the same groups. Manual runs happen in US Pacific working hours, and 10:17 UTC (03:17 PDT) is
    the middle of the Pacific night.
  - It's far from 00:00 UTC, so GitHub's scheduling delays can't move a run onto a different UTC
    date (snapshots are keyed by date, ADR 0011).
  - Minute 17 avoids the top of the hour, when GitHub most often delays scheduled runs.
- **Run:** install `flyctl` (pinned to 0.4.111), then `flyctl machine start` on the existing
  Machine, using a `FLY_API_TOKEN` repository secret scoped to this app. `flyctl` reads the token
  from the environment, so it never appears in a command or log. `concurrency: daily-run` stops a
  manual dispatch from overlapping the scheduled run.
- **Verify, don't just fire:**
  1. **Before starting:** read `history/index.json`. If the last publish was under 2 hours ago,
     fail with an explanation of CelesTrak's cooldown and when to re-run, rather than spend a
     doomed download that would 403.
  2. **Wait** for the Machine to stop, for up to 15 minutes (the job's timeout is 25 minutes). A Fly
     run takes about 2 minutes, and the margin covers a slow boot or a repeat of the unexplained
     560 s first run in the working notes. The wait polls `flyctl machine list --json` every 10 s
     (`.github/scripts/wait-for-machine.sh`, amended 2026-10-04; see below). It counts the run as
     finished only when the Machine is `stopped` *and* has an exit event from after this run's
     start, so the previous run's `stopped` state can't end the wait early. A failed poll is
     retried. At the deadline it fails with the Machine's last state and what to check.
  3. **Check the exit code** from the Machine's exit event after this run's start
     (`flyctl machine list --json`). Fly omits `exit_code` when it's 0, so a present exit event
     without a code counts as success, and a missing exit event fails. A non-zero exit fails. If
     the run's failure log line shows a 403 or CelesTrak's "has not updated since your last
     successful download" message, the error says it's the cooldown, not an outage.
  4. **Check the bucket:** `history/index.json`'s `generated_at_utc` must be after this run
     started. Then write a step summary with the run id, exit code, snapshot date and retained
     dates.
- **Retiring Fly's schedule:** both triggers firing would double-run, and the second run would hit
  the 403. `flyctl` 0.4.111 can't clear a schedule with `--schedule ""`; its update path only sets
  the field when the flag is non-empty. But `--machine-config` is unmarshalled onto the Machine's
  current config before flags apply, so `make fly-unschedule` runs:

  ```bash
  fly machine update 1850e47cdd43e8 --machine-config '{"schedule": ""}' --skip-start -a satellite-conjunction-screening --yes
  ```

  That clears it in place and keeps the Machine id. Max runs it, and checks with `fly machine
  status 1850e47cdd43e8 -d` that `schedule` is gone. If it doesn't clear, the fallback is a
  replacement Machine created without `--schedule` (`make fly-machine-create`, which runs once on
  creation, so mind the cooldown). The workflow's and Makefile's `FLY_MACHINE_ID` would then be
  updated, and the old Machine destroyed.
- `--schedule daily` is removed from the Makefile's `FLY_MACHINE_FLAGS`. `fly machine update`
  leaves an existing schedule alone when the flag is absent, so this keeps routine image updates
  from quietly re-scheduling the Machine.

## Consequences

- **A red workflow run is the alert.** No extra monitoring is needed: GitHub emails the repo
  owner when a run fails.
- **GitHub disables scheduled workflows in a public repo after about 60 days with no repository
  activity.** If that happens, the daily run silently stops, and so do the red-run emails. The
  mitigation is partial: the next manual `workflow_dispatch` (or any push) re-enables it, and a
  stale snapshot date in the bucket and on the page is the visible symptom. Worth a calendar
  reminder if the repo goes quiet for two months.
- **GitHub's cron is also best-effort**, but any delay is visible in the run history and leaves
  the UTC date unchanged at this time of day.
- **A manual run inside 2 hours of a scheduled one** makes the scheduled run fail at the cooldown
  check, with a message saying so. Re-run it after the time the message gives.
- **New credential:** one Fly token in the repository secrets, scoped to this app. Max creates and
  stores it. Rotating it means replacing the secret.
- **No pipeline code changes.** `app.publish`, the Machine size and the bucket layout are
  untouched.

## Amendment, 2026-10-04: the wait is a polling loop, not `flyctl machine wait`

The first real run (GitHub Actions run 37242110531) failed in its wait step. `flyctl machine wait
1850e47cdd43e8 --state stopped --wait-timeout 15m` started at 23:00:08Z and gave up at 23:01:08Z,
exactly 60 s later, with `deadline_exceeded: machine failed to reach desired state, stopped,
currently started`. The Machine was still running its job.

**Cause, verified in source** (`flyctl` v0.4.111 and the `fly-go` v0.11.2 it vendors):
- `fly-go`'s `WithWaitTimeout` clamps every Machines API wait request to
  `min(timeout, proxyTimeoutThreshold)`, where `proxyTimeoutThreshold = 60 * time.Second`
  (`flaps/flaps_machines_wait.go`, lines 19 and 38). So `--wait-timeout 15m` becomes one request
  of at most 60 s. The Machines API docs give the wait endpoint's `timeout` a default of 60 s and
  state no higher maximum.
- `flyctl machine wait` (`internal/command/machine/wait.go`) makes up to 3 attempts, but only
  retries errors its `isRetryableWaitError` accepts: HTTP 429, 5xx, "currently replaced" and a
  list of network-error strings. A `deadline_exceeded` with the Machine still `started` isn't one
  of them, so it returns after the first 60 s request.

The original version of this ADR assumed `--wait-timeout` set the overall wait. It doesn't. The
wait is now the polling loop described in the Decision above. The exit-code and bucket checks are
unchanged. `tests/test_daily_run_workflow.py` exercises the loop and the exit-code step against a
fake `flyctl` for these cases: still running then stopped OK, stopped with exit 1, a 403 cooldown,
never stops, a stale stop from the previous run, and a transient `flyctl` failure.
