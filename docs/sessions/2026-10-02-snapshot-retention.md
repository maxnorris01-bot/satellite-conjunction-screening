# Session 2026-10-02: 7-day dated snapshot retention (ADR 0011)

Branch: `feat/snapshot-retention`. This was the first item on `docs/todo.md`: the retention ADR, a
prerequisite for the Phase 1 globe's time-slider backward range (the 2026-10-03 "Globe build plan"
amendment in the working notes).

## What changed and why

- **ADR 0011** (new) records the retention design, with the real compressed sizes the plan asked
  for. ADR 0009 got a status note: its "no history" stance is superseded.
- **`app.publish`:**
  - Each run also writes `objects/<date>.json.gz` and `reports/<date>.json.gz`. `<date>` is the
    UTC date of the run's window start, so a second run on the same date overwrites it.
  - Both are served with `Content-Encoding: gzip` and `Content-Type: application/json`, for the
    slider's browser `fetch()`.
  - The objects snapshot reuses the exact bytes of `objects/current.json`. The report is
    compressed at level 6: 5.42 MB vs 5.07 MB at level 9, but 0.27 s vs 0.97 s, and CPU matters
    more on Fly's shared vCPUs.
- **Retention step**, run after everything is published:
  - Deletes keys named exactly `<prefix><YYYY-MM-DD>.json.gz` that are dated more than
    `RETENTION_DAYS = 7` days before the run's date. That's at most 8 dated keys per prefix, so a
    full 7-day drag always lands on a stored date.
  - Never touches `current.json` or any other key.
  - Rewrites `history/index.json`: the dates that have both keys, newest first.
  - If this step fails, the run still logs `"published"` with a `retention_error` and exits 1, so
    a retention problem never undoes a publish.
- **Stores:** `ObjectStore` gained `list_keys` and `delete`. `S3Store` uses the
  `list_objects_v2` paginator; `LocalStore` walks the directory.
- **Tests (4 new, 1 extended):**
  - Dated copies match the current ones.
  - Pruning on both sides of the 7-day boundary.
  - Keys that must never be deleted.
  - The index's both-keys rule.
  - A retention failure keeps the publish but exits 1.
  - `LocalStore` list and delete.
- **Docs:** README Daily run section, working-notes entry, to-do (a new top item for the deploy).

## Choices made here that the build plan didn't specify (flag for review)

1. **`history/index.json`.** Without it, the frontend would have to probe for 404s or rely on
   public bucket listing to find past dates, and runs are fuzzy-scheduled, so gaps happen.
2. **Pruning in code rather than a bucket lifecycle rule.** It expires by snapshot date, not
   object age, and needs no extra bucket configuration.
3. **"Older than 7 days"** means dated more than 7 days before the run's date, so up to 8 dates
   are kept.
4. **The `.json.gz` names from the plan, with `Content-Encoding: gzip`.** A browser gets JSON. A
   client that ignores `Content-Encoding` (plain `curl`) gets gzip bytes, which the suffix
   signals.

No questions were asked mid-session; the plan and its amendment settled the rest.

## Verification

- `make publish-local` (full-catalog scope, fresh fetch) ran as `20261003T0434Z-389a93`, with
  2026-09-01 keys seeded.
- The two dated keys were written, and both decompress byte-identical to their `current.json`.
  The report compressed from 76.2 MB to 5.30 MB.
- Both seeded keys were deleted and `history/index.json` was written.
- **Peak RSS 2,875 MB** (2,863-2,870 MB before). **Wall time 41.3 s**, including a 4.6 s fetch.

**Cost:** at most about 55 MB of dated snapshots (8 x 6.8 MB), inside Tigris's 5 GB free tier.
Deletes and egress are free; each run adds 2 PUTs, 2 LISTs and 1 index PUT.

## Eval numbers

`make eval-fast`: pass rate 1.0 (12/12), oracle recall 1.0, $0. The screening pipeline is
unchanged.

## Test / lint / typecheck

`make lint` is clean, `make typecheck` is clean (28 files), and `make test` passes (39 tests).

## Open questions / flag for review

- **Not deployed.** The bucket has no dated keys until the Machine runs this code. The deploy
  sequence is the new top to-do item. The Machine size (8 GB) doesn't change.
- **History starts empty** and fills in one day per run, so the slider's full backward range is
  available about a week after deploy.
- **Frontend contract:** dates in the index can be non-contiguous, and a past date's report covers
  the 24 h after that run's window start.

## Next command

```bash
git log --oneline main..feat/snapshot-retention
```
