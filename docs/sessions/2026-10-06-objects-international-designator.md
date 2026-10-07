# Session 2026-10-06: `international_designator` in `objects/current.json`

Branch: `feat/objects-international-designator`. This implements option (a) from the 2026-10-06
"Orbit line built; satellite age paused" working-notes entry: put the designator in the objects
file the site loads, so the satellite-age feature can read the launch year.

## What changed and why

- **`src/app/reporting/objects_builder.py`:** `object_entry` adds
  `"international_designator": obj.object_id.strip() or None` next to `name`.
  - It's the same value and name as the report's object records (`report_builder.py`).
  - A blank or whitespace-only value becomes `null` rather than an empty string. CelesTrak
    records with no `OBJECT_ID` at all never get this far: `OBJECT_ID` is a required GP field,
    so `parse_gp_records` reports them as parse failures.
  - The module docstring says the key is absent from files written before this change, and that
    readers must treat a missing key like null.
- **`schema_version` stays 1:** it's an additive field.
- **Tests** (`tests/test_objects_builder.py`):
  - The key is in the entry's field set, and the ISS fixture gives `"1998-067A"`.
  - Blank and whitespace-only designators give `null` rather than crashing.
  - Records missing `OBJECT_ID`, or with it empty, are parse failures and never reach the
    builder.
- **Schema docs kept in sync:** the README's Daily run table (with a note that the key is absent
  before 2026-10-06), and a dated note on ADR 0010's field list.
- **Working notes and to-do:** a decision entry; satellite-age item 2 updated (decision made,
  pipeline done, the site must treat a missing key as "Unknown"); a new Up next item for the
  redeploy.

**Checked on real data** (the frozen snapshot, no network): all 2,048 records give a well-formed
designator (`YYYY-NNNA..`) with no nulls. Launch years are 1999 for the 1,968 Fengyun-1C debris
and 2017-2023 for Iridium NEXT.

## Test / lint / typecheck / evals

`make lint` and `make typecheck` are clean, and `make test` passes (51; 3 new). `make eval-fast`:
pass rate 1.0, oracle recall 1.0. Screening is unchanged.

## What has to be redeployed, and how to verify

**Merging doesn't change the daily run.** GitHub Actions starts Fly Machine `1850e47cdd43e8`,
which runs its already-deployed image. Only a new image changes what gets published.

- **What to redeploy:** the image, using the existing Makefile targets.
- **The scheduled-machine config isn't affected.** `FLY_MACHINE_FLAGS` has no `--schedule` (ADR
  0012), and `fly machine update` leaves the absent schedule absent. The update keeps restart
  `no` and shared-cpu-4x/8 GB, and doesn't start the Machine. The GitHub workflow refers to the
  Machine by id, not by image, so it needs no change.

Run in order, after the PR merges:

```bash
git checkout main && git pull                     # build from merged main: the image tag is HEAD's short SHA
make fly-build                                    # remote build, pushes registry.fly.io/satellite-conjunction-screening:<sha>
make fly-update FLY_MACHINE_ID=1850e47cdd43e8     # if MANIFEST_UNKNOWN right after the build, re-run it a few seconds later
fly machine status 1850e47cdd43e8 -a satellite-conjunction-screening                    # Image: ...:<sha>
fly machine status 1850e47cdd43e8 -d -a satellite-conjunction-screening | grep schedule # expect no output
gh workflow run daily-run.yml                     # needs 2 h since the last publish, or the cooldown check fails it
gh run watch                                      # pick the run; expect green with a fresh snapshot date
```

Then check the bucket:

```bash
B=https://satellite-conjunction-screening.fly.storage.tigris.dev
curl -sS --compressed "$B/objects/current.json" | jq '{run_id, generated_at_utc,
  iss: (.objects[] | select(.norad_id == 25544) | {norad_id, name, international_designator}),
  all_have_key: ([.objects[] | has("international_designator")] | all)}'
```

Expected:
- `iss.international_designator` is `"1998-067A"`.
- `all_have_key` is `true`.
- `run_id` matches the workflow summary's run id and `history/index.json`'s `latest_run_id`.
- The same query on that day's `objects/<YYYY-MM-DD>.json.gz` gives the same answer.

The `--compressed` flag matters: the file is served with `Content-Encoding: gzip`.

**If the cooldown blocks the manual run:** the next scheduled run proves it on its own. Its cron
is 10:17 UTC, but recent runs have started around 16:45 UTC (GitHub best-effort). Check the same
`curl` after that run's workflow goes green.

**Older snapshots.** Retained dated files written before the redeploy
(`objects/<date>.json.gz`, up to 7 days, ADR 0011) don't have the key. The site must treat a
missing key as the "Unknown" age bucket. The last of them ages out about 7 days after the first run
with the field.

## Open questions / flag for review

- The site-side satellite-age feature (colour-by-age mode, launch-year filter) is still to build
  in `portfolio-site`, and it has to handle the missing key above.
- Nothing has been deployed. All of the above is Max's to run.
