# Session 2, Step B - Scaling measurement at `active` + Fengyun-1C (18,526 objects)

**Date:** 2026-09-28 · **Branch:** `feat/session-2b-scaling-spike` · **LLM calls:** zero

This was measurement only. No screening algorithm changed, and the regression parity test still
passes unchanged. Step C (coarse filter) was **not** implemented; ADR 0007 goes back to Cowork
first. `config/screening.yaml`'s demo scope is untouched (still Iridium NEXT + Fengyun-1C).

## What was built

- **Phase instrumentation** (`src/app/screening/conjunction_screen.py`). `perf_counter`
  accumulators around existing code split screening into three parts:
  - neighbor search (tree build + query);
  - survivor closest-approach math (the per-timestep loop over the tree's survivors);
  - event refinement (event splitting + SGP4).

  Also added: mean/max pairs within radius per timestep, and `refined_events`.
- **Peak memory** (`src/app/conjunction_pipeline.py`): `resource.getrusage(...).ru_maxrss`
  recorded at the end of every pipeline step, in trace spans and in `RunOutput.peak_rss_mb`.
  It's normalized to MB, because macOS reports bytes and Linux reports KB.
- **`scripts/scaling_spike.py`**: a one-off measurement script, not a CLI flag. It needed
  freeze/pin behavior the CLI shouldn't carry. The first run fetched `active` + Fengyun-1C (GP +
  SATCAT, 4 requests, about 16 MB) **once** into `cache/scaling-spike/` (gitignored) and pinned the
  window start in a manifest. Every later run is served from that frozen copy with network access
  blocked. It writes a result JSON with timings, memory, swap activity and sanity data.
- **`scripts/coarse_filter_headroom.py`**: measures how many KD-tree survivor pairs an altitude-band
  coarse filter *could* remove, validated against every real conjunction. It's measurement only;
  it informed ADR 0007.
- **Report `schema_version` 3.** The diagnostics keys above are additive, but the rule logged at
  v2 says any shape change bumps the version. See the open questions.
- **Test:** `test_stats_report_phase_timings_and_pair_density`. 27 tests pass in total.

## Sanity checks (in place of parity, since there's no baseline at this scale)

| Check | Result |
|---|---|
| Fetched count vs. CelesTrak's listing | `active`: 16,620 GP records, 16,620 parsed, 16,620 unique NORAD IDs, 0 parse failures. Fengyun-1C: 1,968 / 1,968 / 1,968. The SATCAT listings cover every object (0 missing). Merged: 18,588 |
| Malformed/decayed elements logged and dropped, not miscounted | 62 dropped and each recorded in the report: 61 stale elements (> 14 days), and 1 SGP4 error 6 ("satellite has decayed"): STARLINK-38358 (NORAD 100560). 18,588 - 62 = 18,526 screened, which reconciles exactly |
| Risk counts plausible | 63,896 conjunctions: **2,299 high**, 8,605 moderate, 52,992 low. Not all-zero, not all-error. By type: PAY-PAY 62,601, DEB-PAY 833, DEB-DEB 451, PAY-R/B 11 |
| Geometry | The linear estimate is within 9 m of refined SGP4 (the same as at small scale). Relative speed median 11.0 km/s, max 15.3 km/s, both physical |
| Determinism | All 3 runs gave identical results |

**One observation, not a failure.** Miss distances don't follow the random-crossing curve
(proportional to d) that the debris-only scope matched. The 1-2 km bin has 4,861 against about
7,667 expected; the 3-5 km bins run high. That's consistent with the population being about 60%
Starlink with coordinated shell phasing, but it isn't proven. The same code matched the random
curve on the debris-only baseline, and the geometry checks pass.

## Before / after (medians of 3 fresh-process runs each, same instrumented code)

The before column was re-measured on the frozen 1,995-object regression snapshot with the new
instrumentation, because session 2a didn't split phases or record memory. It still reproduces the
509-conjunction baseline.

| | Session 2a scope (1,995 objects) | Step B scope (18,526 objects) | Ratio |
|---|---|---|---|
| **1. Propagation** | 1.60 s | **17.98 s** | 11.3x |
| **2. Neighbor search** (tree build + query) | 1.94 s | **34.70 s** | 17.9x |
| **3. Post-search, total** | 1.24 s | **72.03 s** | 58x |
| 3a. survivor closest-approach math | 1.12 s | 58.06 s | 51.7x |
| 3b. event splitting + SGP4 refinement | 0.11 s | 13.97 s | 122x |
| Screening total (2 + 3) | 3.17 s | 106.93 s | 33.7x |
| Pipeline total | 4.92 s | 139.75 s | 28.4x |
| **Peak memory** (`ru_maxrss`) | 362 MB | **2,214 MB** (runs: 2,214 / 2,271 / 2,068) | 6.1x |
| **Pairs within 485 km per timestep** (mean / max) | 3,273 / 3,875 | **162,656 / 165,015** | 49.7x |
| Refined events | 509 | 63,951 | 126x |
| Report file | ~1 MB | 76 MB | - |

Per-run Step B pipeline totals were 139.75 s, 140.56 s and 129.79 s.

- **Phase 3a is the bottleneck, as Step A predicted.** It's 42% of the pipeline, and it tracks
  survivor pairs (exponent 1.77 vs. 1.75 for pairs per step).
- **Memory:** peak memory is set during propagation. The position and velocity arrays are 641 MB
  each, plus a transient filtered copy.
- **Swap:** in every run, macOS swapped out about 1.5 GB of *other* processes' memory. This
  process had only 30-364 major page faults, so its timings weren't distorted by its own paging.

## Coarse-filter headroom (measured, not implemented)

| Altitude band | KD-tree pairs removed | Real conjunctions wrongly dropped (of 63,896) |
|---|---|---|
| Propagated radius range, widened by radial speed x step/2 | 61.4% | **0** (provably safe) |
| ADR 0003's mean-element band, pad 0 / 5 / 10 / 20 / 30 km | 74.4 / 68.1 / 63.4 / 49.4 / 46.3% | **1,212 / 304 / 254 / 127 / 45** |

The mean-element band misses the real SGP4 radius by a median of 7.0 km. It misses by 157-383 km
for highly elliptical deep-space orbits (MMS, XMM-Newton), and by tens of km for fast-decaying
objects.

## ADR 0007's conclusion

1. **The coarse filter is not required to reach full-catalog scale on time.** Extrapolating each
   phase at its measured exponent to about 30k objects gives about 5 minutes per 24 h window on
   this laptop, or about 5.2 minutes under a pure n^2 assumption. That fits a 2-hourly batch job.
   This is an extrapolation, not a measurement.
2. **Memory is the binding constraint, not time.** About 3.5 GB peak is projected at 30k objects
   on an 8 GB machine that's already swapping other processes at 2.2 GB. The next scaling step
   should be time-chunked propagation and screening (plus report streaming or a cap), not Step C.
3. **ADR 0003's coarse-filter design is unsafe as written.** If Step C is ever built, use the
   propagation-derived band: safe, and it cuts phase 3a by about 60%. It's an optimization, not a
   prerequisite.

## Other doc changes

- **README Known failures.** The entry is now titled for the *default demo scope* (still 0 high).
  It records the first live `high` examples from this run: 2,299, closest STARLINK-31121 vs.
  STARLINK-35643 at 0.026 km and 10.0 km/s. It's explicit that this shows the logic firing on real
  inputs, not that those passes are real threats, given TLE error and frequent Starlink maneuvers.
  The previous wording ("verified only by unit tests, not by any live example") was no longer
  true, so it had to change. The default-scope limitation itself is kept as-is.
- **ADR 0003** has a pointer to ADR 0007. The working notes record the Step B conclusion and the
  v3 schema bump. `docs/todo.md` now leads with the Cowork review of ADR 0007, then time-chunked
  propagation.

## Status

- `make lint`: clean. `make typecheck`: clean. `make test`: **27 passed**. That includes the
  frozen-snapshot parity regression, which confirms the instrumentation changed no results.
- `make eval-fast` wasn't re-run. No prompts, LLM calls or agent logic exist, and the placeholder
  harness doesn't exercise screening.
- The Step B snapshot (`cache/scaling-spike/`, about 16 MB raw) is deliberately **not** committed,
  per the "freeze locally" instruction and its size. Anyone re-running the spike re-freezes from
  CelesTrak once. The committed regression snapshot remains the reproducible, in-repo reference.

## Open questions

1. **Step C:** build it as an optional optimization using the propagation-derived band, or skip it?
   (For Cowork, per ADR 0007.)
2. **Full-catalog goal:** is full-catalog scale a target on this 8 GB laptop, or only on a
   deployed instance? If it's the laptop, time-chunking comes next.
3. **Schema-version rule:** should purely additive diagnostics keys bump `schema_version`? v3
   follows the current rule; bumping only for removals, renames and type changes is the more
   common convention.
4. **Demo scope and the `high` tier:** add a dense active constellation to the demo so `high`
   shows up in the default run, or keep the small demo and cite the Step B run?

## Next command

```bash
git log --oneline main..feat/session-2b-scaling-spike && git diff main --stat
uv run python scripts/scaling_spike.py      # ~2.5 min; served from cache/scaling-spike/ if present
```
