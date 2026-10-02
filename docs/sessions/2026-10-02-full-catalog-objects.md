# Session 2026-10-02: full-catalog scope, objects/current.json, Fly resize and deploy

Branch: `feat/full-catalog-objects`. This implements ADR 0010 (with its 2026-10-02 amendment), the
repo side of `docs/todo.md`'s foundation-gate item.

## What changed and why

- **Scope** (`config/screening.yaml`, and the `Settings` default to match): CelesTrak's full
  published catalog, `active` plus `fengyun-1c-debris`, `iridium-33-debris` and
  `cosmos-2251-debris`. This is the amendment's option (a). I checked CelesTrak's group index:
  those are the only debris groups it lists, and `cosmos-1408-debris` no longer exists. The result
  is 19,308 objects fetched and 19,240 screened. Tests and evals pin the MVP demo scope explicitly,
  so they're unaffected.
- **`objects/current.json`** (`app.reporting.objects_builder`, published by `app.publish`): every
  screened object as `norad_id`, `name`, `tle_line1`, `tle_line2`, `element_epoch_utc`,
  `satcat_owner`, `object_type`, `active_payload` and `source_groups`, plus `schema_version` 1,
  `run_id`, `generated_at_utc` and `object_count`.
  - TLE lines come from `sgp4.exporter.export_tle`. 668 objects have catalog numbers above 99999
    and use Alpha-5 (100057 -> `A0057`), which I checked round-trips through `sgp4`.
  - It's uploaded gzipped, with `Content-Encoding: gzip` and `Content-Type: application/json`,
    after the snapshot and before the report. Max confirmed this is the intended design for
    browser `fetch()`, and ADR 0010's wording was tightened so it no longer suggests matching the
    snapshots' opaque `.json.gz` style.
  - `RunOutput` now carries the screened objects. `ObjectStore.put` takes an optional
    `content_encoding`. The publish log line adds artifact sizes and whole-process `peak_rss_mb`,
    so memory headroom can be read from `fly logs`.
- **Fly Machine size** (Makefile `FLY_MACHINE_FLAGS`): `--vm-cpus 4 --vm-memory 8192`
  (shared-cpu-4x, 8 GB). That's 2.85x the measured peak. Shared CPUs cap memory at 2 GB per vCPU.
- **Docs:** ADR 0010 gained a measurement section (local and Fly) and the Content-Encoding
  clarification. Also updated: working notes, README (scope, Quickstart note, Daily run artifacts
  and Machine size) and to-do.

## Decisions asked mid-session

1. **Catalog definition.** The options were (a) a CelesTrak group union or (b) the Space-Track
   full GP catalog. **Picked (a).** (b) is deferred to its own future ADR, now a "Later" to-do.
2. **Report and objects size vs. Vercel's ~4.5 MB response cap.** Max recorded the resolution in
   ADR 0010's amendment (direct bucket fetch with CORS for the two large files, and a small
   `/summary` function). **No trimmed report or API work this session.**
3. **Machine size:** shared-cpu-4x with 8 GB. **Approved** after I reported the measured numbers
   and per-run cost.
4. **flyctl install:** Homebrew isn't installed here, so I used Fly's official install script
   (`~/.fly/bin`). **Approved.** Max ran `fly auth login`.
5. **`Content-Encoding: gzip` for `objects/current.json`.** **Approved as the correct design**, and
   the ADR wording was clarified.

Max's instructions this session arrived as pasted blocks relayed from the Cowork session. Max
confirmed that relay before any external action.

## Measured numbers

**Local, three fresh-process runs of the full `app.publish` job on an Apple M5 (32 GB):**
- Peak RSS: 2,863-2,870 MB.
- Wall time: 34.9-37.5 s.
- Output: 56,367 conjunctions; a 78 MB report; `objects/current.json` at 7.86 MB raw and 1.39 MB
  gzipped.

**On Fly** (shared-cpu-4x, 8 GB, `sjc`), run `20261002T0403Z-4a2f42`:
- **Peak RSS: 2,804 MB.**
- **Pipeline total: 109.6 s** (screening 81.3 s, propagation 19.0 s).
- About 2 minutes from Machine start to publish. Exit code 0.
- Cost: about $0.0035 per run, about $0.11 a month.

## Deploy and verification

1. `make fly-build` built remotely and pushed `registry.fly.io/satellite-conjunction-screening:95d93aa`
   (205 MB).
2. The first `make fly-update FLY_MACHINE_ID=1850e47cdd43e8` **failed** with `MANIFEST_UNKNOWN`
   seconds after the push. I confirmed the Machine was unchanged, and an identical retry 18 s later
   succeeded. This looks like registry propagation lag.
3. **The update didn't start the stopped Machine**, contrary to my plan. My first log poll matched
   the previous day's 03:03Z run (old image, MVP scope) and briefly looked like success. I caught
   that before relying on it, started the Machine once with `fly machine start`, and re-polled only
   for log lines after that start time.
4. **Verified in the public bucket:** `reports/current.json` (78.0 MB), `objects/current.json`
   (`Content-Encoding: gzip`, 1.39 MB, 19,240 objects) and `snapshots/current/manifest.json` (4
   groups, 8 files) all carry run id `20261002T0403Z-4a2f42`. The Machine's `schedule: daily` and
   `restart: no` are intact.

## Eval numbers

`make eval-fast`: pass rate 1.0 (12/12), p95 1.33 s, $0, oracle recall 1.0. The pipeline logic is
unchanged; the evals pin the MVP scope.

## Test / lint / typecheck

`make lint` is clean, `make typecheck` is clean (28 files), and `make test` passes (35 tests; 4 new
for the objects builder, and the publish test was extended).

## Open questions / flag for review

- **Stale snapshot files:** `snapshots/current/gp-iridium-NEXT.json.gz` and
  `satcat-iridium-NEXT.json.gz` are still in the bucket from the old scope. The manifest excludes
  them. Deleting them is on the to-do list as opportunistic.
- **Bucket CORS** for the two large files (ADR 0010 amendment) isn't configured yet. It's on the
  to-do list as part of the gate remainder.
- **README Results row:** it still describes the MVP demo scope (pinned by tests). A full-catalog
  results row could come with the `portfolio-site` work.
- **`fly machine update` doesn't start a stopped Machine.** The README's update steps now say so
  (`fly machine start <id>` to run immediately) and mention the `MANIFEST_UNKNOWN` retry.

## Next command

Committed on `feat/full-catalog-objects`, pushed and opened as a PR (not merged):

```bash
gh pr view --web
```
