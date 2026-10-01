# Evals

Screening evals: the real pipeline (`run_screening`: fetch -> propagate -> screen -> assess ->
report) on frozen inputs, scored case by case. No network and no LLM calls, so every run is free.
The design reasoning is in
[ADR 0008](../docs/adr/adr-0008-screening-evals-oracle-and-named-cases.md).

```bash
make eval-fast        # all current cases, a few seconds
```

## Two kinds of case

**Known-answer (synthetic).** `fixtures/<scenario>/` holds a tiny engineered catalog: circular LEO
element sets placed so that specific pairs pass specific points at specific times (a crossing
between samples, a sub-1 km hypervelocity pass, a pair just outside the threshold, a co-located
twin, a stale element set, and so on). With `"oracle": true`, the screener's output must also match
`oracle.py` exactly. The oracle is brute force: raw SGP4 on a 1 s grid, every pair, every sample,
then each local minimum refined. It shares none of the screener's search radius, KD-tree or
straight-line logic, so it's an independent check of recall and accuracy. It's too slow for anything
but small catalogs, which is why the scenarios are small.

**Named encounters (real data).** The frozen default-scope snapshot in
`tests/regression/default_scope_snapshot/` (the same files the parity test uses), with specific,
human-checked facts: the closest active-payload pass, the co-located debris pair, the stale-epoch
drops. The parity test in `tests/regression/` is all-or-nothing: any change fails it. These cases
show *which* behavior moved when something does.

## Case format

One JSON object per line in `cases/*.jsonl` (directly in `cases/`; the loader doesn't recurse).
Order matters: tiers take the first N, so the highest-signal cases go first.

| Field | Meaning |
|---|---|
| `id`, `category`, `note` | Name, `known-answer` or `snapshot`, and why the case exists |
| `fixture` | Directory (repo-relative) of CelesTrak cache files, `.json` or `.json.gz` |
| `groups`, `window_start_utc`, `window_hours` | Scope and window; `step_seconds` and `threshold_km` optional, else `config/screening.yaml` |
| `oracle` | `true` to also require exact agreement with `oracle.py` |
| `expect` | Any of: `objects_screened`, `by_risk_level`, `encounters` (per pair: closest pass's `risk_level`, `miss_km` range, `events` count, `satcat_owners` codes in pair order), `absent_pairs`, `co_located_pairs` (exact set), `dropped` (norad id + reason), `dropped_count`, `min_oracle_events` |

Oracle agreement means every oracle encounter under threshold is reported, TCA within 0.5 s and
miss within 1 m, with nothing extra reported, and the co-located pairs match. Encounters within 1 m
of the threshold are neither required nor forbidden.

## Summary metrics

`pass_rate` and `latency_p95_s` (the pipeline's own time per case, not the oracle's) gate against
`thresholds.yaml`. `oracle_recall`, `max_miss_error_km` and `max_tca_error_s` are reported so the
README can quote them. Cost is always $0 and stays in the summary so any future LLM step would show
up without a harness change. Reports land in `reports/` (git-ignored).

## Rules

- Cases, thresholds and fixtures change only in their own commits, never bundled with the code
  change they'd excuse, and never to make a failing eval pass.
- Regenerate synthetic fixtures only deliberately: `uv run python -m evals.build_fixtures`. A
  scenario's `scenario.json` records what it was designed to show. The designed misses are targets;
  the oracle, not the design, is the expected answer.
- Everything here is deterministic, so a flaky case is a bug to investigate, not something to
  quarantine. (The template's `known-unstable/` convention for LLM verdict instability was removed
  along with the placeholder LLM harness.)
- When a real screening failure turns up, add it as a case: a synthetic scenario that reproduces
  the geometry, or a named encounter on a frozen snapshot.

## Mutation check (how we know the cases can fail)

When the harness was built, each of these deliberate breakages was run against it
(2026-09-29, 12 cases):

| Breakage | Cases failing |
|---|---|
| Search radius sized for 4 km/s instead of 16 km/s | 8 (103 missed encounters in the crowd alone) |
| SGP4 refinement skipped (linear-estimate TCA used as-is) | 5 (miss errors of 1-3 m) |
| Unknown SATCAT status treated as inactive | 1 (`synthetic-missing-satcat-counts-as-active`) |
| Co-location disabled | 3 |

Re-run the same kind of check after any change to the harness itself.
