# Session 2, Step A - KD-tree fine filter (algorithmic swap only)

**Date:** 2026-09-27 · **Branch:** `feat/session-2-kdtree-fine-filter` · **LLM calls:** zero

This session did Step A only. Step B (scaling spike) and Step C (coarse filter) were deliberately
not started; whether they're needed depends on the numbers below. The plan,
`docs/session-2-plan-screening-at-scale.md`, wasn't in the repo when the session started, so the
work followed the kickoff prompt's Step A description. The plan appeared mid-session, and its Step
A matches what was built. It was committed as-is in the cleanup pass (below).

## What changed

`src/app/screening/conjunction_screen.py`: at each timestep, the O(n^2) `pdist` distance matrix
plus `np.triu_indices` lookup is replaced by `cKDTree(positions).query_pairs(485 km)`. The radius
comes from ADR 0006 as before. That's the whole change. The closest-approach math, event splitting,
SGP4 refinement, co-location split, risk model and report records are untouched.

- `query_pairs` returns index pairs with `i < j`, the same orientation as the old `triu_indices`,
  so relative position and velocity vectors carry identical signs. That's what makes bit-identical
  output possible.
- `query_pairs` tests `<= r` where the old filter tested `< r`. A pair sitting exactly on the radius
  can close to at best exactly the threshold, which the strict `miss < threshold` check rejects,
  so the difference can never change a result (commented in code).
- **Report diagnostics changed** (in `summary.screening` only; no conjunction record changed shape):
  `pairs_per_timestep` and `pair_checks` were removed, because no all-pairs check happens anymore.
  `all_pairs_per_timestep` (the naive problem size, for comparison) and `neighbor_search` were
  added. `schema_version` was bumped from 1 to 2 in the cleanup pass (below): any report shape
  change bumps the version, not only record changes.
- No O(n^2) arrays remain in memory. The old code's pair-index arrays would have been about 7 GB
  at 30k objects.
- **New test:** `test_many_objects_match_an_exact_closest_approach_oracle`. 120 straight-line
  objects pass through six small hubs from random directions, which produces 342 encounters under
  5 km at arbitrary sub-sample times, including 5 s from each window edge. For straight lines the
  true closest approach is exact, so any pair the neighbor search missed would fail the test. I
  confirmed it catches a deliberately broken search (radius halved), so it's a real guard.

## Parity check against the known-good baseline: PASSED (exact)

The baseline is run `20260928T0101Z-c6e1f2` (from the session-1 review follow-up): `iridium-NEXT`
+ `fengyun-1c-debris`, window start 2026-09-28T01:01Z, 24 h, 60 s step, 5 km threshold.

A live `make screen` can't reproduce a baseline. It starts its window at the current minute, and
the 2 h cache eventually refetches newer elements. So the check ran on **frozen inputs**:

1. I copied the four cached CelesTrak responses the baseline used (all fetched between 00:35 and
   00:52 UTC, before its 01:01Z window start, and unchanged since) to a snapshot.
2. I ran the pipeline on that snapshot with the window start pinned to 01:01Z.
3. **The old code first** (from `main`): its output matched the committed baseline report record
   for record. That proves the harness reproduces the baseline before it's used to judge anything.
4. **Then the KD-tree code**, compared record for record against the old code's output.

| | Baseline (old, all-pairs) | KD-tree | Match |
|---|---|---|---|
| Conjunctions | 509 | 509 | identical: pair, TCA, miss, speed, risk, linear estimate |
| high / moderate / low | 0 / 31 / 478 | 0 / 31 / 478 | yes |
| Closest active-payload pass | 1.2889 km | 1.2889 km | yes |
| Closest overall | 0.1125 km | 0.1125 km | yes |
| Co-located pairs | 1 | 1 | identical |
| Pairs inside 485 km, summed over all steps | 4,716,128 | 4,716,128 | yes: the neighbor search returns exactly the same pairs |
| Candidate pairs / rejected after refinement | 500 / 0 | 500 / 0 | yes |

Nothing differs, so there's nothing to explain away.

**A correction to the kickoff prompt's numbers.** This scope screens **1,995 objects** (2,048
fetched, 53 dropped as stale), not about 1,937. The 1,937 figure was session 1's original
`stations` + Fengyun-1C scope. The 509 / 0-31-478 / 1.29 km baseline came from the review
follow-up run on the Iridium scope, which is what was checked here.

## New timing at this scope (Intel i5-6267U, 2 cores)

Head-to-head, both implementations on the same in-memory propagation output, 3 runs each:

| | All-pairs (old) | cKDTree (new) | Speedup |
|---|---|---|---|
| `screen_conjunctions` | 25.99 / 26.40 / 29.17 s, **median 26.40 s** | 2.92 / 2.94 / 3.11 s, **median 2.94 s** | **~9x** |
| Neighbor search alone, per timestep | 15.0 ms | 1.5 ms | 10x |

End-to-end through the CLI (`make screen`, default scope, cached fetch, two runs):

| Step | Run 1 | Run 2 | Session-1 equivalent |
|---|---|---|---|
| fetch | 0.37 s | 0.21 s | 0.35 s |
| propagate | 1.79 s | 1.64 s | 1.66 s |
| **screen** | **3.29 s** | **3.25 s** | 23.98 s |
| assess + write | 0.06 s | 0.05 s | 0.05 s |
| **Pipeline total** | **5.51 s** | **5.16 s** | 26.05 s |
| Wall-clock incl. startup | 6.56 s | 6.40 s | ~28 s |

These two runs flagged 502 conjunctions, not 509. That's expected: their windows started at 01:18Z,
not 01:01Z. It isn't a parity signal; the frozen-input check above is.

**Where the time goes now.** About 2.2 s of the ~3 s screen is the KD-tree search itself (1,441
steps x 1.5 ms). The rest is closest-approach math on the survivors and SGP4 refinement of the
~500 events, which scales with the number of encounters, not n^2. Propagation (~1.7 s) is now a
third of the pipeline.

## Input for deciding on Steps B and C (not measured, just what these numbers imply)

- At this scope, Step A alone solved the time problem: about 5 s per 24 h window.
- Scaling isn't answered yet. The KD-tree returned about 3,300 pairs within 485 km per timestep at
  2,000 objects. At about 30k objects in similar shells, that count grows roughly with n^2 (on the
  order of 700k pairs per step), and the survivor math is linear in it. So the post-search cost,
  not the tree, could become the bottleneck, and the 485 km radius (set by the 60 s step, per ADR
  0006) is the lever. That's exactly what Step B should measure rather than assume.
- Propagation memory (about 2 GB of positions and velocities at 30k x 24 h x 60 s) is untouched by
  Step A and is still an open item.

## Status

- `make lint`: clean. `make typecheck`: clean. `make test`: **26 passed**: 24 existing, plus the
  oracle test, plus the regression parity test from the cleanup pass. The existing screening
  tests pass unchanged.
- `make eval-fast` (mock): pass rate 1.0, 2 cases, p95 0.0016 s, $0.00. It's the placeholder
  harness and doesn't exercise screening. `make eval-fast-live` was not run: no LLM calls exist.
- Docs: ADR 0003 has a status update (fine filter implemented, coarse filter pending Step B).
  `docs/working-notes-and-decisions.md` records the parity-gated swap. `docs/todo.md` is
  re-ordered: Step B next, Step C conditional on it.

## Cleanup pass (after review, same branch)

- **`schema_version` 1 -> 2** (`src/app/reporting/report_builder.py`), for the diagnostics key
  change above. Reasoning is logged in `docs/working-notes-and-decisions.md`.
- **`docs/session-2-plan-screening-at-scale.md` committed as-is.**
- **The parity check is now a committed regression test**, in `tests/regression/`:
  - The frozen snapshot: the four CelesTrak cache entries, gzipped byte for byte to stay under the
    500 KB pre-commit file limit.
  - `expected_default_scope.json`: the all-pairs baseline's output (509 / 0-31-478 / 1,995 objects
    / 4,716,128 pairs within radius).
  - `test_default_scope_parity.py`: runs the full pipeline on the snapshot with any network request
    failing the test, and asserts exact counts and pairs, with tight numeric tolerances only for
    cross-platform float noise.
  - A README covering provenance, how to read a failure, and the deliberate-only regeneration
    rule.

  Re-run it with `uv run pytest tests/regression -v` (about 7 s). It also runs in `make test`, and
  the Makefile is unchanged. I verified it both ways: the old all-pairs code passes it (25.9 s) and
  a 300 km search-radius mutant fails it.
- One fix while wiring it up: `fetch_tle_data` constructs an HTTP client even when every response
  is cached, so the test's network guard fails requests rather than client construction. No
  pipeline code changed.
- The Step A parity result and timing numbers above are unchanged by any of this.

## Open questions

None open from Step A. The earlier questions about bumping `schema_version` and committing the
parity harness were resolved in the cleanup pass. Step B's scaling numbers are the next input.

## Next command

```bash
git log --oneline main..feat/session-2-kdtree-fine-filter && git diff main --stat
uv run pytest tests/regression -v && make test
```
