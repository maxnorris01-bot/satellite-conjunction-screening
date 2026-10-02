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
  snapshot objects. Stored gzip-compressed and served with `Content-Encoding: gzip` and
  `Content-Type: application/json` (clarified 2026-10-02), since full-catalog scope makes this file
  several MB, not the sub-1MB it would be at the current default scope. This is deliberately
  **not** the snapshot files' style (`*.json.gz` keys served as opaque `application/gzip`).
  `objects/current.json` is meant for direct browser `fetch()`, which decompresses
  `Content-Encoding: gzip` transparently. The snapshots are reproducibility artifacts that no
  browser reads directly.
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

## Measured at full-catalog scope, 2026-10-02 (closes the open sizing item)

Scope: `config/screening.yaml` groups `active`, `fengyun-1c-debris`, `iridium-33-debris` and
`cosmos-2251-debris` (option (a) above). CelesTrak lists no other debris group;
`cosmos-1408-debris` no longer exists. Measured with `app.publish` end to end (fetch, screen,
report, objects artifact, snapshot), as `/usr/bin/time -l uv run python -m app.publish
--local-dir ...`. Three fresh-process runs on an Apple M5 (32 GB). Run 1 fetched live; runs 2-3
reused the cache.

| | Result |
|---|---|
| Objects fetched / screened | 19,308 / 19,240 (68 stale element sets dropped) |
| GP records per group | active 16,636; fengyun-1c-debris 1,979; cosmos-2251-debris 583; iridium-33-debris 110 |
| **Peak RSS, whole process** | **2,863-2,870 MB** (3 runs) |
| **Wall time, whole process** | **34.9-37.5 s** (run 1 includes a 2.5 s live fetch) |
| Pipeline phases (run 3) | propagation 4.1 s; neighbor search 12.6 s; survivor closest-approach 13.9 s; refinement 2.4 s; write report 0.6 s |
| Candidate pairs per timestep (mean, 485 km radius) | 172,816 |
| Conjunctions (run 3) | 56,367: 1,207 high / 5,778 moderate / 49,382 low; 185 co-located pairs |
| `reports/current.json` | 78.0 MB |
| `objects/current.json` | 19,240 objects; 7.86 MB raw, **1.39 MB gzipped** (668 use Alpha-5 TLE numbers) |
| Snapshot (`snapshots/current/`) | 1.5 MB gzipped, 8 files + manifest |

**Machine size: `shared-cpu-4x` with 8,192 MB** (`--vm-cpus 4 --vm-memory 8192`), 2.85x the
measured peak, following ADR 0009's ~3x convention. Shared CPUs cap memory at 2 GB per vCPU, so
8 GB needs 4 shared vCPUs. The alternative, `performance-1x` at 8 GB, costs about 20% more per
second for faster CPU this job doesn't need. Compared with ADR 0007's 18,526-object test (2.2 GB
on the Intel i5), this scope's peak is about 0.65 GB higher at a similar object count, because
the published job also holds the full report and the objects artifact.

### First deployed run on Fly, 2026-10-02

The Machine `1850e47cdd43e8` was updated to image `95d93aa`, `shared-cpu-4x` with 8,192 MB, in
`sjc`. The first `fly machine update` attempt failed with `MANIFEST_UNKNOWN` seconds after the image
push (registry propagation lag); an identical retry 18 s later succeeded. The update left the
Machine stopped, so it was started once by hand (`fly machine start`) for this verification run.
The daily schedule (`schedule: daily`, `restart: no`) is unchanged.

| | Fly (shared-cpu-4x, 8 GB) | M5 (local, for comparison) |
|---|---|---|
| Run id | `20261002T0403Z-4a2f42` | `20261002T0355Z-9c1e47` |
| Objects screened | 19,240 | 19,240 |
| **Peak RSS** (`peak_rss_mb` in the publish log) | **2,804 MB** (34% of 8 GB) | 2,863 MB |
| **Pipeline total** | **109.6 s** | 33.7 s |
| Phases | fetch 3.9 s; propagate 19.0 s; screen 81.3 s; write report 5.2 s | fetch 0.2 s; propagate 4.1 s; screen 28.8 s; write report 0.6 s |
| Machine start to publish | ~2 min (started 04:03:51Z, published 04:05:50Z) | - |
| Conjunctions | 56,402 (1,211 high / 5,781 moderate / 49,410 low), 183 co-located | 56,367 |

Verified in the public bucket afterwards, with all three carrying run id `20261002T0403Z-4a2f42`:
- `reports/current.json`: 78.0 MB, `application/json`.
- `objects/current.json`: 1.39 MB on the wire, `Content-Encoding: gzip`, `Content-Type:
  application/json`, 19,240 objects, `schema_version` 1.
- `snapshots/current/manifest.json`: the four groups and 8 files.

**Cost per run at the measured runtime:** about $0.0000295/s in `sjc` (the shared-cpu-4x base
plus 7 GB of extra RAM, at Fly's published rates, times the 1.19 sjc multiplier) x ~120 s
billed = **about $0.0035 per run, or about $0.11 a month** for daily runs. A stopped Machine isn't
billed for CPU or RAM.

**Left over in the bucket, as ADR 0009 predicted:** the previous scope's
`snapshots/current/gp-iridium-NEXT.json.gz` and `satcat-iridium-NEXT.json.gz` (last modified
2026-10-02 03:03Z). The manifest doesn't list them. Deleting them is a one-off manual cleanup that
wasn't done this session.
