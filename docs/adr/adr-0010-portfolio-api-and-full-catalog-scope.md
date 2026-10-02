# ADR 0010: Portfolio API layer, full-catalog scope, and the objects/current.json foundation artifact

**Status:** Accepted, 2026-10-02. Amended 2026-10-02 (see amendment at the end) after Claude Code's read-only scoping pass surfaced two real constraints this ADR hadn't accounted for: CelesTrak has no all-objects query, and the report/objects payloads exceed Vercel's serverless response limit at full-catalog scope.

## Context

`docs/todo.md`'s foundation-gate item calls for "a small API layer serving the current report and
recent history, replacing the static-file approach" `portfolio-site` uses today. This is the single
gate from the 2026-09-30 vision decision (`docs/working-notes-and-decisions.md`): if it's easy, the
visualization vision (3D globe, owner/operator filtering, sky view, satellite POV) stays realistic;
if it's a significant lift, bank the work and move to City Livability Scoring Tool's MVP instead.

Scoped in a Cowork session 2026-10-01/02. Two things came out of that scoping that changed the
shape from what the to-do item implied:

1. **The report alone isn't enough data for the future vision.** `reports/current.json` only
   carries full object detail for objects already in a flagged conjunction or co-located pair — not
   the whole screened catalog. The full catalog's raw TLEs are published, but only inside
   `snapshots/current/gp-<group>.json.gz` (raw, gzipped CelesTrak GP responses) — usable, but it
   means a browser would need to fetch multiple gzipped files per group and parse CelesTrak's native
   format just to get a flat `{norad_id, name, tle lines}` list for every tracked object. Every one
   of the future features (3D globe, owner/operator filtering, sky view, satellite-POV camera) needs
   exactly that flat list, propagated client-side with SGP4 (`satellite.js`) to the current moment
   or an arbitrary selected time — none of them need *stored history*, because a trailing path or a
   "where will this be tomorrow" projection is just propagating the *same* current TLE backward or
   forward; the elements already encode the whole trajectory.

2. **A fifth future feature surfaced during scoping: near-miss replay/focus.** Given the existing
   list of flagged conjunctions, select one and have the globe jump to that pair's `tca_utc`,
   propagate just those two objects to that moment, and focus the camera there. This needs no new
   data beyond what's below — the report already carries `tca_utc` and both objects' `norad_id`s per
   conjunction; the only requirement is that the flat object list cover *every* screened object, not
   just ones already in a flagged pair, since a selected near-miss can involve any two objects in the
   catalog.

Separately, Max decided the catalog scope itself should expand from the MVP's default (~2,010
objects) to the full tracked catalog ("if we can grab everything we should do that"), which has its
own infrastructure consequences accounted for below.

## Options considered

**API shape**, given there's no server today and the bucket (ADR 0009) is already public:
1. **No server — static objects + CORS.** Fetch bucket JSON directly, client-side. Cheapest, but
   CORS on an S3-compatible bucket is its own configuration surface, and "recent history" becomes N
   client round-trips (an index fetch plus one per day) with any stitching logic living in the
   frontend.
2. **A thin serverless function in `portfolio-site`'s existing Vercel deployment.** One function,
   same repo, same deploy pipeline, no new account or ops surface. Fetches the bucket server-side
   and returns JSON same-origin — no CORS configuration needed at all — and can consolidate a
   multi-day history fetch into one response.
3. **A standalone, always-on API service** (e.g., a continuously-running Fly app). Real new
   infrastructure to run and pay for continuously, for a job that's otherwise all static-file
   serving. This is the shape `Engineering_Standards.md`'s "validate before building out scope"
   lesson actually warns against here.

**Catalog scope:**
1. Keep the MVP's default scope (~2,010 objects). Smallest file sizes, but doesn't reflect "the
   full catalog" and undersizes the near-miss list the new replay feature wants to be interesting.
2. Expand to the full tracked catalog. Matches the stated goal and gives the near-miss-list feature
   real material, at the cost of a real memory/runtime increase in the daily job (see Consequences).

## Decision

- **A new published artifact, `objects/current.json`**: a flat, propagation-ready list of every
  screened object — `norad_id`, `name`, `tle_line1`, `tle_line2`, `element_epoch_utc`,
  `satcat_owner`, `object_type`, `active_payload`, `source_groups` — plus its own `schema_version`,
  `run_id`, and `generated_at_utc`. Published by `app.publish` alongside the existing report and
  snapshot objects. Stored/served gzip-compressed (same `Content-Encoding` pattern as the existing
  snapshot files) since full-catalog scope makes this file several MB, not the sub-1MB it would be
  at the current default scope.
- **API: option 2 — one Vercel serverless function in `portfolio-site`.**
  `GET /api/satellite/current` returns `{ report, objects, run_id, generated_at_utc }` in one
  response, reading `reports/current.json` and `objects/current.json` from the Tigris bucket
  server-side. No bucket CORS configuration needed. `GET /api/satellite/history?days=N` (default 7,
  per the earlier retention decision) is the same shape, lower priority — see Consequences.
- **Catalog scope: option 2 — expand to the full tracked catalog**, via `config/screening.yaml`'s
  `groups`. Before locking a machine size into this ADR, re-measure actual peak memory and runtime
  at the true full-catalog scope (ADR 0007's 18,526-object test is a data point, not this scope's
  ceiling — don't extrapolate without a real run). Size `--vm-memory` at roughly 3x the measured
  peak, following ADR 0009's own margin convention.
- **The near-miss replay/focus feature needs no additional data or API scope.** It's a frontend
  capability built entirely on `report.conjunctions[].tca_utc` / `.object_a.norad_id` /
  `.object_b.norad_id` (already in the report) plus `objects/current.json` covering the full catalog
  (already decided above) for TLE lookup of either object. Noted here so a future session doesn't
  mistake it for new scope.

## Consequences

- **`objects/current.json` becomes the load-bearing artifact** for four of the five future features
  (globe, filtering, sky view, satellite POV) plus the near-miss replay feature; `reports/current.json`
  (plus its history) only matters for the MVP collision widget and its possible trend sparkline.
  History is real but lower-priority: worth building since it's cheap and already decided, but it
  shouldn't gate or complicate shipping the foundation-gate item. If time runs short, ship
  `/current` first and treat `/history` as the "if this is easy, keep going" portion of the gate.
- **A fresh memory/runtime measurement at true full-catalog scope is an open action item** before
  the Fly machine's `--vm-memory` can be set with confidence — don't copy ADR 0007's number forward
  without re-measuring.
- **Conjunction counts will grow substantially** at full-catalog scope (likely well beyond the
  current 509) — good fuel for the "expand the list of near misses" interaction, but the MVP's
  stat-tile copy ("509 conjunctions") needs to read sensibly at a much larger number.
- **One new deploy surface**: a Vercel serverless function in `portfolio-site`. Small and riding on
  infrastructure that already exists for that site, not a new service to operate.
- **No bucket CORS configuration needed**, since the Vercel function fetches server-side and serves
  same-origin to the browser.
- **If the bucket's internal layout or storage provider ever changes, only the Vercel function
  changes** — the frontend talks to `/api/satellite/*`, never the bucket directly.

## Amendment, 2026-10-02: catalog definition and API payload size

Claude Code's first read-only pass on this ADR (before touching anything) found two things that
change its shape, surfaced back to Cowork for decisions rather than assumed:

**"Full tracked catalog" needs a precise definition.** CelesTrak's GP endpoint has no all-objects
query — it supports `CATNR`, `INTDES`, `GROUP`, `NAME` and `SPECIAL` (`GPZ`, `GPZ-PLUS`,
`DECAYING`), not "everything." Two ways to get there:
- **(a) A union of CelesTrak groups** — active plus the debris-event groups (Fengyun-1C,
  Iridium-33, Cosmos-2251, etc.). Same source, no new credentials, but a curated subset (~20k+
  objects), not literally every tracked object — plenty of on-orbit debris isn't in any CelesTrak
  group.
- **(b) The Space-Track full GP catalog**, via the account registered 2026-09-30. Genuinely
  everything, but a new primary data source: credentials as Fly secrets, Space-Track's stricter
  rate limits, and a revision to ADR 0001 (which deliberately kept Space-Track supplemental, not
  primary). That's its own scope decision, not something to fold into this session.

**Decision: (a) now, (b) deferred to its own future ADR.** Taking on a new primary data source
mid-session, with new credentials and rate-limit constraints, is exactly the kind of unplanned
scope growth `Engineering_Standards.md`'s "validate before building out scope" lesson warns
against. (a) still moves scope from ~2,010 objects to ~20k+, which is the real change Max asked
for; true Space-Track-backed completeness can be evaluated deliberately later, as its own decision
with its own ADR, if (a) turns out to not be enough.

**The report and `objects/current.json` are both too large for the Vercel function design as
written.** ADR 0007 measured a 76 MB report at 18,526 objects (63,896 conjunctions); full (a)-scope
will be larger still, and `objects/current.json` at ~20k+ objects also likely exceeds a few MB.
Vercel serverless functions cap response bodies at roughly 4.5 MB, so `GET /api/satellite/current`
bundling the full report and the full object list in one response — this ADR's original API
decision — won't work at this scale.

**Decision: supersede part of the API-shape decision above.** The large static artifacts (the full
report, `objects/current.json`) are fetched **directly from the public Tigris bucket, with CORS
enabled for those two objects** — reversing this ADR's "no bucket CORS needed" call, but only for
these two, and only because of the size constraint, not the configuration-overhead reasoning option
1 was originally rejected for. The Vercel function's role narrows to a small, server-computed
`GET /api/satellite/summary` (risk-level counts, top-N near-misses with enough fields for the
near-miss list UI) that stays comfortably under the response cap — and remains the right place for
`/api/satellite/history`'s stitching logic once that's built. This is a provisional resolution to
validate in the `portfolio-site` implementation session, not a final mandate on exact endpoint
shapes.

**Deploy process for this session (satellite-conjunction-screening repo only).** `flyctl` isn't
installed on this machine; Claude Code installs it (`brew install flyctl`) and Max runs
`fly auth login` himself, since login is interactive. The existing scheduled Machine's id is
`1850e47cdd43e8`. Steps that change the Fly account (`fly-build`, `fly-update` against that
Machine) require Max's explicit go-ahead at the time, after Claude Code reports the real measured
memory/runtime and the resulting Fly Machine type and its per-run cost — per
`Chat_Instructions.md`'s cost/risk discipline, a step with real cost impact is called out on its
own, not bundled into a larger batch of instructions.
