# Session 1 - Pipeline spike: fetch -> propagate -> screen -> assess -> report

**Date:** 2026-09-27 · **Branch:** `feat/session-1-pipeline-spike` · **LLM calls in pipeline:** zero

## What got built

The four core pipeline functions from the spec, plus JSON report output and per-step timing
traces. All of it runs against real CelesTrak data.

| Step | Where | What it does |
|---|---|---|
| `fetch_tle_data` | `src/app/data/celestrak_client.py`, `tle_cache.py`, `models.py` | Pulls CelesTrak GP elements (OMM JSON) **and** SATCAT metadata (object type, operational status) for named groups. Caches each raw response on disk for 2 h (CelesTrak's refresh cadence and fair-use rule). Merges duplicates across groups by catalog number. A bad record is logged as a parse failure and never crashes the run. |
| `propagate_orbits` | `src/app/propagation/sgp4_propagator.py` | Vectorized SGP4 (`SatrecArray`, C-accelerated backend confirmed active) over the window in TEME. Drops stale elements (> 14 days), init failures and any SGP4 error code (e.g. decay mid-window), recording each drop in the report. |
| `screen_conjunctions` | `src/app/screening/conjunction_screen.py` | Naive all-pairs distance per timestep, as the spec asked. Detects closest approaches *between* samples (see below). Refines each candidate with SGP4 and separates docked/co-located pairs out. |
| `assess_risk` | `src/app/risk/risk_model.py` | ADR 0004's threshold table (high / moderate / low) over miss distance, closing speed and active-payload status. |
| Report | `src/app/reporting/report_builder.py` | Versioned JSON (`schema_version: 1`) written to `runs/reports/<run_id>.json`: parameters, scope, dropped objects, per-step timings, one record per encounter, a separate co-located list, and an explicit limitations note. |
| Orchestration | `src/app/conjunction_pipeline.py`, `src/app/cli.py`, `make screen` | Each step runs in a `tracing.span`, producing one JSON line per step in `runs/trace.jsonl`, tagged with `run_id`. |
| Config | `config/screening.yaml`, `src/app/settings.py` | Scope, window, step, threshold and risk bands. CLI flags override scope, window, step and threshold. |

### The one design change that matters: between-sample detection

Following the spec's step 4 literally (flag a pair when `distance < 5 km` at a 60 s sample) would
have found almost nothing. At the observed median closing speed of 13 km/s, objects move about
800 km relative to each other between samples. Instead, each sample keeps pairs within
`5 km + 16 km/s x 30 s = 485 km`, solves the straight-line closest approach over the half-step
either side, and then refines with real SGP4. The linear estimate was within 9 m of the refined
answer across all 460 encounters. Details and alternatives are in
[ADR 0006](../adr/adr-0006-between-sample-closest-approach-detection.md).

### Surprise: docked vehicles look like zero-miss conjunctions

CelesTrak publishes the host station's elements for every docked vehicle and module (Soyuz,
Progress, Crew Dragon, Cygnus, CSS modules), so their separation is exactly 0.0 km. Pairs whose
relative speed stays under 0.1 km/s are reported as `co_located_pairs` and not risk-rated.
Without this, the top of the report would have been 38 meaningless ISS/CSS "conjunctions".

## Results on the real scope (`stations` + `fengyun-1c-debris`, 24 h, 60 s, 5 km)

Canonical run: `20260928T0050Z-06c87c` (window start 2026-09-28 00:50 UTC).

- **Fetched 1,990 objects** (22 stations + 1,968 Fengyun-1C). 0 parse failures, 0 missing SATCAT
  records. **1,937 screened**, 53 dropped as stale (debris epochs 15-27 days old). 0 SGP4 errors.
- **460 conjunctions flagged under 5 km: 18 moderate, 442 low, 0 high.** All are debris vs.
  debris. The closest was FENGYUN 1C DEB 31685 vs. 36160 at **0.113 km, 14.47 km/s**, TCA
  2026-09-28T10:46:52Z.
- **39 co-located pairs** (38 ISS/CSS docked combinations plus 1 slowly drifting debris pair).
- **Sanity check on the geometry:** miss distances in 1 km bins (0-5 km) were 18 / 60 / 82 / 119 /
  181. Random crossings should grow linearly with distance, which predicts 18 / 55 / 92 / 129 /
  166. That close match is good evidence the geometry and units are right.

**Why no "high":** the stations (385-426 km) and Fengyun-1C debris (about 800 km) don't overlap in
altitude, so no station ever meets debris. As a supplementary check I ran `iridium-NEXT` +
`fengyun-1c-debris` (run `20260928T0052Z-0c8580`). It found 510 encounters, including **50
debris-vs-Iridium passes under 5 km, 13 rated moderate** (under 2.5 km with an active payload).
That confirms the active-payload path works on real data. None came under 1 km in that window, so
"high" is covered only by unit tests so far.

## Timing numbers (Intel i5-6267U, 2 cores, sgp4 C backend)

| Step | Run 1 (cold fetch) | Run 2 (cached) | Iridium run |
|---|---|---|---|
| `fetch_tle_data` | 1.60 s | 0.30 s | 0.65 s |
| **`propagate_orbits`** (about 1,940 objects x 1,441 steps = 2.8M states) | **2.42 s** | **1.56 s** | **1.59 s** |
| `screen_conjunctions` (2.7B pair-checks) | 23.95 s | 21.27 s | 23.40 s |
| `assess_risk` | 0.002 s | 0.003 s | 0.002 s |
| `write_report` | 0.03 s | 0.04 s | 0.04 s |
| **Pipeline total** | **28.0 s** | **23.2 s** | **25.7 s** |

Peak RSS about 410 MB. Position arrays are 69 MB, plus velocities of the same size.

**What this says about ADR 0003's urgency.** Propagation is not the bottleneck: about 1.6 s for
2.8M state evaluations, which is linear in object count. Screening is. About 13 s of the 21 s is
the O(n^2) distance matrix itself (measured separately at 9.2 ms per timestep). The rest is
candidate handling and roughly 500 SGP4 refinements. Extrapolating the naive screen to about 30k
objects gives roughly 240x the pairs, so about 50+ minutes per 24 h window. It also needs about 7
GB of pair-index arrays, which alone rules it out on this machine. So:
- **The KD-tree fine filter is required before any meaningful scale-up, not optional.** At the
  current 2,000-object scope the naive version is fine (about 25 s).
- **Propagation memory, not time, is the full-catalog issue for that step.** It would need about
  1 GB each for positions and velocities at 30k x 24 h x 60 s, so it will need time-chunking.

**Unexplained one-off:** the very first CLI invocation took 560 s wall-clock, even though the
pipeline's own spans total 28 s and user CPU was only 25 s. The process was idle for the rest.
Every run since has had wall-clock about equal to pipeline time plus about 2.5 s of imports. It's
most likely the first `uv run` after the `pyproject.toml` change, or macOS scanning freshly built
native libraries on first load, but I didn't confirm either. It's parked in `docs/todo.md`.

## Decisions made this session

All of these are logged with reasoning in `docs/working-notes-and-decisions.md`:
- Between-sample closest-approach detection and the co-located split (new ADR 0006).
- OMM JSON instead of TLE lines, because catalog numbers above 99999 are already live.
- CelesTrak SATCAT supplies object type and status, so Space-Track is off the MVP's critical path.
- Elements older than 14 days are dropped (53 fragments this run).
- Code stays under the template's `src/app/` with the spec's subpackages. The screening config is
  `config/screening.yaml`, to avoid clashing with `evals/thresholds.yaml`.
- The first risk-table numbers (1 km / 2.5 km-if-active / 1 km/s), with reasoning.
- `pyproject.toml`: mypy `python_version` changed 3.11 -> 3.12, because the locked numpy 2.5 stubs
  use 3.12-only syntax, which broke `make typecheck` before any project code was checked. Added
  `ignore_missing_imports` for `sgp4.*` and `scipy.*`, which ship no type info.

No questions came up mid-session that needed your input. The two judgment calls where the spec was
ambiguous (between-sample detection, and treating docked pairs as co-located) are written up above
and in ADR 0006 for review.

## Status

- `make lint`: clean. `make typecheck`: clean (24 source files). `make test`: **24 passed**. That
  covers parsing, caching, a mocked CelesTrak fetch, SGP4 sanity, stale/decay drops, synthetic
  between-sample geometry, the risk table and report shape. All tests run offline.
- `make eval-fast` (mock): pass rate 1.0 (2 cases), p95 0.0015 s, $0.00. This is the template's
  placeholder harness and doesn't exercise the screening pipeline at all. It's plumbing only.
  `make eval-fast-live` was deliberately **not** run: there are no prompts or LLM calls to measure.
  A screening regression eval (a frozen GP snapshot plus expected encounters) is on the to-do list.
- README not updated (deferred to a later session by the spec).
- Space-Track registration: not something I can do. It's still Max's to kick off.

## Open questions / flag for review before merge

1. **Demo scope.** Keep `stations` (it only yields co-located docked pairs), or switch the default
   to something that overlaps the debris shell, such as `iridium-NEXT` + `fengyun-1c-debris`?
2. **Risk thresholds** are defensible first numbers, not calibrated ones. Worth a sanity pass
   before they appear in the README.
3. **Co-located by speed alone** would hide a slow drift toward collision (see ADR 0006). This is
   fine for the MVP, but it's a known gap.
4. **One-off 560 s first run** (above). Watch for it on the next cold start.
5. `cosmos-1408-debris` is down to about 2 objects, so the spec's "e.g. Cosmos-1408" suggestion is
   no longer viable.

## Next command

```bash
git log --oneline main..feat/session-1-pipeline-spike && git diff main --stat
make test && make screen      # re-run end-to-end (served from the 2h cache if run soon)
```
