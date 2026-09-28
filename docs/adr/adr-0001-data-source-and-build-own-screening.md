# ADR 0001: CelesTrak as primary data source; build our own screening pipeline rather than consuming Space-Track's CDM feed

**Status:** Proposed (Cowork scoping session, 2026-09-27)

## Context

Two candidate public data sources exist for this project:

- **CelesTrak**: free, no-account GP/TLE data, refreshed ~every 2 hours, generous formats (JSON,
  CSV, XML/OMM). No approval process, usable immediately.
- **Space-Track.org**: the authoritative U.S. government source, requires a registered, approved
  account (email/password; approval timing unspecified, "must be renewed periodically"), strict
  rate limits (30/min, 300/hour; GP-class TLE queries limited to once/hour by policy), and — notably
  — **already publishes CDM (Conjunction Data Message) data**: CSpOC's own pre-computed close-approach
  warnings, 3x daily.

Since Space-Track already does conjunction screening and publishes the results, there's a real
question of whether this project should just consume that feed instead of building a screening
pipeline from TLEs.

## Decision

- **Primary TLE/GP source: CelesTrak.** No approval bottleneck, sufficient refresh cadence, and the
  named object-groups (stations, debris clouds) are convenient for a scoped demo.
- **Supplemental source: Space-Track**, for metadata (SATCAT object type/status) and as a secondary
  TLE source, once approved — not as the primary feed, given its stricter access/rate constraints.
- **Do not consume Space-Track's CDM feed as a shortcut.** The entire point of this portfolio
  project is to demonstrate the fetch → propagate → screen → assess pipeline as original engineering
  work. Pulling pre-computed CDMs would reduce the project to a data-display wrapper around someone
  else's screening output, undermining the "data analytics / pipeline engineering" skills this MVP
  tier exists to demonstrate (per `Applied_AI_Portfolio_Plan.md`'s "why this shape" rationale).

## Consequences

- We accept the engineering cost of writing our own SGP4 propagation and screening logic (see ADR
  0002 and ADR 0003) rather than reusing CSpOC's more authoritative, covariance-aware conjunction
  assessments.
- Our risk levels are necessarily cruder than CSpOC's real Pc-based CDMs (see ADR 0004) — this is an
  acceptable, explicitly documented limitation for a portfolio MVP, not a claim of operational-grade
  accuracy.
- Space-Track account registration should start on day 1 of implementation (approval timing is
  unknown) even though session 1's spike doesn't depend on it.
