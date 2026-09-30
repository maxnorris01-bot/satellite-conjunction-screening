# ADR 0008: Screening evals are oracle-checked synthetic scenarios plus named real-data encounters

**Status:** Accepted, 2026-09-29.

## Context

The repo came from an LLM-app template whose eval harness (`evals/run.py`, `app.pipeline`) scored
an echo placeholder with `expected_contains` string matching. The screening pipeline makes no LLM
calls, so that harness measured nothing. Every `make eval-fast` pass so far was vacuous.

A frozen-snapshot parity test already exists (`tests/regression/`). It pins the whole default-scope
output bit for bit, which is the right gate for pure speedups, but it can't say *whether* the output
is right, only that it didn't change. When it fails, it doesn't say which behavior moved either.

## Options considered

1. **Named encounters on the frozen snapshot only.** Cheap, real data. But nothing checks
   correctness independently, and it overlaps heavily with the parity test.
2. **An oracle recall metric on a subset of the real snapshot.** The strongest claim, but brute
   force over even a few hundred real objects for 24 h is slow. A real subset also gives no control
   over which edge cases (window edges, threshold edges, slow crossings, missing SATCAT) actually
   occur.
3. **Engineered synthetic scenarios checked against an independent oracle, plus named encounters on
   the real snapshot.** More new code (a scenario builder and an oracle), but each edge case exists
   by construction, the oracle makes the expected answer independent of the screener's logic, and
   real-data cases still pin human-checked facts.

## Decision

Option 3, chosen by Max this session over options 1 and 2.

- **Scenarios** (`evals/build_fixtures.py` -> `evals/fixtures/`) are circular LEO element sets
  placed by a Newton solve on real SGP4, so each designed encounter happens under the same dynamics
  the screener uses. Two objects crossing at a point both move horizontally there, so a radial
  offset sets the miss distance. (The first build offset them sideways, which only moved the TCA,
  and every designed miss came out wrong. The oracle caught it.) The fixtures are written as
  CelesTrak cache files and served through the real fetch path, with the network blocked.
- **The oracle** (`evals/oracle.py`) runs raw SGP4 on a 1 s grid, checks every pair at every sample
  and refines each local minimum under `threshold + 16 km`. It shares no code path with the
  screener's search radius, KD-tree or straight-line prediction. It only reuses `build_satrec`
  (element parsing) and the 14-day stale rule, which it re-applies itself.
- **The expected answer is the oracle's output, not the design.** A scenario's designed miss is a
  target, recorded in its `scenario.json`. Same-altitude crossing pairs re-meet every half orbit at
  drifting misses, and those re-encounters are real encounters the screener must also find.
- **Named cases** pin the closest pass per pair (risk level, miss range, event count), absent
  pairs, co-located pairs and drops, so risk-table changes (which the geometric oracle can't see)
  fail a specific case.

## Consequences

- The harness was shown to be able to fail. Four deliberate breakages each failed at least one case
  (table in `evals/README.md`). A harness change should repeat that check.
- `min_pass_rate` goes to 1.0: the pipeline is deterministic, so any failing case is a bug, and the
  template's 0.90 (sized for LLM variance) would let one broken case in ten through.
- Cost is always $0. The `max_mean_cost_usd` / `max_total_cost_usd` thresholds stay so a future LLM
  step shows up without a harness change.
- The oracle scales as pairs x samples, so scenarios must stay small (40 objects for 6 h takes well
  under a second). Checking screening recall on real data at scale would need a different design,
  such as a SOCRATES cross-check (already on the to-do list as a spot check).
- Synthetic scenarios cover a single 780 km shell of circular orbits. Eccentric orbits,
  mixed-altitude crossings and GEO aren't exercised yet. Add scenarios as those scopes matter.
