# ADR 0007: The KD-tree alone reaches full-catalog scale on time; the coarse filter is optional, and ADR 0003's element-band design is unsafe as written

**Status:** Proposed (session 2 Step B, 2026-09-28). The conclusion comes from measurement; whether
and how to build Step C goes back to Cowork before any implementation.

## Context

ADR 0003 planned two stages for full-catalog screening: a coarse filter on altitude bands from
orbital elements, then a per-timestep KD-tree. Session 2 Step A shipped the KD-tree alone, with
exact parity against the naive screen. Step B measured it at about 9x the object count to decide
whether the coarse filter (Step C) is actually needed before scaling further.

**Setup:** CelesTrak `active` (16,620 objects, dominated by Starlink) plus `fengyun-1c-debris`
(1,968). That's 18,588 merged objects, 18,526 screened (61 stale elements dropped, 1 SGP4 decay
error dropped). The data was fetched once on 2026-09-28 at 01:35Z and frozen. Window: 24 h at a
60 s step, 5 km threshold, 485 km search radius. Machine: Intel i5-6267U (2 cores, 4 threads),
8 GB RAM. Every run is a fresh process; figures are medians of 3 runs, and all 3 produced
identical results.

## Measurements

| | Step A scope (1,995 objects) | Step B scope (18,526 objects) | Ratio | Scaling exponent vs. n |
|---|---|---|---|---|
| Objects | 1,995 | 18,526 | 9.3x | - |
| KD-tree pairs within 485 km, per timestep (mean / max) | 3,273 / 3,875 | 162,656 / 165,015 | 49.7x | 1.75 |
| 1. Propagation | 1.60 s | 17.98 s | 11.3x | 1.09 |
| 2. Neighbor search (tree build + query) | 1.94 s | 34.70 s | 17.9x | 1.30 |
| 3a. Survivor closest-approach math | 1.12 s | 58.06 s | 51.7x | 1.77 |
| 3b. Event refinement (SGP4) | 0.11 s | 13.97 s | 122x | 2.15 |
| Screening total (2 + 3a + 3b) | 3.17 s | 106.93 s | 33.7x | - |
| Pipeline total | 4.92 s | 139.75 s | 28.4x | - |
| Peak RSS (`ru_maxrss`) | 362 MB | 2,214 MB (range 2,068-2,271) | 6.1x | - |
| Conjunctions (high / moderate / low) | 509 (0 / 31 / 478) | 63,896 (2,299 / 8,605 / 52,992) | - | - |
| Report file | ~1 MB | 76 MB (8.3 s to write) | - | - |

Peak memory is reached during propagation: position and velocity arrays of 641 MB each, plus a
transient filtered copy. During every Step B run, macOS swapped out about 1.5 GB of *other*
processes' memory. This process itself had only 30-364 major page faults, so the timings above
aren't distorted by its own paging, but 8 GB is already tight at this scale.

**Coarse-filter headroom** (`scripts/coarse_filter_headroom.py`, 49 sampled timesteps, validated
against all 63,896 real conjunctions):

| Altitude band definition | KD-tree pairs removed | Real conjunctions wrongly removed |
|---|---|---|
| Propagated radius range, widened by max radial speed x step/2 | **61.4%** | **0** (provably safe) |
| Mean-element perigee/apogee, pad 0 km (ADR 0003 as written) | 74.4% | 1,212 |
| Mean-element, pad 5 km | 68.1% | 304 |
| Mean-element, pad 10 km | 63.4% | 254 |
| Mean-element, pad 20 km | 49.4% | 127 |
| Mean-element, pad 30 km | 46.3% | 45 |

Why the element version fails: SGP4's actual radius sits outside the mean-element perigee/apogee
band by a median of 7.0 km (99th percentile 16.4 km). On top of that, 106 objects exceed it by
more than 30 km: highly elliptical deep-space orbits (MMS 1-4 by 383 km, XMM-Newton by 157 km),
fast-decaying objects, and one object with anomalous elements. No padding value is both safe and
worthwhile.

## Decision

1. **The coarse filter (Step C) is not required to reach full-catalog scale on time.**
   Extrapolating each phase at its measured exponent to about 30,000 objects (1.62x) gives roughly
   30 s propagation + 65 s search + 136 s survivor math + 39 s refinement + about 25 s report,
   **about 5 minutes per 24 h window** on this laptop. A pure n^2 assumption for survivor pairs
   gives about 5.2 minutes. That's comfortably within a batch job refreshed every 2 hours
   (CelesTrak's cadence). *This is an extrapolation, not a measurement. The ~11k objects beyond this scope are
   mostly debris and rocket bodies, less concentrated than Starlink's shells, so the
   pair-density exponent is more likely to fall than rise.*
2. **Memory, not screening time, is the binding constraint at full-catalog scale.** Peak RSS scales
   with propagation arrays, which are linear in n. About 30k objects implies roughly 3.5 GB peak
   before report assembly, which would be under heavy memory pressure on this 8 GB machine. The
   next scaling step, if full-catalog runs are wanted here, is **time-chunked propagation and
   screening**, not Step C. Streaming the report, or capping what it includes, belongs with it:
   76 MB already at 64k conjunctions.
3. **If Step C is built later, it must not be ADR 0003's mean-element band.** That design silently
   drops real conjunctions at every padding tested. Use the propagation-derived band (each object's
   actual radius range over the window, widened by its maximum radial speed x step/2). It's
   provably safe and removes 61% of survivor pairs, which would cut phase 3a (the largest phase)
   by about 60%. Its cost is that it needs propagation first, so it saves screening time, not
   propagation. It's a worthwhile optimization, not a prerequisite.

## Consequences

- ADR 0003's "coarse filter, then KD-tree" is superseded as a *requirement*. Its KD-tree half is
  done. Its coarse-filter half is optional, and if built it needs the band definition above.
  ADR 0003 has a pointer here.
- The first live `high`-tier conjunctions exist: 2,299 at this scope. 78.6% are Starlink vs.
  Starlink, and 96.5% involve at least one Starlink. The README's Known failures entry is updated.
  These come with a strong caveat: Starlink maneuvers often and TLE position error is about 1 km, so many sub-1 km "high" passes
  are within prediction noise. That is exactly ADR 0004's heuristic-not-Pc limitation, now
  visible at scale.
- The miss-distance distribution at this scope doesn't follow the random-crossing curve
  (proportional to d) that the debris-only scope matched. The 1-2 km bin has 4,861 against about
  7,667 expected. That's consistent with Starlink's coordinated phasing, though not proven. Geometry
  checks still pass: the linear estimate is within 9 m of refined SGP4, and speeds are physical.
- Timings come from a 2016 dual-core laptop. A cloud instance would be faster, and ADR 0005's
  deployment sizing should use the memory numbers above, not these wall-clock times.
- Reproduce with `uv run python scripts/scaling_spike.py`, followed by
  `uv run python scripts/coarse_filter_headroom.py`. The frozen snapshot lives in
  `cache/scaling-spike/` (gitignored, about 16 MB, deliberately not committed). Delete it to
  re-freeze.
