# ADR 0009: Daily run on a Fly.io scheduled Machine, publishing to a public Tigris bucket, no history

**Status:** Accepted, 2026-10-01. Supersedes ADR 0005's deferral: the measured runtime and memory
it was waiting for are in ADR 0007. **"No history" is superseded by
[ADR 0011](adr-0011-dated-snapshot-retention.md) (2026-10-02):** the job now also keeps 7 days of
dated objects and report snapshots alongside `current.json`.

## Context

ADR 0005 deferred deployment until the pipeline's runtime and memory were measured. ADR 0007 has
those numbers: the default scope takes about 5 s and peaks at 362 MB, and even the 18.5k-object
scale test takes about 140 s and 2.2 GB. Cowork decided on 2026-10-01 (recorded in
`docs/todo.md`) to run daily on Fly.io rather than AWS Lambda + EventBridge. Lambda's scale isn't
needed at this size, and Fly avoids standing up a second cloud account's IAM and
container-registry surface. Cowork also decided there's no retention window: each run overwrites
the current report, and history is deferred with the rest of the visualization vision.

What remained open was how the run gets triggered and where its output lands.

## Options considered

**Trigger:**
1. **A Fly scheduled Machine** (`fly machine run --schedule daily`). It starts, runs the image's
   command and stops, so nothing runs between days. The schedule is "fuzzy": roughly daily, with
   no fixed time.
2. **An always-on Machine running cron.** Exact timing, but it's billed around the clock for about
   5 s of work a day and adds a process supervisor.

**Output:**
1. **A Fly volume.** A volume attaches to one Machine only, so nothing else (the planned API layer,
   `portfolio-site`) could read it.
2. **Tigris object storage**, Fly's integrated S3-compatible store. Any client can read it, it can
   be public, and `fly storage create` wires the credentials in as app secrets.

## Decision

- **A scheduled Machine with `--schedule daily --restart no --vm-memory 1024` in `sjc`.**
  `--restart no` is deliberate: a failed day leaves the previous report in place rather than
  retrying against CelesTrak in a loop. 1 GB is about 3x the measured peak for the default scope.
  The fuzzy schedule is acceptable because every report records its own window.
- **A public Tigris bucket** (Max's call), so `reports/current.json` has a stable public URL that
  `portfolio-site` can fetch today. The data is already public. The planned API layer can read the
  same object later.
- **The raw CelesTrak snapshot is published too** (Max's call): `snapshots/current/*.json.gz` plus
  a `manifest.json` carrying the run id. It's the same format as the regression test's frozen
  snapshot, so any published report can be reproduced exactly or frozen into a test. That was
  verified on a dry run: re-screening from the published snapshot with the report's window start
  reproduced all 510 conjunctions.
- **The entry point is `app.publish`.** It runs the unchanged pipeline with a fresh temp cache,
  then uploads the snapshot, manifest and report, in that order. It uploads nothing if the pipeline
  fails, exits non-zero, and logs one JSON line either way.
- The image is built and pushed with `fly deploy --build-only --push` (no long-running process is
  deployed), and the Machine is pointed at new images with `fly machine update`. Both are wrapped
  as Makefile targets.

## Consequences

- **Cost** is a few seconds of a 1 GB shared-CPU Machine a day, plus under 1 MB of storage
  (report ~0.6 MB, snapshot ~0.2 MB).
- **Uploads aren't transactional.** Each object put is atomic, but if an upload fails partway, the
  snapshot can be newer than the report. Consumers can compare `manifest.json`'s `run_id` with the
  report's.
- **Changing groups leaves stale objects.** If the configured groups change, the old groups'
  snapshot files stay in the bucket. The manifest lists only the current files.
- **No history** means "what changed since yesterday" isn't answerable yet. That's deliberate.
  Adding history later means writing dated keys alongside `current`, not a redesign.
- **The fuzzy schedule.** If a consumer ever needs a fixed time, switch to option 2 above or an
  external trigger.
- **Verified on Fly, 2026-10-01.** First setup run: image built via Fly's remote builder (202 MB),
  scheduled Machine created in `sjc`, and the triggered-on-create run published successfully
  (`run_id 20261001T0304Z-7f5497`, 2,010 objects, 509 conjunctions - 1 high / 32 moderate / 476
  low - in 5.3 s). The public URL is `https://<bucket>.fly.storage.tigris.dev/reports/current.json`,
  confirmed with a direct `curl` returning `200 OK` and the matching `run_id`.
