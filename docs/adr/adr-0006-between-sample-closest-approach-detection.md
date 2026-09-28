# ADR 0006: Detect closest approaches between samples (padded search radius + linear TCA + SGP4 refinement)

**Status:** Accepted (session 1, 2026-09-27)

## Context

The spec's session-1 plan propagates at a 60 s step and flags pairs "whose separation drops below
`threshold_km` at any timestep." Taken literally, that check is almost blind: LEO closing speeds
are typically 10-15 km/s (median 13.2 km/s across the 460 real encounters found in session 1), so
two objects move 600-900 km relative to each other between samples. A 5 km pass lands exactly on a
sample only by luck. Shrinking the step until a sample-only check works would need a ~0.3 s step,
200x more propagation and screening work.

## Options considered

1. **Sample-only check at a fine step (~0.3 s).** Simple and correct, but 200x the compute and
   memory. Not viable past a toy scope.
2. **Coarse step + interpolation of every pair's trajectory (e.g. cubic Hermite on position and
   velocity).** Accurate, but applied to every pair it's expensive, and most pairs are hundreds of
   km apart.
3. **Coarse step + padded search radius + linear closest approach + SGP4 refinement.** At each
   sample, keep only pairs within `threshold + v_max * step / 2`. That is the farthest apart two
   objects can be at a sample and still come within the threshold in the half-step either side.
   For those pairs, solve for the closest approach assuming straight-line relative motion over
   +/-step/2. Refine each candidate by re-propagating just that pair with SGP4 and minimizing true
   separation.

## Decision

Option 3. Relative acceleration between two nearby objects is tiny (tidal-scale), so straight-line
relative motion over +/-30 s is very accurate. In session 1 the linear estimate differed from the
SGP4-refined miss distance by at most 9 m (median 0.3 m) across 460 encounters, and refinement
never pushed a candidate back over the threshold. Each sample "owns" the half-step either side of
it, clipped at the window edges, so the samples tile the window with no gaps and no double
coverage. A pair's hits on consecutive samples are one encounter; hits separated by a gap are
separate encounters.

Pairs whose relative speed never exceeds `co_located_max_relative_speed_km_s` (0.1 km/s) are split
out as **co-located** and not risk-rated. CelesTrak publishes the host station's elements for
docked vehicles and station modules (0.0 km separation, identical elements), so without this every
docked Soyuz/Progress/Dragon would be reported as a zero-miss "conjunction" with the ISS.

## Consequences

- The search radius (485 km at a 60 s step) is the dominant term in the candidate count, and it
  scales with step size. ADR 0003's KD-tree fine filter queries at this radius, so a smaller step
  shrinks the neighbor sets the tree returns. The KD-tree work should measure that tradeoff,
  not assume 60 s.
- `max_relative_speed_km_s` (16 km/s) is a safety bound, not a tuning knob. Lowering it risks
  silently missing head-on encounters.
- Co-location by relative speed alone would also swallow a genuinely dangerous slow drift toward
  another object (rare, but it's what a rendezvous or a failed proximity operation looks like).
  That's acceptable for the MVP. A later refinement could flag co-located pairs whose separation
  trends toward zero.
