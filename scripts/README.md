# Measurement scripts

One-off performance measurements. These aren't part of the pipeline, CI or `make test`, and never
change `config/screening.yaml`'s demo scope.

| Script | What it measures | Written up in |
|---|---|---|
| `scaling_spike.py` | The full pipeline at `active` + `fengyun-1c-debris` scope (~18.5k objects): per-phase timing, peak memory, sanity checks | [ADR 0007](../docs/adr/adr-0007-coarse-filter-not-required-for-full-catalog.md), `docs/sessions/2026-09-28-session-2b-scaling-spike.md` |
| `coarse_filter_headroom.py` | How many KD-tree survivor pairs an altitude-band coarse filter could remove, validated against real conjunctions | ADR 0007 |

```bash
uv run python scripts/scaling_spike.py          # ~2.5 min; run 3x for a median
uv run python scripts/coarse_filter_headroom.py # needs a scaling_spike report in runs/scaling-spike/
```

## The frozen snapshot (local only, never committed)

`scaling_spike.py` works from a frozen copy of CelesTrak data in `cache/scaling-spike/`. That
directory is **gitignored** (`cache/` in `.gitignore`) and deliberately not committed: it's about
16 MB raw, and it's a measurement input, not a test fixture. The committed, reproducible
reference is the smaller regression snapshot in `tests/regression/` (about 213 KB gzipped).

- **With `cache/scaling-spike/manifest.json` present:** every run is served from the frozen files.
  Network requests are blocked, and the window start is pinned to the manifest's. Repeated runs
  measure identical inputs and never re-pull `active` from CelesTrak.
- **Without it** (a fresh clone, or after deleting the directory): the next run fetches `active` and
  `fengyun-1c-debris` (GP + SATCAT, 4 requests) **once**, pins the window start to that minute, and
  writes the manifest. That run *is* the re-freeze.

### Snapshot behind ADR 0007's numbers

If `cache/scaling-spike/` doesn't match this, you're measuring a different snapshot.

| | |
|---|---|
| Frozen / window start | 2026-09-28T01:35:00Z |
| Records | `active` 16,620 GP / 17,086 SATCAT; `fengyun-1c-debris` 1,968 GP / 3,532 SATCAT |
| Screened | 18,526 (61 stale elements + 1 SGP4 decay error dropped) |
| Result | 63,896 conjunctions: 2,299 high / 8,605 moderate / 52,992 low |
| `gp-active.json` | 7,583,452 bytes, sha256 `74d7a20d89d39cdb…` |
| `gp-fengyun-1c-debris.json` | 902,274 bytes, sha256 `edb0a29dfeb098a2…` |
| `satcat-active.json` | 6,241,158 bytes, sha256 `21c135b9918906f0…` |
| `satcat-fengyun-1c-debris.json` | 1,320,406 bytes, sha256 `9c68cdb55e4eb740…` |

## Re-freezing (deliberate, separate step)

The same policy as the regression baseline (`tests/regression/README.md`): re-freezing is done on
purpose, never as a side effect of re-running a measurement.

1. **Only re-freeze when you want a new measurement**: newer catalog data, a different scope, or
   the original snapshot was lost. For repeat timings of the same measurement, keep the existing
   snapshot.
2. **Re-freeze with** `rm -r cache/scaling-spike && uv run python scripts/scaling_spike.py`. That's
   one CelesTrak pull. Don't loop it: `active` is a large feed, and CelesTrak asks clients not to
   poll faster than its ~2 h refresh.
3. **A re-frozen snapshot is a new data point, not a correction.** Its numbers aren't directly
   comparable to ADR 0007's: the catalog changes daily. Record the new snapshot's identity (window
   start, record counts) next to its results, in a new session doc or an ADR update, and leave
   ADR 0007's figures as they are.
4. Commit any resulting doc updates on their own, separate from code changes.
