# Session 1 review follow-ups: demo scope, Cosmos-1408, Known failures

**Date:** 2026-09-27 · **Branch:** `feat/session-1-pipeline-spike` (same branch as the spike) ·
**Scope:** docs and config only. No pipeline logic changed.

These follow up on the review of [session 1](2026-09-27-session-1-pipeline-spike.md). They resolve
its open questions 1 (demo scope) and 5 (Cosmos-1408).

## What changed and why

1. **Default demo scope is now `iridium-NEXT` + `fengyun-1c-debris`** (`config/screening.yaml`,
   plus the matching code default in `src/app/settings.py`). With `stations`, the only results were
   docked-vehicle pairs, because the stations (385-426 km) never meet the Fengyun-1C debris
   (~800 km). Iridium NEXT shares the debris shell, so the demo now shows real
   active-payload-vs-debris screening. The spec's session-1 scope paragraph has a dated note
   recording the switch.
2. **Cosmos-1408 removed as a suggested debris source.** It only ever appeared in the spec, never
   in config or the README. CelesTrak's group is down to about 2 tracked objects.
3. **README Known failures section filled in.** It states plainly that no `high`-tier conjunction
   has been observed in real data at this scope, and that the high-tier logic is verified only by
   unit tests. A second entry covers the heuristic-not-Pc limitation (ADR 0004). The rest of the
   README is still the template's placeholder; the full README is deferred per the spec.
4. **Working notes:** added the scope decision. Replaced the now-resolved scope and Cosmos open
   items with a "no live high-tier example" item and a fuller entry for the unreproduced 560 s
   first run (what was measured, suspects, and how to split setup time from run time if it
   recurs). `docs/todo.md` is updated to match.

## Verification run on the new default

`make screen`, run `20260928T0101Z-c6e1f2`, 24 h window, 60 s step, 5 km threshold. CelesTrak data
was served from the 2 h cache, so no new requests were made.

- 2,048 objects fetched, 1,995 screened, 53 dropped as stale.
- **509 conjunctions: 0 high, 31 moderate, 478 low.** 1 co-located pair.
- 52 encounters involve an active Iridium satellite (13 moderate). The closest was 1.29 km, just
  outside the 1 km `high` band. The closest overall was 0.11 km, debris vs. debris.
- Timings: fetch 0.35 s, propagate 1.66 s, screen 23.98 s, assess 0.007 s, write 0.04 s,
  **total 26.05 s**, consistent with session 1.

## Status

- `make lint`, `make typecheck` and `make test` (24 passed) were re-run after these changes: all
  clean.
- `make eval-fast` wasn't re-run. No prompts, agent logic or pipeline code changed, and that
  harness doesn't exercise the screening pipeline.

## Open questions

None new. The remaining session-1 open questions (risk-threshold sanity pass, co-location by speed
only, the 560 s one-off) still stand.

## Next command

```bash
git log --oneline main..feat/session-1-pipeline-spike && git diff main -- README.md config/
```
