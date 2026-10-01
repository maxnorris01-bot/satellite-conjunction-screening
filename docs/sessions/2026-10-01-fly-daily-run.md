# Session 2026-10-01: daily run on Fly.io

Branch: `feat/fly-daily-screen`. This was the top item on `docs/todo.md`. The code is written and
verified locally; it is **not yet deployed**.

## What changed and why

Cowork had already decided on Fly.io over Lambda, with no retention window (recorded in
`docs/todo.md`, commit `174a5e2`). This session settled how the run is triggered and where its
output goes, then built it. Full reasoning is in ADR 0009.

- **`src/app/publish.py` (new entry point).** It runs the unchanged pipeline with a fresh temp
  CelesTrak cache, then uploads, overwriting the previous run's objects:
  - the raw CelesTrak snapshot as `snapshots/current/*.json.gz`
  - `snapshots/current/manifest.json` (run id and file list)
  - `reports/current.json`, uploaded last

  If the pipeline fails, nothing is uploaded, the process exits 1, and the previous report stays.
  Either way it logs one JSON line. `--local-dir` writes to a directory instead of the bucket.
  `--cache-dir` reuses an existing cache so local dry runs don't re-fetch inside CelesTrak's
  2-hour fair-use window.
- **Storage is Tigris** (Fly's S3-compatible store) via `boto3`, rather than a Fly volume. A volume
  is readable only by the Machine it's attached to, so neither `portfolio-site` nor the future API
  could read it. New dependencies: `boto3`, plus `boto3-stubs[s3]` in dev for strict mypy.
- **The trigger is a Fly scheduled Machine:** `--schedule daily --restart no --vm-memory 1024
  --region sjc`.
  - `--restart no` means a failed day doesn't retry in a loop against CelesTrak.
  - Fly's schedule is approximate (roughly daily, no fixed time). That's acceptable because each
    report records its window.
- **Infrastructure files:**
  - `Dockerfile`: `python:3.12-slim` plus uv, runtime dependencies only, with `src/` and
    `config/`.
  - `.dockerignore`.
  - `fly.toml`: app `satellite-conjunction-screening`, region `sjc`, build section only.
  - Makefile targets: `publish-local`, `fly-build` (remote build and push, tagged with the commit),
    `fly-machine-create` and `fly-update FLY_MACHINE_ID=...`.
- **Tests:** `tests/test_publish.py` (4 tests) covers upload order and content types, that the
  gzip and manifest contents round-trip, that a failed pipeline uploads nothing and exits 1, and
  that a missing `BUCKET_NAME` fails before the pipeline runs. CI never touches Fly or Tigris.
- **Docs:**
  - ADR 0009 (new), and ADR 0005 marked superseded.
  - A working-notes decision entry.
  - README: a "Daily run" section with the object layout, the dry run, the one-time Fly setup and
    the update flow. Also an updated project boundary, security notes, ADR table and "What's next".
  - To-do: the item is ticked, and a new top item covers the actual Fly setup.

## Decisions asked mid-session

I proposed the approach before writing code. Max chose:
1. **A public bucket** rather than a private one, so `reports/current.json` has a stable URL that
   `portfolio-site` can fetch now.
2. **Publishing the raw CelesTrak snapshot** alongside the report, which goes beyond the to-do
   item's wording.
3. **App name** `satellite-conjunction-screening`, **region** `sjc`.

## Verification

- `make publish-local` ran against the existing 15-minute-old cache, so nothing was fetched. It
  produced run `20261001T0237Z-94f74c`: 2,010 objects screened, 510 conjunctions (1 high, 31
  moderate, 478 low) and 3 co-located pairs. The report is 629 KB and the snapshot about 216 KB
  across 4 files plus the manifest.
- **Reproducibility check:** I re-ran the pipeline from the *published* snapshot with the report's
  window start. It reproduced all 510 conjunctions exactly (same pairs, TCAs, misses and risk
  levels).
- **Not verified:**
  - The Docker image has never been built. Docker isn't installed here, so the first build will
    happen on Fly's remote builder.
  - Nothing has run on Fly yet.
  - The Makefile's `fly` commands follow Fly's current docs but haven't been run.
  - The public URL host is the documented pattern, not observed.

## Eval numbers

`make eval-fast`: pass rate 1.0 (12/12), p95 1.32 s, $0, oracle recall 1.0. The pipeline is
unchanged; this was a regression check.

## Test / lint / typecheck

`make lint` is clean, `make typecheck` is clean (26 files), and `make test` passes (30 tests).

## Open questions / flag for review

- `fly deploy --build-only --push` with a `fly.toml` that defines no processes is the intended way
  to build an image without deploying, but it hasn't been run. If it complains, the fallback is
  `fly deploy --build-only --push --dockerfile Dockerfile`, or building with the Fly remote
  builder directly.
- `fly machine run` starts the Machine immediately on creation, so the first report lands at setup
  time, not a day later.
- Tigris bucket names are global. If `satellite-conjunction-screening` is taken, pick another name
  with `-n`; `BUCKET_NAME` follows automatically.
- A daily run at the default scope is 4 CelesTrak requests a day, well within fair use.

## Next command

Committed on `feat/fly-daily-screen` and opened as a PR (not merged). After merging, run the one-time Fly
setup from the README's "Daily run" section:

```bash
fly apps create satellite-conjunction-screening
fly storage create -a satellite-conjunction-screening -n satellite-conjunction-screening --public
make fly-build
make fly-machine-create
fly logs -a satellite-conjunction-screening
```
