# ADR 0002: Use `sgp4` directly (SatrecArray) rather than `skyfield`

**Status:** Proposed (Cowork scoping session, 2026-09-27)

## Context

Two well-maintained Python options exist for SGP4 propagation from TLEs:

- **`sgp4`** (Brandon Rhodes, MIT license, PyPI `sgp4`, latest ~2.2x as of this writing): a focused
  SGP4/SDP4 implementation with an optional C++-accelerated backend, agreeing with the official
  reference implementation to within 0.1mm. Its `Satrec.twoline2rv` / `SatrecArray` API returns raw
  position/velocity in the TEME (True Equator Mean Equinox) frame.
- **`skyfield`** (also Brandon Rhodes): a higher-level astronomy toolkit that wraps `sgp4`
  internally and adds time-scale handling, coordinate-frame conversions (ECI/ECEF/topocentric),
  almanac calculations, and observer-relative geometry (altitude/azimuth, rise/set times).

## Decision

Use `sgp4` directly, via `SatrecArray` for vectorized propagation across many objects × many
timesteps at once, rather than `skyfield`.

**Reasoning:** conjunction screening is a *relative* calculation — the distance between two objects
propagated to the same instant. As long as every object is propagated into the same frame (TEME,
`sgp4`'s native output), no further frame conversion is needed; skyfield's coordinate-frame and
observer-geometry features solve a different problem (where is this satellite relative to a ground
observer or the Earth's surface) that this project doesn't have. Taking on `skyfield`'s extra
dependency weight and abstraction layer buys nothing here, and `SatrecArray`'s vectorized NumPy
interface is the more direct fit for propagating a large object catalog across many timesteps
efficiently — which matters once scope grows past the session-1 demo subset.

## Consequences

- If a later upgrade needs true geodetic (lat/lon/altitude) output — e.g. for a map-based dashboard
  view — a frame conversion (TEME → ECEF → geodetic) will need to be added explicitly; this is a
  well-documented, bounded piece of work (`sgp4`'s docs cover the TEME→ITRF conversion), not a
  reason to swap libraries.
- Pin to a current `sgp4` release (2.2x line) at implementation time and confirm the C-accelerated
  backend is actually active on Max's Intel Mac (the pure-Python fallback is slower and would
  understate real propagation performance during the session-1 timing spike).
