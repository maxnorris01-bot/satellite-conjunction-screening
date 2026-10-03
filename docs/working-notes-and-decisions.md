# Working notes and decisions log - Satellite Conjunction Screening Tool

This is a different kind of record from `docs/sessions/*.md`. Session docs narrate what changed in
one sitting and are written for someone with zero context picking up the diff. This file is the
opposite shape: short, durable entries - a decision plus *why*, or an open item worth remembering -
meant to be skimmed months later when the reasoning behind something has otherwise been forgotten.
Append to it whenever a real decision gets made, not just at the end of a session. If something is
already fully documented elsewhere (a technical fix in a session doc, a known failure in the
README, a design tradeoff in an ADR), point to it here rather than duplicating it.

## Decisions

**2026-10-03 - Globe build plan (Phase 1): core globe + near-miss replay, user-selectable point
coloring.** Follows the 2026-10-03 gate decision (go). Scoped in Cowork, to hand off to Claude Code
in `portfolio-site`.

**What ships in this phase:**
- **The core globe.** Fetch `objects/current.json` directly from the bucket (CORS already allows
  the Vercel origin and localhost); parse every object's TLE with `satellite.js`; render all
  19,240 as points with raw three.js on a bare sphere, orbit-style camera (pan/zoom/rotate, no
  fixed "up"). **Propagation is frame-sliced from the first commit** (`slice=10` - each object
  re-propagated roughly every 10th frame, not every frame every time) - this is the hard
  requirement the 2026-10-03 spike established, not a later optimization.
- **Near-miss replay/focus**, wired to the near-miss table already on the page
  (`SatelliteTool.tsx`'s `NearMissList`, fed by `GET /api/satellite/summary`). Clicking a row:
  looks up both objects' TLEs in the already-fetched `objects/current.json` by `norad_id`,
  propagates each to that row's `tca_utc` (not "now"), animates the camera to that point, and
  visually marks the two objects (e.g. a highlight ring or enlarged point) so they're findable at
  globe scale. A visible "back to full view" control returns to the free-roam camera. No new data
  needed - `tca_utc` and both `norad_id`s are already in the summary response; this is exactly
  what ADR 0010 anticipated when it specified this feature needs nothing beyond
  `objects/current.json` covering the full catalog.
- **User-selectable point coloring**, a small control (e.g. a segmented toggle) with three modes:
  - **By object type** (default) - active payload / rocket body / debris / unknown, from
    `object_type` + `active_payload` already in `objects/current.json`. No new data.
  - **By SATCAT owner** - `satcat_owner.name`, already in the data. Note: this field has dozens of
    distinct values; the legend needs a sensible "top N + other" grouping rather than one swatch
    per owner, or it becomes unreadable. Decide the exact cutoff during implementation, not here.
  - **Flat / single color** - what the spike itself measured; the simplest fallback view.
  Switching modes only recolors existing points (no re-fetch, no re-propagation) - should be
  instant.

**Explicitly deferred to later phases (not this session):**
- True operator filtering (SpaceX, etc.) - blocked on the GCAT join, which has its own unresolved
  to-do item and needs its own ADR. Owner-coloring above uses the state/org-level `satcat_owner`
  field that already exists, which is a different, looser thing than "operator."
- Browser-geolocation sky view and the satellite-POV camera - each is its own real feature, not
  an incremental add to the globe; scope those in their own future Cowork session once this phase
  is live and reviewed.

**Known open risks, not blockers for v1:**
- The frame-time spike validated `slice=10` on desktop Chromium (CPU-throttled to approximate a
  slower laptop), not actual mobile hardware or Safari. If the page looks janky on a phone,
  revisit then rather than guessing now - a portfolio site is mostly viewed on desktop anyway.
- `three.js` (~600 KB) plus `satellite.js` add real bundle weight. Since the page is already a
  separate route (`react-router-dom`), import the globe module so it code-splits onto the
  satellite-tool route rather than the app's main bundle - confirm this actually happens
  (`npm run build`'s chunk output), don't just assume route-based splitting is automatic.

**Branch:** `feat/satellite-globe` in `portfolio-site`, real feature branch (unlike the spike),
Conventional Commits, PR + review per the usual sequence. No AI attribution per the standing
convention.

**Amendment, 2026-10-03: textured/rotating Earth, real-time motion, and a 7-day time slider
folded into Phase 1.** Three more requirements came out of the same scoping session, after the
above was first written but before any of it was handed to Claude Code - all three change the
plan materially, so folded in here rather than left implicit.

- **The Earth must look like Earth, not a solid-colored sphere.** Texture the sphere with a
  public-domain day map showing real continents/oceans (e.g. NASA's Blue Marble/Visible Earth
  imagery), at a resolution that stays reasonable for bundle size (around 2k, not 8k).
- **Correct orientation is a rotation, not a conversion.** `satellite.js` already returns
  positions in an Earth-centered *inertial* frame (ECI/TEME) - the frame satellites naturally
  orbit in without the planet's spin added back in. The cheap and correct way to make the
  continents line up with real geography at the displayed moment is to **rotate the Earth mesh**
  by the sidereal angle (GMST) for that moment, computed once per frame from the simulated clock,
  and leave every satellite's already-computed ECI position alone. Converting each of 19,240
  satellite positions into an Earth-fixed frame instead would be the same visual result for far
  more per-frame cost, and would need redoing for every selected time anyway - rotating one mesh
  is strictly cheaper and is the standard technique for this.
- **Real-time motion, by default.** The simulated clock runs at true 1x: satellites visibly move
  within seconds (they're moving several km/s); Earth's spin itself is close to imperceptible
  over a short visit (one rotation is ~24h), which is fine - it doesn't need to be artificially
  sped up to look correct, it just needs to actually be live and continuously advancing rather
  than a static snapshot.
- **A time slider: 7 days back, about 1 day forward, with a "Live" control to snap back to
  real-time.** This is bigger than a frontend-only addition:
  - **Forward (now to about +24h) needs no new data.** The daily report already screens the
    *next* 24 hours from its own generation time (see `SatelliteTool.tsx`'s existing "following
    24 hours" copy), so today's `objects/current.json` and `reports/current.json` already cover
    this whole range - propagate the existing elements forward to the selected time, no new
    fetch.
  - **Backward (up to 7 days) needs real stored history, not extrapolation.** Running today's
    TLEs backward 7 days with SGP4 would drift from what actually happened (real drag/maneuvers
    aren't in old elements propagated the "wrong" direction for that long) - the risk-table entry
    above already notes SGP4 error grows with element age. Giving an accurate past view means the
    daily publish job on Fly needs to **start retaining dated snapshots instead of only
    overwriting `current.json`**: both `objects/<date>.json.gz` and, per Max's call, **a dated,
    gzip-compressed `reports/<date>.json.gz` too** (so near-miss replay also works on past
    dates, not just positions) - alongside the existing `current.json` overwrites, which stay for
    today's live consumers. A 7-day retention window, pruned on every run (delete any dated key
    older than 7 days so the bucket doesn't grow unbounded).
  - **This needs its own ADR** in this repo before implementation, the same way every other real
    storage/architecture decision here has (ADR 0009's bucket layout, ADR 0010's API shape) - the
    retention policy, the new dated-key naming, the pruning step, and the report's storage size
    once compressed (reports/current.json was measured at 78 MB uncompressed; confirm the gzipped
    size and multiply by 7 before treating this as a settled cost) all belong in that ADR rather
    than assumed here.
  - **Bucket CORS already covers this** - the existing rule is bucket-wide (not per-key), so new
    dated keys need no CORS change, same reasoning ADR 0010 already established for the two
    large current artifacts.
  - **Frontend:** dragging the slider into the backward range fetches that date's dated
    objects+report snapshot and propagates from *that day's own elements*, not today's;
    dragging into the forward range or back to "now" uses today's `current.json` as already
    planned; "Live" exits slider mode and resumes the continuous real-time animation.

**Decision: folded into this same Phase 1**, rather than split into its own later phase, per
Max's call - so `feat/satellite-globe` now also depends on the new retention work in this repo.
Sequencing within the one PR cycle is Claude Code's to work out, but the retention/ADR piece in
*this* repo is a real prerequisite for the slider's backward range specifically (not for the
globe, the real-time motion, or the forward range, which need nothing new).



**2026-10-03 - Frame-time spike results: the worst case fails under throttling; slicing
propagation across frames passes with margin.** Run by Claude Code on `portfolio-site`'s
`spike/globe-frame-time` branch (local only, one commit, not pushed) against the entry below.

**Setup:**
- **Data:** the real `objects/current.json` (run `20261002T0403Z-4a2f42`). All 19,240 objects
  parsed and propagated with 0 errors, including the 668 Alpha-5 numbers.
- **Libraries:** `satellite.js` 7.1.0 (plain-JS SGP4 plus ECI->ECF for every object, every
  frame) and raw three.js 0.186 `Points`.
- **Browser:** Chromium 153 in a headed window on the M5. That gives the real GPU (`ANGLE Metal
  Renderer: Apple M5`), a 60 Hz display, devicePixelRatio 2 and a 1440x900 viewport. Chrome
  isn't installed, so it ran under Playwright.
- **Throttling:** CDP `Emulation.setCPUThrottlingRate`, the same call DevTools' "CPU: Nx
  slowdown" makes.
- **Measurement:** a 5 s warm-up, then 45 s measured per run.

Frame time is the interval between `requestAnimationFrame` callbacks, so 16.7 ms is the 60 Hz
ceiling. The worst-case rows show two runs each as A / B.

| CPU | Variant | Frame mean (ms) | Frame p95 (ms) | Propagate mean / p50 (ms) | fps |
|---|---|---|---|---|---|
| 1x (M5) | every object, every frame | 18.2 / 16.7 | 33.3 / 17.6 | 9.7 / 6.5, p50 ~6.6 | 55 / 60 |
| 4x | every object, every frame | **30.4 / 38.4** | 116 / 133 | 30-37, p50 ~21 | 33 / 26 |
| 6x | every object, every frame | **54.9 / 59.3** | 151 / 232 | 53-57, p50 ~31 | 18 / 17 |
| 4x | `slice=10` (1/10 of objects per frame) | **16.8** | 17.6 | 7.8, p50 9.0 | 59 |
| 6x | `slice=10` | **20.5** | 33.9 | 11.0, p50 3.2 | 49 |

**Against the bar:**
- The M5 unthrottled clears it easily, so neither "shrink the vision" nor "bank" is triggered
  on that branch of the rule.
- The worst case **fails** throttled. At 4x the mean straddles 33 ms across two runs, and the
  p95 of 116-133 ms means visible hitches regardless. At 6x it fails clearly.
- The mitigation the scoping entry named **passes with margin**. `?slice=10` refreshes each
  object every 10 frames (~0.17 s, ~1.3 km of LEO motion, invisible at globe scale) and holds
  ~60 fps at 4x and ~49 fps at 6x.
- Rendering isn't the bottleneck. Frame work is almost entirely propagation; three.js draws
  19k points in well under 1 ms.

**Observations worth carrying forward:**
- **The worst case's tail is garbage-collection-shaped.** p50 propagation is 6.5 ms on the M5,
  but some runs show 26-48 ms spikes. Each `propagate` and `eciToEcf` call allocates result
  objects, roughly 19k x several per frame. Slicing helps mainly because it allocates less
  per frame.
- **CPU throttling slows only main-thread JS, not the GPU.** That's fine here, since the cost is
  propagation, but it's an approximation of a slower laptop, not a measurement of one.
- **Unmeasured further headroom** if it's ever needed:
  - propagate in a Web Worker
  - `satellite.js` 7's WASM `BulkPropagator`
  - interpolating between once-a-second positions, the scoping entry's other idea

**Claude Code's read, for Cowork's decision:** go, with time-sliced (or otherwise
non-every-frame) propagation as a design requirement from day one, not an optimization later.
Rendering all 19,240 objects works, so filtering to active payloads isn't needed for
performance. The branch is kept locally until Cowork decides, in case a re-run is wanted. It
gets deleted per the scoping entry once the call is made (`git branch -D spike/globe-frame-time`
in `portfolio-site`).

**2026-10-03 - Frame-time spike run: go, with propagation sliced across frames as a requirement
from the start.** Measured on `portfolio-site`'s `spike/globe-frame-time` branch (Playwright's
Chromium on the M5, real `objects/current.json`, all 19,240 objects including the 668 Alpha-5
ones, 0 parse/propagation errors). Every-object-every-frame propagation passes unthrottled on the
M5 (18.2/16.7 ms mean) but fails once CPU-throttled to approximate a slower laptop (4x: 30.4/38.4
ms mean, p95 over 110 ms, visible stutter; 6x: fails clearly). Spreading propagation across frames
(`slice=10` - each object re-propagated every 10th frame, about every 0.17 s, roughly 1.3 km of
motion for a LEO object and invisible at globe scale) clears the bar with margin: about 60 fps at
4x throttle, about 49 fps at 6x. Rendering is cheap regardless (under 1 ms for 19k points); the
entire cost is SGP4 propagation and its per-call allocation - the slow unsliced frames look like
GC pauses from the tens of thousands of small result objects created every frame. Caveat: CPU
throttling only slows JS, not the GPU, so this approximates a slower laptop rather than measuring
one.

**Decision: go.** Neither fallback from the spike-scoping entry (shrink the rendered catalog,
bank the project) is triggered - the M5 clears the bar on its own, and the slicing mitigation
clears it even throttled. Frame-sliced propagation (each object updated on a staggered ~10-frame
cycle, not every frame) is **not an optional later optimization - it's a hard requirement from the
start** of any globe implementation, per this result. This reopens the 2026-09-30 gate: the
visualization vision (3D globe, owner/operator filtering, sky view, satellite POV) is real scope
again, not deferred.

Spike code stays on `portfolio-site`'s `spike/globe-frame-time` branch, unmerged, in case a re-run
is wanted; delete with `git branch -D spike/globe-frame-time` once that's no longer needed.

**2026-10-03 - Frame-time spike scoped (Cowork): the gate's real test, before any globe feature
work.** The foundation gate closed easily on 2026-10-02 (CORS, `/summary`, `objects/current.json`
all shipped without friction) - but that gate tested the *data and API* foundation, not the
visualization vision's actual risk: can a browser propagate 19,240 objects with `satellite.js` and
render them as points on a 3D globe without choking. Nothing has exercised that yet. This is the
"validate before building out scope" step from `Engineering_Standards.md`, applied to the
visualization vision itself before any globe UI gets built around it.

**Scope, deliberately minimal (time-boxed):**
- Fetch the real `objects/current.json` from the public bucket (CORS already allows
  `localhost:5173`/`4173` and the Vercel origin) - real 19,240-object data, not synthetic.
- Parse each object's TLE with `satellite.js` and propagate every object to the current moment.
- Render all positions as points on a bare sphere with **raw three.js**
  (`Points`/`BufferGeometry`), not `globe.gl` - the point of the spike is to isolate the two real
  unknowns (SGP4 propagation cost, point-rendering cost) without a wrapper's own overhead
  muddying the number. Basic orbit-controls camera only.
- Propagate every object every animation frame (the worst case - no throttling to "recompute once
  a second and interpolate" yet; that's a mitigation to try *if* the worst case fails, not the
  first thing measured).
- Measure frame time via `performance.now()` across a sustained ~30-60 s run: mean and p95 frame
  time, logged to the console or a simple on-screen readout.
- **Test twice:** once unthrottled on Max's M5 (a ceiling, not representative), and once with
  Chrome DevTools CPU throttling at 4x-6x slowdown, to approximate what a hiring manager's actual
  laptop would see. The M5 number alone isn't the answer to "will this look smooth to a visitor."
- **Explicitly out of scope:** UI controls, filtering, labels, click-to-select, camera polish,
  Earth texture/stars, the near-miss replay feature, any production wiring. This is a
  measurement, not a feature.

**Where it lives:** a disposable branch in `portfolio-site` (`spike/globe-frame-time`), not wired
into nav, never merged to `main` regardless of outcome. Findings get written up here (a follow-up
entry to this one) and the branch gets deleted once the number is in - keeps `main`'s visible
history clean of a throwaway experiment either way.

**Success bar (working definition, not yet validated):** mean frame time at or under ~33 ms
(≈30 fps) under the 4x-6x-throttled run counts as "smooth enough for a portfolio demo." If the
unthrottled M5 run itself can't clear that bar, the vision needs to shrink (fewer rendered objects,
e.g. active payloads only at ~16,636, or a user-toggle filter) or the project banks here per the
2026-09-30 gate decision and work moves to City Livability Scoring Tool's MVP.

**Division of labor:** scoped here; handed to Claude Code in `portfolio-site` to implement and
run, per `Engineering_Standards.md`'s workflow split. Numbers come back as a short write-up (not a
polished session doc, since nothing here survives), and the resulting go/no-go gets decided back
in Cowork against the bar above.



**2026-10-02 - Foundation gate closed: bucket CORS is bucket-wide (origin-narrowed), `/summary`
shipped, `/history` deferred.**
- **CORS:** Tigris CORS rules can't target individual keys (dashboard, S3 `PutBucketCors` and
  `tigris buckets set-cors` all take the same bucket-level rule). Max approved a bucket-wide rule
  allowing only `GET` from `portfolio-site`'s Vercel origin plus localhost 5173/4173. It was
  applied from a throwaway `fly machine run --rm` so the bucket credentials never left Fly.
- **API:** `portfolio-site`'s `GET /api/satellite/summary` is the only API so far.
- **`/history`:** deferred, because the daily run keeps no history to serve. It needs a retention
  change here first.

Policy, verification and watch items: [ADR 0010](adr/adr-0010-portfolio-api-and-full-catalog-scope.md)'s
"as built" section.

**2026-10-02 - Full-catalog scope measured and the Fly Machine resized; `objects/current.json`
added.** This implements ADR 0010 (with its amendment):
- **Scope:** `config/screening.yaml` now screens CelesTrak's full published catalog, `active` plus
  every listed debris group (`fengyun-1c-debris`, `iridium-33-debris`, `cosmos-2251-debris`;
  `cosmos-1408-debris` no longer exists). That's 19,308 objects fetched and 19,240 screened.
- **Measured** with the whole `app.publish` job, 3 runs on an Apple M5: **peak RSS 2,863-2,870 MB,
  wall time 34.9-37.5 s**, 56,367 conjunctions, a 78 MB report and a 1.39 MB gzipped objects file.
- **Machine:** `shared-cpu-4x` with 8 GB (2.85x the peak, per ADR 0009's ~3x convention). Shared
  CPUs cap memory at 2 GB per vCPU, so 8 GB needs 4 vCPUs. `performance-1x` at 8 GB would cost
  about 21% more for CPU speed this job doesn't need.
- **Space-Track full-catalog source:** deferred to its own future ADR (amendment option (b)).
- **Trimmed report and API changes:** deferred to the `portfolio-site` session.

- **Deployed and verified on Fly** the same day: image `95d93aa` on `shared-cpu-4x`/8 GB. The
  first run published report, objects and snapshot, all with run id `20261002T0403Z-4a2f42`. On
  Fly: **peak RSS 2,804 MB, pipeline 109.6 s**, about $0.0035 per run.
- **`Content-Encoding: gzip` for `objects/current.json`** is the intended design, not a deviation
  (Max, 2026-10-02). It's for direct browser `fetch()`; the snapshots' opaque `.json.gz` style is
  for reproducibility files. ADR 0010's wording was tightened to say so.

Full table: [ADR 0010](adr/adr-0010-portfolio-api-and-full-catalog-scope.md)'s measurement section.

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
