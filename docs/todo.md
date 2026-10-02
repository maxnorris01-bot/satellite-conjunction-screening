# To-do - Satellite Conjunction Screening Tool

A running checklist, not a narrative. Check items off as they're done and add a short note (what
happened, any surprises) rather than deleting the line - that note is often more useful later than
the checkmark itself. Add new items as they come up; don't wait for a session's end. This is
*not* where decisions and reasoning go - that's `docs/working-notes-and-decisions.md`. This is just
"what's next."

## Up next (in priority order)

*Phase per the 2026-09-30 decision in `docs/working-notes-and-decisions.md`: finish collision-tracker
polish, then build only the foundation a possible later visualization product would need. Full
scope (3D globe, owner/operator filtering, sky view, satellite POV) is intentionally NOT on this
list yet - see that decision entry.*

- [ ] Foundation-gate item, remainder (ADR 0010 and its amendment). This repo's side is done
      (see Completed, 2026-10-02). Still open:
      - Enable CORS on the public bucket for `reports/current.json` and `objects/current.json`
        only (the amendment's direct-fetch decision).
      - In `portfolio-site`: a small Vercel `GET /api/satellite/summary` (risk counts, top-N near
        misses) under the ~4.5 MB response cap, then `/history` as the lower-priority add-on.
      If this turns out easy, the visualization vision stays realistic; if it's a significant lift,
      bank what's built and move to City Livability Scoring Tool's MVP instead.

## Later

- [ ] Space-Track full GP catalog as the source for true full-catalog scope (ADR 0010 amendment,
      option (b)). Needs its own ADR: new primary source, credentials as Fly secrets, rate limits,
      and a revision to ADR 0001.

- [ ] Operator join from GCAT (Jonathan McDowell's catalog: `Owner` = owner/operator org code,
      `State` = country) onto each object, for "filter by operator" (e.g. SpaceX). SATCAT can't
      supply it (see the 2026-10-01 working-notes entry). Needs its own ADR: source reliability
      (one maintainer), GCAT-to-NORAD id mapping, license, and how often the daily run refreshes
      a large TSV.

- [ ] Add a status note to ADR 0001: SATCAT metadata now comes from CelesTrak.
- [ ] **Deferred pending the foundation gate above:** 3D globe of all tracked objects (client-side
      SGP4 via `satellite.js`, fed by the API layer), owner/operator filtering UI, browser-geolocation
      sky view with per-satellite visibility/pass predictions, and a satellite-POV camera view. See
      the 2026-09-30 working-notes entry for the full vision and sequencing.

## Lower priority / opportunistic

- [ ] Delete the stale `snapshots/current/{gp,satcat}-iridium-NEXT.json.gz` from the bucket (left
      over from the MVP scope; the manifest doesn't list them, see ADR 0010).

- [ ] Add eval scenarios beyond the single 780 km circular shell: eccentric orbits, mixed-altitude
      crossings (ADR 0008's consequences).

- [ ] Flag co-located pairs whose separation trends toward zero (see ADR 0006's consequences).
- [ ] Cross-check a few flagged encounters against CelesTrak SOCRATES for the same window, as a
      correctness spot-check.
- [ ] Investigate the one-off 560 s wall-clock on the first-ever run (the pipeline itself took
      28 s). Not reproduced since; details in the working notes' open items.

## Completed (most recent first)
- [x] 2026-10-02 - Full-catalog scope plus `objects/current.json`, deployed (ADR 0010):
      - Scope is now CelesTrak's `active` plus all three debris groups, 19,240 objects screened.
      - Measured locally at 2.87 GB peak and 35 s on the M5. The Machine was resized to
        shared-cpu-4x with 8 GB.
      - On Fly: 2,804 MB peak, 109.6 s pipeline, about $0.0035 per run.
      - Report, objects (served with `Content-Encoding: gzip`) and snapshot all verified live with
        the same run id.
      - Surprise: the first `fly machine update` hit `MANIFEST_UNKNOWN` right after the push (an
        immediate retry worked), and the update doesn't start a stopped Machine.
      See `docs/sessions/2026-10-02-full-catalog-objects.md`.
- [x] 2026-10-01 - SATCAT owner joined onto each tracked object as `satcat_owner` ({code, name})
      in every report object record, with names from a vendored 132-code table
      (`config/satcat_owners.yaml`). Additive, so `schema_version` stays 3. Surprise: SATCAT has no
      operator field and its OWNER is mostly the registering state (Iridium NEXT is "US", not
      "IRID"; there is no SpaceX code), so the operator join was split out below. See
      `docs/sessions/2026-10-01-satcat-owner.md`.
- [x] 2026-10-01 - Ran the one-time Fly setup. Image built (202 MB), scheduled Machine created in sjc, first run published successfully (2,010 objects, 509 conjunctions: 1 high / 32 moderate / 476 low, 5.3 s). Confirmed the public report URL serves real content with a matching run_id. See ADR 0009's verification note.
- [x] 2026-10-01 - Daily run code: `app.publish` (report + raw CelesTrak snapshot to a public
      Tigris bucket, overwritten each run), Dockerfile, fly.toml, Makefile targets, ADR 0009.
      Verified by local dry run, including that the published snapshot reproduces the report
      exactly. **Not yet deployed:** the one-time Fly setup (README "Daily run") is Max's to run;
      the image has never been built (no Docker locally). See
      `docs/sessions/2026-10-01-fly-daily-run.md`.
- [x] 2026-10-01 - README polish: project boundary section (heuristic risk, not Pc), results trimmed
      to real rows with the scale-test detail moved down, quickstart with real live `make screen`
      output, how-it-works diagram, ADR table, current "What's next". Surprise: that live run
      produced the first `high` at the default scope (IRIDIUM 105 vs. Fengyun-1C debris, 0.57 km).
      See `docs/sessions/2026-10-01-readme-polish.md`.
- [x] 2026-09-30 - Decided not to build a dashboard/report viewer. The JSON report is consumed programmatically (by portfolio-site's data file today, by the planned API layer later); no standalone viewer is needed.
- [x] 2026-09-29 - Replaced the placeholder eval harness with screening evals: 9 engineered SGP4
      scenarios checked against a brute-force 1 s oracle, plus 3 named-encounter cases on the frozen
      snapshot. 12/12 pass, oracle recall 1.0 (359 encounters), miss error at most 0.1 m. A
      mutation check confirmed that four deliberate breakages each fail cases. Surprise: the first
      scenario build set the miss offset sideways instead of radially, which only moved the TCA,
      and the oracle caught it. See ADR 0008 and `docs/sessions/2026-09-29-screening-eval-harness.md`.
- [x] 2026-09-30 - Max registered a Space-Track.org account (wanted for a supplemental feed and CDM cross-validation, no longer needed for SATCAT metadata since CelesTrak covers that).

- [x] 2026-09-28 - Session 2 Step B: scaling spike at 18,526 objects (`active` + Fengyun-1C,
      frozen snapshot). Pipeline 139.8 s against 4.9 s at 1,995 objects; survivor math is the
      largest phase (58 s); peak 2.2 GB. The coarse filter isn't required for full catalog on time
      (ADR 0007). See `docs/sessions/2026-09-28-session-2b-scaling-spike.md`.
- [x] 2026-09-27 - Frozen-snapshot parity regression test (`tests/regression/`), running in CI via
      `make test` with no live CelesTrak calls. Re-run: `uv run pytest tests/regression -v`.
- [x] 2026-09-27 - Session 2 Step A: KD-tree fine filter (`cKDTree.query_pairs` per timestep).
      Exact parity with the naive version on the frozen default-scope snapshot (509 conjunctions,
      0/31/478, closest active 1.29 km). Screening went from 26.4 s to 2.9 s (median of 3) and the
      pipeline from about 26 s to about 5.3 s. See
      `docs/sessions/2026-09-27-session-2a-kdtree-fine-filter.md`.
- [x] 2026-09-27 - Switched the default demo scope to `iridium-NEXT` + `fengyun-1c-debris`, dropped
      Cosmos-1408 from the spec, and added README Known failures (no live `high` example yet).
      The new default flagged 509 encounters (0 high, 31 moderate, 478 low) in 26 s.
- [x] 2026-09-27 - Session 1 spike: fetch -> propagate -> screen (naive all-pairs) -> assess ->
      JSON report, end-to-end on real CelesTrak data with per-step JSON timing traces. 460
      encounters flagged under 5 km in 24 h (18 moderate, 442 low), plus 39 co-located pairs.
      Pipeline takes about 23-28 s, of which propagation is about 1.6-2.4 s. See
      `docs/sessions/2026-09-27-session-1-pipeline-spike.md`.
