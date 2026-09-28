# ADR 0004: MVP risk level is a documented heuristic, not a true probability-of-collision (Pc)

**Status:** Proposed (Cowork scoping session, 2026-09-27)

## Context

Real operational conjunction assessment computes a probability of collision (Pc) from each object's
full state covariance (position/velocity uncertainty ellipsoid) combined with miss distance and
relative geometry. Plain TLEs do not carry covariance data — SGP4 propagation from a bare TLE gives a
best-estimate position/velocity only, with no uncertainty bound attached. Real covariance data (as
used in actual CDMs) comes from higher-fidelity tracking sources CSpOC has and this project doesn't.

## Decision

`assess_risk` in the MVP combines miss distance, relative (closing) velocity, and object type
(active satellite vs. debris, from SATCAT/GP metadata) into a categorical risk level via a documented
threshold table (e.g. sub-1km + high closing velocity + at least one active satellite → `high`;
wider miss distance or debris-debris → `low`/`moderate`) — not a numerical Pc.

This is stated explicitly and prominently (README "project boundary" section, per
`Engineering_Standards.md`'s README standard) as a known limitation, not glossed over: this tool
screens and categorizes candidate close approaches from public TLE data; it does not replace or
match CSpOC's operational Pc-based conjunction assessments.

## Consequences

- The risk heuristic's thresholds are config, not hardcoded, and should be documented with their
  reasoning in `docs/working-notes-and-decisions.md` so they're defensible in an interview
  conversation ("why did you pick 1km / X km/s") rather than looking arbitrary.
- If a later upgrade wants a real Pc estimate, that requires either sourcing covariance data
  separately (e.g. from Space-Track's own CDM feed for cross-validation — see ADR 0001's boundary
  on not just consuming that feed wholesale, but nothing stops using it as a validation/comparison
  set) or a documented simplifying assumption (e.g. an assumed fixed covariance) — that's a
  deliberate future ADR of its own, not an MVP concern.
