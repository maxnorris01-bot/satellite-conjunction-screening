# Working notes and decisions log - Satellite Conjunction Screening Tool

This is a different kind of record from `docs/sessions/*.md`. Session docs narrate what changed in
one sitting and are written for someone with zero context picking up the diff. This file is the
opposite shape: short, durable entries - a decision plus *why*, or an open item worth remembering -
meant to be skimmed months later when the reasoning behind something has otherwise been forgotten.
Append to it whenever a real decision gets made, not just at the end of a session. If something is
already fully documented elsewhere (a technical fix in a session doc, a known failure in the
README, a design tradeoff in an ADR), point to it here rather than duplicating it.

## Decisions

**2026-10-02 - Foundation-gate item scoped: objects/current.json, a Vercel API function, and a move
to full-catalog scope.** Full reasoning: [ADR 0010](adr/adr-0010-portfolio-api-and-full-catalog-scope.md).
Short version: the report alone doesn't carry full-catalog TLEs, so a new flat `objects/current.json`
artifact (every screened object, propagation-ready) is the real foundation the 2026-09-30 vision
needs — not the report's history, which only matters for the MVP's own trend widget. API shape is a
single Vercel function in `portfolio-site` (`GET /api/satellite/current`), not bucket CORS or a
standalone service. A fifth future feature came up during scoping — select a near-miss, jump the
globe to its TCA, focus on the two objects — and needs no new data beyond the above. Catalog scope
is also expanding to the full tracked catalog (Max's call); the Fly machine's memory needs a fresh
measurement at that real scale before being sized, not an extrapolation from ADR 0007's number.

**2026-10-01 - SATCAT owner added as `satcat_owner`; operator deferred to a GCAT join.** CelesTrak's
SATCAT has one ownership field, `OWNER` ("source or ownership"), and no operator field. Its 132
codes mix states (`US`, `PRC`, `CIS`), international bodies (`ESA`) and a few companies (`IRID`,
`SES`), with none for SpaceX, Starlink or OneWeb. In practice it's mostly the registering state:
all 80 Iridium NEXT satellites are `US`, not `IRID`. Max chose:
- **`satcat_owner`, not `owner`,** so nobody reads it as the operator.
- **A readable `name` from a vendored code table** (`config/satcat_owners.yaml`, regenerated
  deliberately by `scripts/build_satcat_owners.py`). CelesTrak's code list is HTML-only, so it
  isn't scraped at runtime.
- **Operator deferred** to its own to-do item (a GCAT join, with its own ADR). Name-prefix
  guessing (`STARLINK-*` -> SpaceX) was rejected because it's silently wrong for anything
  unlisted.

The field is additive, so `schema_version` stays 3 under the 2026-09-28 rule. It also extends the
2026-09-27 "object type/status from CelesTrak SATCAT" join below, with no new fetches.

**2026-10-01 - Daily run: Fly.io scheduled Machine -> public Tigris bucket, report + raw snapshot,
no history.** Cowork picked Fly.io over Lambda and no retention window (reasoning in
`docs/todo.md`'s item). This session settled the rest. A scheduled Machine (`--schedule daily`,
`--restart no`, 1 GB, `sjc`) runs `app.publish`, which overwrites `reports/current.json` and
`snapshots/current/*.json.gz` in a Tigris bucket. Not a volume, because a volume is readable only
by the one Machine it's attached to. Max chose a **public** bucket, so `portfolio-site` can fetch
the report directly today, and chose to **publish the raw CelesTrak snapshot** alongside it, so
any published report is reproducible. A dry run confirmed that re-screening from the published
snapshot reproduces the report exactly. Full reasoning:
[ADR 0009](adr/adr-0009-daily-run-on-fly-scheduled-machine.md).

**2026-09-29 - Eval harness replaced: oracle-checked synthetic scenarios plus named real-data
encounters.** The template's harness scored an echo placeholder, so every `make eval-fast` pass so
far measured nothing. Max picked this design over "named encounters on the snapshot only" (no
independent correctness check, overlaps the parity test) and "an oracle recall metric on real data"
(slow, and no control over which edge cases occur). Nine engineered scenarios run the real pipeline
and must match a brute-force 1 s SGP4 oracle exactly. Three more cases pin human-checked facts on
the frozen default-scope snapshot. Max also picked removing the placeholder (`app.pipeline`, the
example case/rubric, `known-unstable/`) while keeping `app.llm`, `app.mock_llm` and `prompts/` as
dormant template infrastructure. `min_pass_rate` went 0.90 -> 1.0 because the pipeline is
deterministic. Full reasoning: [ADR 0008](adr/adr-0008-screening-evals-oracle-and-named-cases.md).
Case format and the mutation check that proves the cases can fail: `evals/README.md`.

**2026-09-30 - Longer-term vision locked in (daily history, 3D tracking globe, owner/operator
filtering, location-based sky view, satellite POV); MVP stays the screening pipeline plus only the
foundation that vision needs.** Cowork scoping sketched a follow-on product direction: scheduled
daily fetches with retained history and forward propagation ("where will this be tomorrow" is
already free - it's just `propagate_orbits` with tomorrow's window), a 3D globe showing all tracked
objects, filtering by owner/operator (SpaceX, USA, etc.), a browser-geolocation sky view with
per-satellite visibility/pass predictions, and a camera view from a selected satellite looking back
at Earth. None of this needs an LLM call, so it's still consistent with the MVP tier's zero-AI-cost
framing - but it's a real scope expansion beyond a batch screening tool, closer to its own flagship
project than a quick MVP entry, so it's being tracked as a deliberate decision rather than drifted
into.

Decision: finish the collision-tracker polish already on the to-do list (eval harness, dashboard,
README), and build only the foundation every one of those future features would need regardless of
which get built: (1) scheduled daily fetch+screen runs with report and snapshot storage plus a
retention window (this is ADR 0005's deployment decision, now with concrete purpose - see ADR 0005
update), (2) SATCAT owner/operator metadata joined onto each tracked object, (3) a small API layer
serving the current report and recent history, replacing the static-file approach (this is also the
seam `portfolio-site`'s satellite tab would eventually read from instead of its hardcoded data
file - see that repo's `Portfolio_Site_Plan.md`). The 3D globe, sky view, and satellite-POV camera
are explicitly NOT being built yet.

Gate: once the foundation is in place - especially the API/deployment piece, the one item here with
real effort behind it - re-assess. If extending toward the visualization vision looks easy from
there, keep going. If it's a significant lift, close this project out at that point and move to
City Livability Scoring Tool's MVP instead, per the roadmap's tiering discipline. This mirrors
`Engineering_Standards.md`'s "validate before building out scope" lesson from Claim Verification
Agent.

This also resolves ADR 0007's open question: Step C (the coarse filter) and full-catalog scale are
**not being pursued for now** - see that ADR's status update.

**2026-09-28 - Schema-version rule changed: bump only on breaking changes.** From now on,
`REPORT_SCHEMA_VERSION` is bumped only when an existing report field is **renamed, removed, or has
its meaning changed**. Purely additive new fields don't bump it: a consumer that ignores unknown
keys keeps working, and bumping for every new diagnostic would make the version number noise. This
replaces the stricter "any shape change bumps" rule from the v2 entry below. The current version
stays at **3**; v3 was bumped under the old rule and isn't being rolled back. The rule is also
stated in `src/app/reporting/report_builder.py`'s docstring.

**2026-09-28 - Step B conclusion: coarse filter not required; memory is the next constraint.** At
18,526 objects the KD-tree pipeline takes about 140 s per 24 h window. Extrapolated to about 30k
objects it's roughly 5 minutes, which fits a 2-hourly batch job. Peak memory (2.2 GB, set by
propagation arrays) is the actual limit on an 8 GB machine. ADR 0003's mean-element coarse filter
turned out unsafe: it drops real conjunctions even at 30 km padding. A propagation-derived band is
safe and would remove 61% of survivor pairs. Full reasoning and numbers:
[ADR 0007](adr/adr-0007-coarse-filter-not-required-for-full-catalog.md). Step C is not
implemented, pending Cowork review.

**2026-09-28 - Report `schema_version` 2 -> 3 for additive diagnostics keys.** Step B added
`phase_timings_s`, pairs-per-timestep density and `refined_events` to `summary.screening`. This
follows the rule from the v2 entry below ("any report shape change bumps the version"), even
though nothing was removed or renamed. (Superseded going forward by the rule change above;
additive keys no longer bump.)

**2026-09-27 - Parity regression test committed as a re-runnable gate for Steps B and C.** The
frozen CelesTrak snapshot and baseline comparison from the Step A parity check now live in
`tests/regression/`. Re-run it with:

```bash
uv run pytest tests/regression -v
```

It also runs as part of `make test`, which picks up everything under `tests/`, so no Makefile
change was needed. It's served entirely from the snapshot; any network request fails the test.
It asserts exact counts and pairs, and tight numeric tolerances only to absorb cross-platform float
noise. The baseline is regenerated only deliberately, in its own commit. Details:
`tests/regression/README.md`.

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

- **First live `high` at the default scope: 2026-10-01 (resolved as an open item).** Run
  `20261001T0222Z-f4a843` flagged IRIDIUM 105 vs. Fengyun-1C fragment 30413 at 0.57 km, 11.8 km/s.
  Recorded in the README's Known failures. A `high` still appears only in some windows, so the
  synthetic `high-tier-hypervelocity` eval case remains the guaranteed check of that tier.
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

- **Synthetic scenarios cover one shell only.** All nine are circular orbits at 780 km. Eccentric
  orbits, mixed-altitude crossings and GEO aren't exercised. See ADR 0008's consequences.

## See also

- `docs/sessions/*.md` - what changed and why, per work session.
- `README.md`'s Known Failures section (if present) - the detailed, evidence-quoted record of real
  bugs found and their status.
- `docs/adr/` - specific architectural decisions with fuller reasoning than fits here.
