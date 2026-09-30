# Session 2026-09-29: screening eval harness

Branch: `feat/screening-eval-harness`. Top item of `docs/todo.md`'s "Up next" list.

## What changed and why

Until now, `make eval-fast` scored the template's placeholder, `app.pipeline.run`, which echoes its
input, with `expected_contains` string matching. The screening pipeline makes no LLM calls, so every
eval pass in earlier sessions measured nothing. This session replaced it with evals that exercise the
real pipeline (`run_screening`: fetch -> propagate -> screen -> assess -> report) on frozen inputs,
with the network blocked.

- **Synthetic scenarios** (`evals/build_fixtures.py` -> `evals/fixtures/`, 132 KB). Nine small
  engineered catalogs of circular 780 km orbits: a crossing between samples, a sub-1 km
  hypervelocity pass (the only end-to-end check of the `high` tier, since the default scope has
  none), missing SATCAT counting as active, debris-debris under 1 km, a slow crossing, threshold
  edges (4.7 km flagged, 5.3 km not), window edges, a co-located twin plus a stale element set, and
  a 40-object crowd. A Newton solve on real SGP4 places each object within 1 m of its target point
  and time. The fixtures are written as CelesTrak cache files and served through the normal fetch
  path. The builder is deterministic: a rebuild is byte-identical.
- **An independent oracle** (`evals/oracle.py`): raw SGP4 on a 1 s grid, every pair, every sample,
  then each local minimum refined. It shares none of the screener's search-radius, KD-tree or
  straight-line logic. Synthetic cases must match it exactly (TCA within 0.5 s, miss within 1 m,
  nothing extra, same co-located pairs).
- **Named-encounter cases** on the frozen default-scope snapshot in `tests/regression/`: the
  closest active-payload passes (1.29 km vs IRIDIUM 115, 1.41 km vs IRIDIUM 167), the closest
  debris pass rating moderate not high, the slowest crossing staying a rated crossing, the
  co-located debris pair, and the 53 stale drops.
- **Runner** (`evals/run.py`) rewritten: per-case failure reasons, oracle recall and error in the
  summary, and cost is still reported (always $0) so a future LLM step shows up.
- **Removed:** `app.pipeline`, its smoke test, the example case and rubric, and
  `evals/cases/known-unstable/` (an LLM-variance convention; everything here is deterministic).
  **Kept:** `app.llm`, `app.mock_llm` and `prompts/`, as dormant template infrastructure.
- **Makefile:** `eval-fast-live` prints that there are no LLM calls and runs the same suite. All
  eval targets force mock mode and disable tracing.
- **Threshold change (its own commit):** `min_pass_rate` 0.90 -> 1.0. The pipeline is
  deterministic, so any failing case is a bug.
- **Docs:** ADR 0008 (design), `evals/README.md` (case format, rules, mutation check), README
  results row and Evaluation section, working-notes decision, to-do, and a lessons-learned entry
  for the template.

Two things the oracle and the scenario checks caught during the build, both in my scenario code,
not the screener:
1. The first build offset the second object sideways from the crossing point. At a crossing, the
   relative velocity is horizontal, so a sideways offset mostly moves the TCA: the designed misses
   came out at 0.05-0.6 km instead of 0.4-4.7 km. Switched to a radial offset, and the designed
   misses now land within 0.3 m.
2. Same-altitude pairs re-meet every half orbit at a drifting miss. The "5.3 km, must not be
   flagged" pair re-met at 4.79 km. That scenario now puts both edge passes 5 minutes apart, and
   its case uses a 36-minute window.

**Mutation check.** I ran four deliberate screener breakages against the final cases: search
radius sized for 4 km/s (8 cases fail), SGP4 refinement skipped (5), unknown SATCAT treated as
inactive (1), co-location disabled (3). So the cases can fail. The table is in `evals/README.md`.

## Decisions asked mid-session

1. **What the eval cases should measure.** The options were known-answer scenarios plus curated
   snapshot cases, curated snapshot cases only, or an oracle recall metric on real data. **Picked:
   known-answer plus curated.**
2. **What to do with the template's LLM eval plumbing.** The options were removing the placeholder
   but keeping `llm.py`, or removing all LLM code. **Picked: remove the placeholder, keep
   `llm.py`.**

## Eval numbers

`make eval-fast` (the only tier that matters; all 12 cases fit in it):

| Metric | Result | Threshold |
|---|---|---|
| Pass rate | 1.0 (12/12) | >= 1.0 |
| Latency p95 | 1.32 s | <= 30 s |
| Mean cost | $0.00 | <= $0.10 |
| Oracle recall | 1.0 (359/359 encounters) | reported |
| Max miss / TCA error vs oracle | 0.104 m / 0.5 ms | reported |

`make eval-fast-live` was not run separately: there are no LLM calls, and it now runs the same free
suite.

## Test / lint / typecheck

`make lint` is clean, `make typecheck` is clean (25 files), and `make test` passes (26 tests,
including the parity regression).

## Open questions / flag for review

- **Different machine.** This session ran on an Apple M5 (32 GB, arm64), and `.venv` didn't exist
  until `uv` created it, with CPython 3.14.7. The README and ADR 0007 timings are from the Intel
  i5-6267U (8 GB). The snapshot runs in about 1.3 s here against about 5 s there. I didn't re-time
  anything, and the README now says which machine its timing figures come from.
- **Dates.** The working-notes entry this session followed is dated 2026-09-30, but this session
  ran on 2026-09-29 (the system date), so this session's entries are dated 2026-09-29. One of the
  two may be off.
- **Scenario coverage.** Every scenario is a circular orbit at 780 km. Eccentric orbits and
  mixed-altitude crossings are on the to-do list as lower priority.
- **CI.** `eval-fast` runs on pull requests only. It now takes a few seconds and needs no secrets,
  so it could also run in the main `checks` job. Not changed here.
- `evals/oracle.py` imports the propagator's private `_jday`. It's harmless, but worth making
  public if the helper is touched again.

## Next command

Committed on `feat/screening-eval-harness` in four pieces, so cases and thresholds land separately
from the code, per `evals/README.md`: the harness (`feat:`), the fixtures and cases (`eval:`), the
`min_pass_rate` change (`eval:`) and the docs (`docs:`). Not pushed.

```bash
git log --oneline main..feat/screening-eval-harness && make eval-fast
```
