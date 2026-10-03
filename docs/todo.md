# To-do - Satellite Conjunction Screening Tool

A running checklist, not a narrative. Check items off as they're done and add a short note (what
happened, any surprises) rather than deleting the line - that note is often more useful later than
the checkmark itself. Add new items as they come up; don't wait for a session's end. This is
*not* where decisions and reasoning go - that's `docs/working-notes-and-decisions.md`. This is just
"what's next."

## Up next (in priority order)

*Phase per the 2026-10-03 gate decision (go) in `docs/working-notes-and-decisions.md`: the
foundation and the frame-time spike are both done, so Phase 1 of the visualization vision is now
the active work.*

- [ ] **Get the daily run publishing again.** The retention image (`e7f3427`) is deployed on
      Machine `1850e47cdd43e8`, but the 2026-10-03 04:43Z run failed with CelesTrak `403 Forbidden`
      (likely a short-term block after an interrupted run plus an immediate restart). Start it
      once after about 2 h, not repeatedly. Then verify the dated keys and `history/index.json`
      land in the bucket. The globe's backward range fills in one day per run after that.
- [ ] **Review and merge globe Phase 1** (`portfolio-site` branch `feat/satellite-globe`, 4
      commits, local). Decide whether Vercel preview origins should be added to the bucket's
      CORS rule (previews can't load the globe today). See
      `docs/sessions/2026-10-03-globe-phase-1.md`.

## Later

- [ ] `GET /api/satellite/history` (ADR 0010, lower priority). Blocked on this repo first: the daily
      run overwrites `reports/current.json` and keeps no history (ADR 0009), so there's nothing
      to stitch. Needs dated reports or dated small summaries published with a retention window,
      then the `portfolio-site` function.

- [ ] Space-Track full GP catalog as the source for true full-catalog scope (ADR 0010 amendment,
      option (b)). Needs its own ADR: new primary source, credentials as Fly secrets, rate limits,
      and a revision to ADR 0001.

- [ ] Operator join from GCAT (Jonathan McDowell's catalog: `Owner` = owner/operator org code,
      `State` = country) onto each object, for "filter by operator" (e.g. SpaceX). SATCAT can't
      supply it (see the 2026-10-01 working-notes entry). Needs its own ADR: source reliability
      (one maintainer), GCAT-to-NORAD id mapping, license, and how often the daily run refreshes
      a large TSV.

- [ ] Add a status note to ADR 0001: SATCAT metadata now comes from CelesTrak.
- [ ] **Deferred to later phases** (see the same working-notes entry for why): true operator
      filtering (blocked on the GCAT join, its own to-do item below), browser-geolocation sky
      view with per-satellite visibility/pass predictions, and the satellite-POV camera view.
      Each needs its own Cowork scoping session once Phase 1 is live and reviewed.

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
- [x] 2026-10-03 - Globe Phase 1 implemented in `portfolio-site` (`feat/satellite-globe`, pending
      review): textured GMST-rotated Earth, all 19,240 objects live with `slice=10`, near-miss
      replay, type/owner/flat colouring, and a time slider with Live. Also
      `/api/satellite/summary?date=`.
      - Verified at 60 fps on the M5 unthrottled and at 4x CPU throttling.
      - Surprise: only three categorical hues pass the all-pairs colour checks on the dark
        globe, so owner colouring is US / China / CIS plus Other.
      See `docs/sessions/2026-10-03-globe-phase-1.md`.
- [x] 2026-10-02 - Retention ADR 0011 written and implemented:
      - Dated `objects/<date>.json.gz` and `reports/<date>.json.gz` (gzip, `Content-Encoding:
        gzip`), pruned past 7 days every run, plus `history/index.json`.
      - Local dry run: report 76.2 MB to 5.3 MB, peak 2,875 MB, seeded old keys pruned, dated
        copies byte-identical to `current.json`.
      - Not deployed yet (item above). See `docs/sessions/2026-10-02-snapshot-retention.md`.

- [x] **Frame-time spike (Claude Code, in `portfolio-site`), run 2026-10-03:** every-object-every
      -frame propagation fails once throttled (4x: 30.4/38.4 ms mean, p95 >110 ms; 6x: 54.9/59.3
      ms). `slice=10` (re-propagate each object every 10th frame) passes with margin (4x: 16.8 ms
      mean; 6x: 20.5 ms mean). Full numbers and method in the 2026-10-03 working-notes entry.
      Spike branch `spike/globe-frame-time` in `portfolio-site`, unmerged - kept for now in case a
      re-run is wanted.
- [x] **Gate decision (Cowork), 2026-10-03: go.** The M5 clears the bar on its own and the
      `slice=10` mitigation clears it even throttled, so neither fallback (shrink the catalog,
      bank the project) is triggered. The visualization vision (3D globe, owner/operator
      filtering, sky view, satellite POV) is real scope again. Frame-sliced propagation is now a
      hard design requirement for all of it, not an optional optimization - see the "Later" item
      below.

- [x] 2026-10-02 - Foundation-gate item, remainder (ADR 0010's amendment):
      - Bucket CORS applied: GET only, from `portfolio-site`'s Vercel origin plus localhost
        5173/4173.
      - `portfolio-site` PR #2: `GET /api/satellite/summary` (risk counts plus the top-N
        conjunctions, ~11 KB) feeds the satellite page and the home page's stats.
      - Surprise: Tigris CORS can't target individual keys, so the rule is bucket-wide and
        narrowed by origin (Max approved).
      - `/history` wasn't built, because there's no stored history to serve (moved to Later).
      - The deployed route was checked on the Vercel preview by Max, since Deployment Protection
        blocks curl.
      See `docs/sessions/2026-10-02-foundation-gate-cors-summary.md`.
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
