# To-do - Satellite Conjunction Screening Tool

A running checklist, not a narrative. Check items off as they're done and add a short note (what
happened, any surprises) rather than deleting the line - that note is often more useful later than
the checkmark itself. Add new items as they come up; don't wait for a session's end. This is
*not* where decisions and reasoning go - that's `docs/working-notes-and-decisions.md`. This is just
"what's next."

## Up next (in priority order)

- [ ] **Max:** start the Space-Track.org account registration. Approval timing is unknown. It's no
      longer needed for SATCAT metadata (CelesTrak covers that), but it's still wanted for a
      supplemental feed and for CDM cross-validation.
- [ ] Session 2 Step B: scaling spike. Measure the KD-tree pipeline at larger scope (CelesTrak
      `active` + major debris groups, or GP `GROUP=all` if fair use allows). That measurement
      decides whether Step C is needed, and it's also ADR 0005's deployment input.
- [ ] Session 2 Step C (only if Step B shows it's needed): ADR 0003's coarse perigee/apogee filter.
      Validate that it never drops a pair the unfiltered screen flags.
- [ ] Time-chunked propagation, so full-catalog position/velocity arrays don't need about 2 GB at
      once.

## Later

- [ ] Replace the template's placeholder eval harness (`evals/`, `app.pipeline`) with screening
      regression cases, e.g. a frozen GP snapshot plus the expected encounters.
- [ ] CI: add the screening tests' real-data counterpart (frozen snapshot), not live CelesTrak
      calls.
- [ ] Dashboard view over the JSON report.
- [ ] README: project boundary section (heuristic risk, not Pc, per ADR 0004), results, quickstart.
- [ ] Containerization and a scheduled run (ADR 0005). Pick Fly.io/VPS cron vs. Lambda using
      measured runtime and memory.
- [ ] Add a status note to ADR 0001: SATCAT metadata now comes from CelesTrak.

## Lower priority / opportunistic

- [ ] Flag co-located pairs whose separation trends toward zero (see ADR 0006's consequences).
- [ ] Cross-check a few flagged encounters against CelesTrak SOCRATES for the same window, as a
      correctness spot-check.
- [ ] Investigate the one-off 560 s wall-clock on the first-ever run (the pipeline itself took
      28 s). Not reproduced since; details in the working notes' open items.

## Completed (most recent first)

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
