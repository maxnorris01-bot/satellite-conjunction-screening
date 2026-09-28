# Working notes and decisions log - Satellite Conjunction Screening Tool

This is a different kind of record from `docs/sessions/*.md`. Session docs narrate what changed in
one sitting and are written for someone with zero context picking up the diff. This file is the
opposite shape: short, durable entries - a decision plus *why*, or an open item worth remembering -
meant to be skimmed months later when the reasoning behind something has otherwise been forgotten.
Append to it whenever a real decision gets made, not just at the end of a session. If something is
already fully documented elsewhere (a technical fix in a session doc, a known failure in the
README, a design tradeoff in an ADR), point to it here rather than duplicating it.

## Decisions

**2026-09-27 - Report `schema_version` 1 -> 2 for a diagnostics-only change.** The KD-tree swap
replaced `summary.screening`'s `pair_checks`/`pairs_per_timestep` with
`all_pairs_per_timestep`/`neighbor_search`. No conjunction record changed, but any consumer
reading those keys would break silently, so any shape change to the report bumps the version, not
just record changes.

**2026-09-27 - KD-tree fine filter landed as a pure algorithmic swap, gated on exact parity.**
Session 2 Step A replaced the per-timestep all-pairs distance matrix with `cKDTree.query_pairs` at
the same 485 km radius. The closest-approach math, refinement, co-location and risk code are
unchanged. The acceptance bar was bit-identical output on a frozen input snapshot (the baseline's
cached CelesTrak responses plus its fixed 01:01Z window start), not "tests pass": a live re-run
uses a new window, so its counts legitimately differ. It passed: all 509 records are identical,
including the per-step pairs-within-radius total (4,716,128). Scope and timing numbers are in
`docs/sessions/2026-09-27-session-2a-kdtree-fine-filter.md`. Steps B (scaling spike) and C (coarse
filter) were deliberately deferred until these numbers were in.

**2026-09-27 - Default demo scope is `iridium-NEXT` + `fengyun-1c-debris`; `stations` and
Cosmos-1408 dropped.** Session 1's `stations` + `fengyun-1c-debris` scope never demonstrated
station-vs-debris screening. The stations (385-426 km) and Fengyun-1C debris (~800 km) are in
different altitude bands, so the stations group contributed only docked-vehicle pairs (0 km,
co-located, not risk-rated). Iridium NEXT (~780 km, all operational) shares the debris shell. Run
`20260928T0101Z-c6e1f2` found 52 debris-vs-Iridium passes under 5 km, 13 of them rated moderate,
which exercises the active-payload path on real data. Cosmos-1408 was never used as a source. It's
dropped from the spec as a suggestion because CelesTrak's `cosmos-1408-debris` group has decayed to
about 2 tracked objects, which no longer works as a debris-cloud example. Even with this scope, no
`high` conjunction has been observed yet; see the README's Known failures section.

**2026-09-27 - Risk-table thresholds (ADR 0004's heuristic, first numbers).** Values are in
`config/screening.yaml`; the rules are in `src/app/risk/risk_model.py`'s docstring.
- `high_miss_km: 1.0`. Fresh LEO TLE/SGP4 position error is roughly 1 km and grows with element
  age. A predicted miss under 1 km therefore can't be told apart from a hit using this data, and
  that's where "high" starts.
- `moderate_miss_km_active: 2.5`. That's half the screening threshold. It gives an active payload
  (something with an owner and maybe a thruster) extra margin that a debris-debris pass doesn't
  get.
- `hypervelocity_km_s: 1.0`. Above about 1 km/s any contact is energetic enough to be
  catastrophic. Below it, the encounter looks more like slow proximity drift than a crossing.
  Nearly all real crossings are far above this (median 13 km/s in session 1). The threshold only
  separates the rare slow case.
- A SATCAT-less object counts as possibly active. A screening tool should err toward surfacing a
  pass, not hiding it.
- Treat all of these as defensible starting points, not calibrated values. Nothing to calibrate
  against exists until a later session compares with Space-Track CDMs or SOCRATES.

**2026-09-27 - Between-sample detection and co-located pairs.** A sample-only
`distance < threshold` check at a 60 s step misses almost every real encounter. See
[ADR 0006](adr/adr-0006-between-sample-closest-approach-detection.md) for the padded-radius +
linear-TCA + SGP4-refinement design and the docked-vehicle "co-located" split.

**2026-09-27 - Elements come from CelesTrak's OMM JSON, not TLE lines.** The stations group
already has catalog numbers above 99999 (e.g. 100057 SOYUZ-MS 29). Those don't fit a TLE line
without Alpha-5 encoding. `sgp4.omm.initialize` builds a `Satrec` straight from the JSON fields,
and the mean-element content is identical. `CatalogObject.elements` keeps the raw OMM record rather
than line1/line2 as the spec sketched.

**2026-09-27 - Object type/status from CelesTrak SATCAT, not Space-Track.**
`celestrak.org/satcat/records.php?GROUP=<g>&FORMAT=JSON` gives `OBJECT_TYPE` (PAY/R/B/DEB/UNK) and
`OPS_STATUS_CODE` with no account, which is everything `assess_risk` needs. ADR 0001 planned to get
this from Space-Track. Space-Track is now only needed for a supplemental TLE feed or CDM
cross-validation, so it's off the MVP's critical path. "Active" means `PAY` with status `+`, `P`,
`B`, `S` or `X`.

**2026-09-27 - Drop elements older than 14 days before propagating.** 53 of 1,968 Fengyun-1C
fragments had epochs 15-27 days old. SGP4 error from elements that stale is far larger than a 5 km
threshold, so their "conjunctions" would be noise. They're dropped and listed in the report's
`scope.dropped`, not silently discarded. The value is `max_epoch_age_days` in config.

**2026-09-27 - Code lives under the template's `src/app/` package, not a renamed one.** The spec's
module sketch (`data/`, `propagation/`, `screening/`, `risk/`, `reporting/`) is mirrored as
subpackages of `app`. Renaming the package would touch the template's eval harness, tracing and
config imports for no functional gain in session 1. It's easy to do later if the name matters for
the portfolio.

**2026-09-27 - Screening config is `config/screening.yaml`, not `config/thresholds.yaml`.** The spec
suggested `thresholds.yaml`, but `evals/thresholds.yaml` already means "eval pass/fail gates" in
this template, and two different files with the same name invite confusion.

## Open items / parking lot

- **No live `high`-tier example yet.** High-tier risk logic is verified only by unit tests. It's
  documented in the README's Known failures section; record the first real example there when one
  appears.
- **One-off 560 s first run, unreproduced.** The very first `python -m app.cli` run (2026-09-27)
  took 560 s wall-clock. The pipeline's own spans totaled 28 s and user CPU was about 25 s, so the
  process sat idle for the rest. Every run since has taken about 24-26 s, which is pipeline time
  plus about 2.5 s of imports. Unconfirmed suspects: the first `uv run` after a `pyproject.toml`
  change (environment re-sync/rebuild), or macOS scanning freshly built native libraries on first
  load. Watch for it on the next cold start or fresh clone. If it recurs, time `uv run python -c
  pass` separately from the pipeline to split environment setup from the run itself.
- **Memory, not just time, blocks full-catalog scale.** All-pairs index arrays at 30k objects would
  be about 7 GB. 24 h x 60 s position + velocity arrays would be about 2 GB. ADR 0003's KD-tree
  fixed the first in session 2 Step A: no O(n^2) arrays remain. The second still needs
  time-chunked propagation. Numbers are in the session-1 summary.
- **Co-located detection uses relative speed only.** A slow drift toward collision would be
  classified co-located and never rated. See ADR 0006's consequences.
- **ADR 0001 still says SATCAT metadata comes from Space-Track.** Worth a one-line status note on
  that ADR, since CelesTrak's SATCAT now covers it (see the decision above).

## See also

- `docs/sessions/*.md` - what changed and why, per work session.
- `README.md`'s Known Failures section (if present) - the detailed, evidence-quoted record of real
  bugs found and their status.
- `docs/adr/` - specific architectural decisions with fuller reasoning than fits here.
