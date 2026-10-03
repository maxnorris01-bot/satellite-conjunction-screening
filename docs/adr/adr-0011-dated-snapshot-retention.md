# ADR 0011: Seven days of dated objects and report snapshots, pruned on every run

**Status:** Accepted, 2026-10-02.

## Context

The Phase 1 globe's time slider (the 2026-10-03 "Globe build plan" amendment in
`docs/working-notes-and-decisions.md`) goes up to 7 days back. Running today's elements backward
that far with SGP4 would drift from what actually happened, because drag and maneuvers aren't in
elements propagated the wrong way for a week. A past view therefore needs that day's own elements,
and near-miss replay on a past date needs that day's own report.

Today the daily Fly job (ADR 0009) only overwrites `reports/current.json` and
`objects/current.json` (ADR 0010), so nothing older than the latest run exists. ADR 0009 chose "no
history" deliberately and noted that adding it later "means writing dated keys alongside
`current`, not a redesign". This ADR is that addition.

**Measured sizes**, from the full-catalog run (ADR 0010; 19,240 objects, 56,367 conjunctions):

| Artifact | Raw | gzip level 6 | gzip level 9 |
|---|---|---|---|
| Report | 78.0 MB | **5.42 MB** (0.27 s on the M5) | 5.07 MB (0.97 s) |
| Objects | 7.86 MB | - | **1.39 MB** (already published at level 9) |

## Options considered

1. **Dated keys in the same bucket, pruned by the job itself.** One extra upload per artifact per
   run, plus a prune pass. Everything stays in the one place the frontend already reads (CORS is
   bucket-wide, so new keys need no CORS change).
2. **An S3 lifecycle rule** (expire objects after N days) instead of pruning in code. That's less
   code, but expiry is by object age, not by snapshot date, and runs on the provider's schedule.
   It's also another piece of bucket configuration to keep in sync, and Tigris's support for
   lifecycle rules would need checking.
3. **Keep extrapolating from today's elements.** No storage, but it's the inaccuracy the plan
   rules out.

## Decision

Option 1.

- **Keys.** Each run also writes `objects/<date>.json.gz` and `reports/<date>.json.gz`. `<date>`
  is the UTC date of the run's window start (`YYYY-MM-DD`, the same instant the `run_id` encodes).
  One snapshot per UTC date: if the fuzzy daily schedule (ADR 0009) runs twice on one date, the
  later run overwrites that date. If it skips a date, that date has no snapshot.
- **Encoding.** Both are gzipped and served with `Content-Encoding: gzip` and `Content-Type:
  application/json`, like `objects/current.json` (ADR 0010's clarification), so the slider's
  browser `fetch()` gets JSON transparently. The `.json.gz` suffix comes from the build plan's key
  names and signals that the stored bytes are gzip. A client that ignores `Content-Encoding` (for
  example plain `curl` without `--compressed`) gets the gzip bytes.
  - The **report** is compressed at **level 6**: 7% larger than level 9 but 3.6x less CPU, which
    matters more on Fly's shared vCPUs than 0.35 MB does.
  - The **objects** snapshot reuses the exact level-9 bytes uploaded as `objects/current.json`.
- **`current.json` stays as it is.** Today's live consumers (`/api/satellite/summary`, the globe's
  live and forward range) are unaffected. `reports/current.json` stays uncompressed, as now.
- **Retention: 7 days, pruned every run.** After uploading, the job lists the `objects/` and
  `reports/` prefixes and deletes every key matching `<YYYY-MM-DD>.json.gz` whose date is more
  than 7 days before the current run's date. That keeps at most 8 dated snapshots per prefix
  (the run's date plus the 7 before it), so a slider dragged a full 7 days back still lands on a
  stored date. Keys that don't match that exact pattern, such as `current.json` or anything added
  later, are never touched.
- **An index, `history/index.json`**, is rewritten every run after pruning. It lists each date
  that has *both* a dated objects and a dated report key, newest first, with both keys and the
  retention setting. The frontend reads it to know which past dates exist. Without it, a skipped
  or failed day would surface as a 404, or the frontend would need bucket listing, which isn't
  something the public bucket should be relied on for.
- **Order and failure handling.** Upload order is snapshot, manifest, `objects/current.json`,
  then the dated objects and dated report, then `reports/current.json` last, as before. Pruning
  and the index come after everything is published. A failure in that retention step doesn't
  undo the publish: the run logs `"event": "published"` with a `retention_error` field and exits
  non-zero, so the problem shows in `fly logs`. The next run retries the pruning naturally.

## Consequences

- **Storage is at most about 55 MB:** 8 x (5.4 MB report + 1.4 MB objects), plus the existing
  ~80 MB `current.json` pair. That's inside Tigris's 5 GB free tier; at $0.02/GB-month it would
  be about a tenth of a cent a month otherwise. Each run adds 2 PUTs, 2 LIST calls and 1 index PUT
  (well inside the 10,000 free class-A requests a month). Deletes and egress are free on Tigris.
- **Run time and memory change little.** Compressing the report adds about 0.3 s on the M5 (more
  on Fly) and holds about 5 MB extra in memory, against a measured 2.8 GB peak on an 8 GB Machine.
  The pruning and index steps are a few small requests.
- **History starts empty.** The first dated snapshot appears on the first run after deploy, and
  the slider's backward range fills in one day per run over the following week.
- **Past dates use that date's run window.** A dated report screens the 24 h after that run's
  window start, so "the near misses on date D" means "the ones that run predicted", which is what
  replay should show.
- **Gaps are real.** A failed or skipped run leaves a missing date in the index rather than a
  synthesized one. The frontend should handle a non-contiguous date list.
- If the window ever changes, it's the one constant `RETENTION_DAYS` in `app.publish`, and this
  ADR should be amended with the reason.

## Verified locally, 2026-10-03

`make publish-local` (full-catalog scope, fresh CelesTrak fetch, Apple M5), run
`20261003T0434Z-389a93`, with two seeded keys dated 2026-09-01:
- Wrote `objects/2026-10-03.json.gz` and `reports/2026-10-03.json.gz`. Both decompress to bytes
  identical to the matching `current.json`.
- The 76.2 MB report compressed to **5.30 MB** at level 6.
- Deleted both seeded 2026-09-01 keys and left the `current.json` keys alone. `history/index.json`
  lists the one date that has both keys.
- **Peak RSS 2,875 MB** (2,863-2,870 MB before retention). **Wall time 41.3 s**, including a
  4.6 s live fetch. Retention adds well under a second here and doesn't change the Machine size
  (8 GB, ADR 0010).

**Not yet deployed.** The bucket gets its first dated snapshot on the first Fly run after this
merges and the Machine is updated.
