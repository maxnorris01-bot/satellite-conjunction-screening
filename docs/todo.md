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

- [ ] **Make the daily run dependable: GitHub Actions trigger** (`satellite-conjunction-screening`;
      scoped in the 2026-10-04 "Daily run: Fly's built-in schedule is unreliable" working-notes
      entry). The Fly schedule is intact but didn't fire (last run 2026-10-03 21:46Z, manual).
      Max creates the Fly token and the `FLY_API_TOKEN` secret himself; first run via manual
      dispatch.
      - [x] 2026-10-04: workflow, ADR 0012, Makefile (`--schedule` removed, `fly-unschedule`
            added) and README on `feat/daily-run-github-actions`. Linted (actionlint + shellcheck).
      - [ ] Max: `fly tokens create deploy -a satellite-conjunction-screening` and
            `gh secret set FLY_API_TOKEN`.
      - [ ] Max: `make fly-unschedule FLY_MACHINE_ID=1850e47cdd43e8`, then confirm with
            `fly machine status 1850e47cdd43e8 -d` that `schedule` is gone (fallback in ADR 0012).
      - [ ] Acceptance: a manual dispatch goes green with a fresh snapshot date; a deliberate
            failure (wrong machine id, throwaway branch) goes red with a clear message; the next
            scheduled run fires on its own and adds a date.

- [ ] **Sky view: header toggle and selection in Sky (Phase 1b)** (`portfolio-site`; scoped in the
      2026-10-04 "toggle moves to the section header; selection in Sky" working-notes entry). Move
      the Globe | Sky toggle to the section heading row, click-to-inspect in the dome with az/el/range
      in the panel, selection kept across the toggle, plus Reset view and touch/accessibility polish.

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
      filtering (blocked on the GCAT join, its own to-do item below), sky-view pass predictions
      and naked-eye visibility (the basic Sky view is scoped, see above), and the satellite-POV
      camera view.
      Each needs its own Cowork scoping session once Phase 1 is live and reviewed.

- [ ] Sky view depth ideas offered but not chosen (2026-10-04): sky gradient and horizon haze,
      distance-based point size/brightness, short motion trails, a faint background star field.
      Revisit if the sky view still feels flat after the lighter ground.

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
- [x] 2026-10-04 - Sky view ground and perspective grid implemented (`portfolio-site`
      `feat/satellite-sky-ground`, pending review).
      - Ground `#26303c` against sky `#05070d`.
      - Labels at least 5.9:1 on either.
      - Grid cells 0.6 eye-heights, fading 3-18 eye-heights.
      - 60 fps at 50x under 4x CPU throttle.
      See `docs/sessions/2026-10-04-sky-ground.md`.
- [x] 2026-10-04 - Sky view Phase 1 implemented (`portfolio-site` `feat/satellite-sky-view`, pending
      review).
      - Geometry matches satellite.js to under 0.0001 degrees in the page, and east is on the
        right (scripted check).
      - One WebGL context across toggles; 60 fps at 50x under 4x CPU throttle.
      - Geocoder: Nominatim, chosen over Open-Meteo because only Nominatim resolves addresses.
      See `docs/sessions/2026-10-04-sky-view-phase-1.md`.
- [x] 2026-10-04 - Page redesign trimmed after review: kept the header and the Latest run + Risk
      breakdown row (GitHub button after the title, full-width two-line lede, three one-line tiles,
      risk caveat as a note under the card). Reverted the globe side column and dropdown back to
      the pre-redesign layout.
- [x] 2026-10-04 - Project page redesign built from the entry's description
      (`portfolio-site` `feat/satellite-page-redesign`, pending a mockup comparison):
      - stats beside risk, three tiles
      - globe with a side column (conjunction dropdown plus one panel)
      - controls, caption and filter bar under the globe
      See `docs/sessions/2026-10-04-page-redesign.md`.
- [x] 2026-10-04 - Top-conjunction view made reliable (`portfolio-site`
      `fix/satellite-globe-conjunction-view`, pending review).
      - Missing rings were frustum culling against a bounding sphere frozen where a marker first
        appeared.
      - The fly-in's camera end state was already correct in 25/25 cases; with the fix, 25/25
        also draw the rings and line.
      See `docs/sessions/2026-10-04-globe-conjunction-view.md`.
- [x] 2026-10-04 - Near-miss pair view now dims everything but the pair (`portfolio-site`
      `fix/satellite-globe-dim-near-miss`, pending review).
      - Surprise: the live neighbour could vanish with the clock frozen (a zero error bound plus
        floating-point rounding emptied the candidate list); fixed with a regression test.
      See `docs/sessions/2026-10-04-globe-dim-near-miss.md`.
- [x] 2026-10-04 - Dimming of everything but the inspected object and its live neighbour
      implemented (`portfolio-site` `feat/satellite-globe-dim-unselected`, pending review).
      - 20% alpha, as a separate draw layer over the filter state.
      - Exactly one bright neighbour, matched to the line, in 2,402/2,402 frames at 10x/50x.
      See `docs/sessions/2026-10-04-globe-dim-unselected.md`.
- [x] 2026-10-04 - Live nearest neighbour and 1x/10x/50x speeds implemented (`portfolio-site`
      `fix/satellite-globe-live-neighbor`, pending review).
      - A full scan costs 5 ms (20 ms at 4x CPU), so it uses a bounded candidate set from the
        render positions (2-38 objects).
      - Matched brute force within the throttle allowance in 180/180 samples across 1x/10x/50x.
      See `docs/sessions/2026-10-04-globe-live-neighbor.md`.
- [x] 2026-10-03 - Globe Phase 1c fix round implemented (`portfolio-site`
      `fix/satellite-globe-phase-1c-feedback`, pending review).
      - Zoom floor verified at 1.10 on wheel, trackpad pinch and touch pinch, and production had
        deployed it. The report most likely came from a cached bundle or a focus mode.
      - The "multiple selected" report came from separate inspect/replay/station states plus a
        10 px pick radius that rarely left empty space.
      See `docs/sessions/2026-10-03-globe-phase-1c-fix-round.md`.

- [x] 2026-10-03 - Globe Phase 1c (`portfolio-site` PR #5, merged): name filters by verified
      prefix groups with "only"/"show all" controls, ISS/Tiangong station-follow views, a sourced
      real-collision-history panel tied to live catalog counts, nearest-neighbor-on-select, and
      a deeper zoom floor (1.10 Earth radii). Corrected two of the scoping entry's own catalog
      numbers during implementation (ISS is 5 modules not 13; Fengyun debris is 1,940 not 1,954).
      Feedback after testing live surfaced 4 follow-up issues - see the fix-round item above.
      See `docs/sessions/2026-10-03-globe-phase-1c.md`.
- [x] 2026-10-03 - Globe Phase 1c implemented in `portfolio-site` (`feat/satellite-globe-phase-1c`,
      pending review). Two corrections to the scoping notes:
      - The ISS is 5 co-located modules, not 13 (the substring count caught unrelated names and
        free-flying `ISS OBJECT`s).
      - The Fengyun ASAT debris is `FENGYUN 1C DEB` (1,940), not the whole `FENGYUN` prefix.
      See `docs/sessions/2026-10-03-globe-phase-1c.md`.
- [x] 2026-10-03 - Globe Phase 1b implemented and merged in `portfolio-site` (PR #4).
      - Phase 1's replay drew both rings, but identical and overlapping, so it read as one. The
        pair now gets two colours and sizes plus a dashed, labelled miss line.
      - Verified: picking is pixel-threshold and zoom-independent, and the replay line matches
        the report's miss distance within 1 m.
      See `docs/sessions/2026-10-03-globe-phase-1b.md`.

- [x] 2026-10-03 - Globe Phase 1 (`portfolio-site` PR #3, merged): textured/rotating Earth
      (GMST-based, satellites stay in native ECI frame), all 19,240 objects live-animating with
      `slice=10` propagation, near-miss replay/focus, point-coloring toggle (type/owner/flat),
      and the 7-day-back/1-day-forward time slider. Orientation verified against satellite.js's
      own coordinate conversion plus a real visual spot-check. three.js + satellite.js code-split
      into their own 150 KB gzipped chunk; main bundle unaffected. Not yet tested: real
      Safari/mobile hardware, and the slider's backward range against real (vs. simulated)
      history, since the retention pipeline's first successful run hadn't landed yet. See
      `docs/sessions/2026-10-03-globe-phase-1.md`.
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
