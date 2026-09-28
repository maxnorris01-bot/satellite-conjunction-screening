# Satellite Conjunction Screening Tool — Spec (MVP)

*Drafted in Cowork, 2026-09-27. Scoping/design only — implementation happens in Claude Code per
`Chat_Instructions.md`. Source: `Applied_AI_Portfolio_Plan.md` (2026-09-27 roadmap), MVP tier
project #2.*

## Purpose and boundary

Continuously ingests public satellite tracking data and screens the tracked catalog (or a scoped
subset of it) for close approaches between object pairs, producing a structured risk report. This
is project #2 in the MVP tier: **the entire core pipeline described below must make zero LLM/AI
calls.** The `generate_summary` LLM step and any alerting (`queue_for_review`, `send_alert`) are a
later, separately-evaluated upgrade and are out of scope for this spec.

**Users:** a hiring manager reviewing the portfolio; secondarily, Max as a demo/reference tool.
**Inputs:** public TLE/GP catalog data (CelesTrak primary, Space-Track supplemental — see ADR 0001),
a distance threshold, a scope (catalog subset or full catalog), a propagation time window.
**Outputs:** a structured JSON report of flagged close-approach pairs with risk levels; optionally a
simple dashboard view over that JSON.
**Out of scope (MVP):** LLM-generated summaries, alerting/notification, true probability-of-collision
(Pc) computation from covariance (TLEs don't carry covariance — see ADR 0004), real-time streaming
ingestion (a scheduled batch run is sufficient).
**Data provenance:** CelesTrak GP data (public, no auth) and, once approved, Space-Track GP/SATCAT
data (public, registered-account auth) — both are the same class of publicly-published tracking data
operators already use; no proprietary or restricted data involved.

## Core pipeline (per `Applied_AI_Portfolio_Plan.md`, zero LLM calls)

```
fetch_tle_data(catalog / satellite_ids)
        -> propagate_orbits(tle_set, time_window, step)
                -> screen_conjunctions(positions, threshold_km)
                        -> assess_risk(candidate)
                                -> structured report
```

### `fetch_tle_data(catalog | satellite_ids, source="celestrak")`

Pulls current GP/TLE data for a named group or explicit catalog-number list.

- **Primary source: CelesTrak.** No account, no auth, GP data refreshed roughly every 2 hours.
  `https://celestrak.org/NORAD/elements/gp.php?GROUP=<name>&FORMAT=JSON` (or `CATNR=`, `NAME=`,
  `INTDES=`). Fair-use rule: don't poll more often than the ~2h refresh cadence; cache the raw
  response with a timestamp and reuse it within that window.
- **Supplemental source: Space-Track**, once the account is approved (start registration on day 1 —
  approval isn't instant). Used for anything CelesTrak's GP feed doesn't cover well (e.g. SATCAT
  object-type/status metadata for the "active satellite vs. debris" input to `assess_risk`), not as
  the primary TLE feed. Auth: registered account (email/password) via the `spacetrack` Python
  library's `SpaceTrackClient`. Hard rate limits: 30 req/min, 300 req/hour; GP-class TLE queries are
  additionally restricted to once per hour by policy. The `spacetrack` library self-throttles to
  these limits but only within one process — never run two scripts against the same account
  concurrently.
- Returns a normalized in-memory `TleSet` (catalog number, epoch, line1/line2, source, fetch
  timestamp) regardless of which source supplied it.
- See ADR 0001 for why we do *not* pull Space-Track's own CDM (pre-computed conjunction) feed
  instead of building this pipeline ourselves.

### `propagate_orbits(tle_set, time_window, step)`

SGP4-propagates every object in `tle_set` across `time_window` at `step` cadence, in the TEME frame
(no need to convert to ECI/ECEF — see ADR 0002 — since conjunction distance is a relative
calculation between objects propagated into the same frame at the same instant).

- Library: `sgp4` (Brandon Rhodes' package), using `SatrecArray` for vectorized propagation across
  many objects at many timestamps at once. See ADR 0002 for why `sgp4` directly rather than
  `skyfield`.
- Output: a `(n_objects, n_timesteps, 3)` position array (km) plus a matching velocity array, indexed
  consistently with `tle_set`.
- Malformed/decayed elements (SGP4 error codes) are logged and the object is dropped from that run's
  screening rather than crashing the batch.

### `screen_conjunctions(positions, threshold_km)`

Finds object pairs whose separation drops below `threshold_km` at any timestep in the window.

- **Not** naive all-pairs distance at every timestep — see ADR 0003 for the coarse-filter (orbital
  regime / altitude band) + fine-filter (`scipy.spatial.cKDTree` per timestep) design, which is
  necessary once scope grows beyond a small demo subset (the full public catalog is ~30k+ tracked
  objects; naive all-pairs is ~450M pair-checks per timestep).
- Output: a list of `(object_a, object_b, timestep, distance_km, relative_velocity_km_s)` candidates.

### `assess_risk(candidate)`

Combines miss distance, closing (relative) velocity, and object type (active satellite vs. debris,
from SATCAT/GP metadata) into a categorical risk level (e.g. `low` / `moderate` / `high`).

- MVP is a documented heuristic/threshold table, not a true probability-of-collision (Pc) estimate —
  Pc requires state covariance, which plain TLEs don't carry. See ADR 0004.
- Output feeds directly into the structured report; this is also the seam where the later
  `generate_summary` LLM upgrade attaches (per the plan doc), so its output shape should be a clean,
  stable schema now even though nothing consumes it yet.

### Structured report

JSON (and/or a lightweight table/dashboard view over it): one record per flagged pair — objects
involved, object types, closest-approach time, miss distance, relative velocity, risk level, source
TLE epochs used. This is the MVP's entire user-facing output.

## Module architecture (rough)

```
satellite_conjunction_screening/
  data/
    celestrak_client.py     # fetch_tle_data() primary path
    spacetrack_client.py    # fetch_tle_data() supplemental path + SATCAT metadata
    tle_cache.py            # on-disk cache respecting source refresh cadence
  propagation/
    sgp4_propagator.py      # propagate_orbits()
  screening/
    coarse_filter.py        # orbital-regime/altitude-band pre-filter
    conjunction_screen.py   # screen_conjunctions() fine filter (cKDTree)
  risk/
    risk_model.py           # assess_risk() heuristic + thresholds table
  reporting/
    report_builder.py       # structured JSON/report assembly
  tracing.py                # structured JSON step logging (from template)
  cli.py / run.py           # entry point: catalog scope, threshold, window as args/config
config/
  thresholds.yaml           # distance threshold, risk bands, time window, step size
tests/
docs/
  spec-satellite-conjunction-screening.md   # this file
  adr/
  working-notes-and-decisions.md
  todo.md
  sessions/
```

Config (thresholds, scope, window, step) lives in `config/`, not hardcoded, per
`Engineering_Standards.md`'s prompts-and-config convention generalized to a non-LLM pipeline.

## First-session implementation plan (small, cheap, validates the real pattern)

Per `Engineering_Standards.md`'s performance-spike lesson (Claim Verification built its full
pipeline before checking cost/latency economics): this pipeline has no per-call API cost to
de-risk, but it has an equivalent risk — **whether the real fetch → propagate → screen chain works
end-to-end against real public data, and whether the screening approach's compute cost stays
reasonable, before committing to full-catalog scope.** Session 1 should spike that on a small,
real, deliberately-chosen scope, not a simplified stand-in.

**Scope for session 1:** two small CelesTrak groups known to have genuine close-approach signal —
`GROUP=stations` (ISS, Tiangong, etc., ~10-20 objects) and the Fengyun-1C fragmentation debris
cloud (`GROUP=fengyun-1c-debris`, ~2,000 tracked fragments) — small enough that a naive all-pairs
distance check is fine for now, real enough to produce actual flagged conjunctions rather than a
synthetic fixture.

> **Updated after session 1 (2026-09-27):** the default demo scope is now `iridium-NEXT` +
> `fengyun-1c-debris`. The stations (385-426 km) never meet Fengyun-1C debris (~800 km), so
> `stations` produced only docked-vehicle (co-located, not risk-rated) pairs. Iridium NEXT shares
> the debris cloud's altitude shell and produces real active-payload-vs-debris encounters. See
> `docs/working-notes-and-decisions.md`.

1. Repo scaffold from `portfolio-project-template` (Max, terminal — commands below).
2. `fetch_tle_data`: real CelesTrak GET for the two groups above, parsed into `TleSet`. Success
   check: object count matches CelesTrak's listing, no parse failures.
3. `propagate_orbits`: SGP4-propagate that small set across a 24-48h window at a 60s step. Success
   check: runs without SGP4 error codes on active elements; record wall-clock runtime — this is the
   number that tells us whether the coarse/fine filter design in ADR 0003 is needed *now* or can
   wait, once scope grows.
4. `screen_conjunctions`: naive all-pairs distance for this small set (defer the coarse+KD-tree
   design's implementation to session 2, once the naive version proves the interface); threshold
   e.g. 5 km. Success check: finds at least one real close approach in the debris group (expected,
   given known debris-cloud density) — a sanity check that the geometry/units are right, not a
   fabricated pass condition.
5. `assess_risk`: stub heuristic (ADR 0004's threshold table) applied to whatever
   `screen_conjunctions` finds.
6. Structured JSON report written to disk; eyeball it for shape/correctness.
7. Structured JSON step logging (fetch/propagate/screen/assess durations + counts) from the first
   prototype, per the template's `tracing.py` convention — this is what makes a later
   full-catalog performance investigation possible at all.
8. In parallel (not blocking the above): start the Space-Track account registration — approval
   timing is unknown, so kicking it off day 1 means it's ready by the time the project needs SATCAT
   metadata or a supplemental feed.

**Explicitly deferred to session 2+:** the coarse-filter + KD-tree screening implementation at
full/larger-catalog scale, containerization and scheduled deployment (Docker/Lambda/EventBridge or
Fly.io cron — see ADR 0005), CI and eval-style regression tests, the dashboard view, README.

**Definition of done for session 1:** the four pipeline functions run end-to-end on the small real
scope above, produce a structured report containing at least one genuine flagged conjunction, log
step timings, and the session ends with a session summary per `Engineering_Standards.md`'s
CLAUDE.md standard (what changed, decisions made, timing numbers observed, open questions, next
command to run).

## Open questions for session 1 (Claude Code should surface answers in its session summary)

- Actual SGP4 propagation wall-clock time for ~200-300 objects × 24-48h × 60s steps — this decides
  how urgently ADR 0003's coarse/fine filter needs implementing before scaling to the full catalog.
- Whether CelesTrak's named debris-cloud groups are large enough (and current enough) to reliably
  produce a real sub-threshold conjunction in a 24-48h window, or whether the threshold/window needs
  adjusting.
