# ADR 0003: Coarse orbital-regime filter + per-timestep KD-tree, not naive all-pairs, for full-catalog screening

**Status:** Proposed (Cowork scoping session, 2026-09-27) — implementation deferred past session 1
(see spec's first-session plan); this ADR documents the design decision now so it isn't
rediscovered mid-implementation.

## Context

`screen_conjunctions` needs to find, across a time window, every pair of tracked objects that comes
within a distance threshold of each other. The publicly tracked catalog is ~30,000+ objects. A naive
all-pairs distance check at every timestep is O(n²) per timestep — roughly 450 million pair-checks
per timestep at full catalog scale — which does not scale, even though it's perfectly fine for
session 1's small demo subset (~200-300 objects).

This is a well-studied problem in the actual conjunction-assessment literature: operational systems
use cheap coarse pre-filters (e.g. apogee/perigee altitude-band overlap, orbital-plane geometry) to
eliminate most pairs before any expensive fine-grained distance computation.

## Decision

Two-stage screening once scope grows past the session-1 demo subset:

1. **Coarse filter**: eliminate pairs whose orbital regimes can't possibly come close — e.g. an
   apogee/perigee altitude-band overlap check (if object A's orbit never reaches the altitude range
   object B occupies, skip the pair entirely). This is a cheap, one-time-per-run filter on TLE-derived
   orbital elements, done before any propagation-heavy work.
2. **Fine filter**: for the much smaller surviving candidate set, propagate and, at each timestep,
   use `scipy.spatial.cKDTree` (build a tree of all positions at that timestep, query each object's
   neighbors within the threshold radius) rather than a manual all-pairs loop — this turns
   near-neighbor lookup from O(n²) into roughly O(n log n) per timestep.

## Consequences

- Session 1 intentionally ships the naive all-pairs version first (correct, simple, sufficient at
  small scale) to validate the pipeline's interfaces and real data end-to-end without also debugging
  a spatial-indexing algorithm in the same session. The coarse+KD-tree version is a session-2+
  optimization with the same function signature — swapping the implementation shouldn't require
  touching callers.
- The coarse filter's altitude-band threshold is a tunable parameter (config, not hardcoded) and
  should itself get a small validation check (does it ever wrongly eliminate a pair that the naive
  version would have flagged, on the session-1 demo subset, before trusting it at scale).
- This is exactly the kind of design decision `Engineering_Standards.md` wants captured as an ADR
  before it's built, rather than discovered as a scaling surprise later.
