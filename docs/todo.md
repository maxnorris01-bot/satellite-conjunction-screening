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

- [ ] README: project boundary section (heuristic risk, not Pc, per ADR 0004), results, quickstart.
- [ ] Scheduled daily fetch+screen run with report and snapshot storage plus a retention window
      (ADR 0005's deployment decision, now with concrete purpose). Pick Fly.io/VPS cron vs. Lambda
      using the measured runtime/memory numbers from ADR 0007.
- [ ] SATCAT owner/operator metadata joined onto each tracked object (needed for any future
      "filter by owner" feature; extends the existing active-vs-debris SATCAT join).
- [ ] Small API layer serving the current report and recent history, replacing the static-file
      approach. This is the foundation-gate item: if this turns out easy, the visualization vision
      stays realistic; if it's a significant lift, bank what's built and move to City Livability
      Scoring Tool's MVP instead.

## Later

- [ ] Add a status note to ADR 0001: SATCAT metadata now comes from CelesTrak.
- [ ] **Deferred pending the foundation gate above:** 3D globe of all tracked objects (client-side
      SGP4 via `satellite.js`, fed by the API layer), owner/operator filtering UI, browser-geolocation
      sky view with per-satellite visibility/pass predictions, and a satellite-POV camera view. See
      the 2026-09-30 working-notes entry for the full vision and sequencing.

## Lower priority / opportunistic

- [ ] Add eval scenarios beyond the single 780 km circular shell: eccentric orbits, mixed-altitude
      crossings (ADR 0008's consequences).

- [ ] Flag co-located pairs whose separation trends toward zero (see ADR 0006's consequences).
- [ ] Cross-check a few flagged encounters against CelesTrak SOCRATES for the same window, as a
      correctness spot-check.
- [ ] Investigate the one-off 560 s wall-clock on the first-ever run (the pipeline itself took
      28 s). Not reproduced since; details in the working notes' open items.

## Completed (most recent first)
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
