# Working notes and decisions log - Satellite Conjunction Screening Tool

This is a different kind of record from `docs/sessions/*.md`. Session docs narrate what changed in
one sitting and are written for someone with zero context picking up the diff. This file is the
opposite shape: short, durable entries - a decision plus *why*, or an open item worth remembering -
meant to be skimmed months later when the reasoning behind something has otherwise been forgotten.
Append to it whenever a real decision gets made, not just at the end of a session. If something is
already fully documented elsewhere (a technical fix in a session doc, a known failure in the
README, a design tradeoff in an ADR), point to it here rather than duplicating it.

## Decisions

**2026-10-04 - Dimming built as a separate draw layer.** Per the entry below (`portfolio-site`
`feat/satellite-globe-dim-unselected`; details in
`docs/sessions/2026-10-04-globe-dim-unselected.md`):
- **Dim level:** `DIM_ALPHA = 0.2`.
- **Two buffers:** the engine draws a copy of the filter rgba with dimming applied and leaves the
  filter rgba as the source of truth for visibility, so picking, the neighbour search and counts
  ignore dimming, and deselect restores exactly.
- **Rendering:** points had to switch from `alphaTest 0.5` to blending (alphaTest 0.01,
  transparent, no depth writes) so a 20% point shows instead of being discarded.
- **Handoff:** the new neighbour brightens in the same frame as the line moves (verified on
  every frame at 10x/50x).

**2026-10-04 - Globe: dim everything except the selected object and its live neighbour.** Max's
request after the live-neighbour round. When one object is inspected, every other object goes
semi-transparent; the selected object and its nearest neighbour stay at full opacity. When the
neighbour changes (it now does, live, especially at 10x/50x), the new one brightens and gets the
dashed line and distance label, and the old one dims. Scoped for one `portfolio-site` branch;
orientation and the frame-sliced propagation are untouched.

- **Scope of the dimming.** Single-object inspect only. The near-miss pair view keeps both objects
  bright and does not dim the rest; station follow is unchanged. Deselecting (empty click, the
  Deselect button, or picking a pair/station) restores everything.
- **Dimmed is not hidden.** Dimmed objects stay eligible as the nearest neighbour and stay
  pickable. Watch the existing convention: the neighbour search, picking and the "Showing N of M"
  count treat `rgba` alpha > 0 as "visible" (`engine.ts`). Dim alpha must stay above zero and must
  not be confused with filter-hidden (alpha 0); keep dimming as a separate multiplier layered on
  the filter/colour alpha so un-dimming restores the exact prior state, and keep the visible count
  and neighbour search keyed to the filter state, not the dim state.
- **Neighbour handoff.** On each live refresh, if the neighbour index changes, un-dim the new one
  and re-dim the old one in the same update as the line moves. No flicker where both or neither
  are bright. The neighbour exemption also applies to the first neighbour found on selection.
- **Dim level.** Start around 20% opacity of the object's normal alpha, tune by eye. The two bright
  objects must stand out clearly against a dense shell, and dimmed points should still read as a
  faint backdrop, not vanish. Name the final value as a constant.
- **Cost.** Dimming only needs the alpha buffer rewritten on selection change and on a neighbour
  change (not every frame); confirm 60 fps holds at 50x with an object selected, as in the last
  round.
- **Acceptance.** Select an object: all others dim, it and its neighbour stay bright. At 10x/50x,
  watch the neighbour change and confirm exactly one bright neighbour at a time, matched to the
  line. Deselect and confirm everything returns to normal, including under active filters and
  colour modes. Lint/typecheck/tests/build clean, no page errors.

**2026-10-04 - Live nearest neighbour built: bounded candidates, no periodic full scan.** Per the
entry below (`portfolio-site` `fix/satellite-globe-live-neighbor`; details in
`docs/sessions/2026-10-04-globe-live-neighbor.md`):
- **Measured:** an exact full-catalog scan is 5.2 ms on the M5 and 19.6 ms at 4x CPU, too heavy
  for the every-sim-second refresh 50x needs.
- **Chosen:** candidates from the frame-sliced render positions with a proven error bound
  (11 km/s x slice staleness, keep within min + 4 x bound), then exact propagation of only those
  (2-38 objects). After a big time jump it waits a few frames for the slices instead of scanning.
- **Verified:** 180/180 samples within the throttle allowance against brute force across
  1x/10x/50x, with 60 fps at 50x even under 4x CPU throttling.
- **Visible-only search** means the nearest changes with filters (deliberate, per the entry).
- **Live at 50x** now pauses at the end of the ~24 h forward range.

**2026-10-04 - Globe: live nearest neighbour, and playback speeds 1x/10x/50x.** Max saw cases
where an object sat visibly next to the selected one while the dashed line went elsewhere. Checked
independently against the live 19,246-object catalog (`satellite.js`, brute force, 25 random
objects): `nearestTo` is correct *at the click moment*. The bug is that the neighbour is chosen
once and frozen, and orbits separate at several km/s. The pick was no longer the nearest after
10 s in 11 of 25 cases, 60 s in 21 of 25, 300 s in 23 of 25; at +60 s the line was often
400-1,000 km long while the true nearest was ~100 km. Scoped for one branch on `portfolio-site`;
none of it touches orientation or the frame-sliced render propagation.

**1. Keep the nearest neighbour live.** While an object is inspected, recompute the nearest
neighbour on a throttle instead of only on click, and move the dashed line and distance label to
the new neighbour when it changes. It must follow the *displayed* time: real-time throttle in
Live (about once per second at 1x, and no slower in sim terms at higher speeds, so at 50x it
refreshes by sim time, not just wall time), and re-run on every scrub or step in historical/paused
modes. Measure the cost of one full-catalog scan first (it is one propagation per object); if it
cannot run about once a second without hurting frame time, use a candidate-set approach (keep the
closest few hundred objects from a periodic full scan and re-rank only those between scans), and
say which was chosen and why. Remove the "Refresh" link and the "found at the moment you clicked"
note; the panel should say the neighbour is live.

**2. Hidden objects.** The search currently counts objects hidden by filters, so the line can end
at an invisible dot. Decision: the neighbour search considers only currently visible objects, so
the line always ends on something on screen. If no visible neighbour exists, show nothing rather
than a far one. (If this reads badly in testing - e.g. "nearest" changing as filters change - note
it; it is deliberate.)

**3. Playback speeds become 1x, 10x, 50x** (was 1x, 2x, 5x, 10x): change `SPEEDS` in
`globe/clock.ts` and anything that assumes the old set (default, labels, tests, the offset label
in `SatelliteGlobe.tsx`). Check that 50x does not break the neighbour refresh above, the near-miss
and station follow views, or the Live/time-slider offset display. No change to the slice=10
propagation rule.

Acceptance: pick several random objects, play at 1x/10x/50x for a minute, and confirm by script
that the displayed neighbour matches an independent brute force at the displayed time (allowing for
the throttle), with no page errors and lint/typecheck/tests/build clean.

**2026-10-03 - Globe Phase 1c fix round done; zoom floor confirmed working.** Per the fix-round
entry below (`portfolio-site` `fix/satellite-globe-phase-1c-feedback`; details in
`docs/sessions/2026-10-03-globe-phase-1c-fix-round.md`):
- **Zoom floor:** measured at 1.1000 R on wheel, trackpad pinch and touch pinch, since
  TrackballControls clamps every zoom path in one place. Production had deployed it (`1abb50b`,
  globe chunk `SatelliteGlobe-Bo_5C-dv.js`). Likely a cached bundle or a focus-mode test.
- **Selection is one state.** Object, pair and station are mutually exclusive. A pick replaces
  the current selection and an empty click clears it, with the camera easing out of a focus
  rather than jumping. The pick radius dropped from 10 to 6 px, since 10 px hit something on
  about 80% of disc clicks.
- **Filters:** the collision buttons toggle (restoring the prior view), and an always-visible
  "Showing N of M · Show all objects" bar covers both filter entry points.

**2026-10-03 - Globe Phase 1c fix round: visibility reset, nearest-neighbor line, single-select,
zoom-floor verification.** Follows Max testing the merged Phase 1c live. Four issues, scoped for a
follow-up branch - none touch orientation/propagation.

**1. No way back to "show all" after isolating an incident's debris.** The collision-history
panel's per-event "show only this debris" buttons (`CollisionHistory.tsx`) leave no path back to
full visibility - confirmed by Max, not a maybe. Fix: either make the button a toggle (clicking
the active one again restores the prior view), or route it through the same visibility state the
name-filter panel's "Show all" control already clears (`globe/groups.ts`) rather than a separate
mechanism. Either way, there must always be an obvious, working way back to showing everything
after using *either* filter entry point.

**2. Nearest-neighbor needs the same dashed line the near-miss replay already has.** This is a
gap in the Phase 1c scoping entry, not an implementation bug - that entry only asked for the
distance to appear in the inspect panel's text (`globe/neighbors.ts`), not the visual connection.
It should get the same treatment Phase 1b built for near-miss replay: a dashed line between the
selected object and its nearest neighbor, labeled with the distance. Reuse that existing line/label
component rather than building a second one.

**3. Selection needs to actually be single-select.** Right now (per Max) it's possible to end up
with more than one object looking selected, clicking empty space does nothing, and there's no
explicit way to clear a selection. Required behavior:
   - Selecting a new object always replaces any previous selection - never additive.
   - Clicking anywhere that isn't an object (not a drag) clears the current selection.
   - The inspect panel gets an explicit deselect/close control, for discoverability and for
     mobile, where an empty-space tap is easy to confuse with a camera drag.

**4. Zoom floor change doesn't appear to have taken effect.** The reported change (1.15 -> 1.10
Earth radii, roughly 955 km -> 637 km above the surface) is large enough that it should be
obviously noticeable, not subtle - so something likely isn't taking effect rather than this being
a perception issue. Check, in order: (a) whether the deployed production bundle actually contains
the change (Vercel auto-deploys on merge to `main`, but confirm the live bundle's hash/build time,
not just that the PR merged) and whether a stale browser cache is masking it - have Max hard-reload
after confirming the deploy; (b) whether the new floor is wired to *every* zoom input path (mouse
wheel, trackpad pinch, and touch pinch may be separate code paths in whatever controls library is
in use - a fix applied to one path and not the others would look exactly like "nothing changed" to
someone testing with a different input method); (c) whether Max was actually testing free-roam
zoom and not the replay/station-follow zoom, which already goes much closer (~2 km) via a separate
path and was unaffected by this change by design - rule this out before assuming the fix itself is
broken.

**Branch:** a fresh branch in `portfolio-site` (e.g. `fix/satellite-globe-phase-1c-feedback`),
separate from the merged Phase 1c branch.


**2026-10-03 - Globe Phase 1c built; two catalog corrections and the zoom floor.** Per the Phase 1c
entry below (`portfolio-site` `feat/satellite-globe-phase-1c`; details in
`docs/sessions/2026-10-03-globe-phase-1c.md`):
- **ISS = 5 pieces, not 13.** The `ISS (` modules are co-located. The other 8 substring hits
  were unrelated names and four `ISS OBJECT`s flying freely 7,500-11,000 km away.
- **Fengyun-1C debris uses `FENGYUN 1C DEB`** (1,940), since the `FENGYUN` prefix includes 14
  working weather satellites.
- **Free-roam zoom floor is 1.10 Earth radii (~640 km).** At 1.06 the centre-facing camera sat
  beneath the LEO shell and saw almost nothing. Close-ups come from replay and station views
  (~2 km); "zoom to / follow this object" from the inspect panel is a natural follow-up.
- **Name filters:** every verified constellation of roughly 150+ objects, plus NAVSTAR and the
  two historical debris groups.

**2026-10-03 - Globe Phase 1c scoped: curated object/keyword filters, real-collision-history
panel, deeper zoom, nearest-neighbor-on-select.** Follows Max reviewing Phase 1b live. Replaces
the originally-floated free-text search bar with curated filters per Max's call - deterministic,
explainable, no AI, and reuses the visibility-toggle mechanism already built for the type/owner
legend in Phase 1b.

**Verified against the live catalog (19,246 objects, 2026-10-03) before writing this, not
guessed:**
- `ISS` matches 13 separate tracked pieces (`ISS (ZARYA)`, `ISS (UNITY)`, `ISS (ZVEZDA)`, etc.) -
  it's one station but many catalog entries.
- `HUBBLE` substring-matches 4 objects, but the real Hubble Space Telescope (`HUBBLE SPACE
  TELESCOPE`) isn't in this catalog at all (0 matches) - the hits are unrelated cubesats named in
  tribute (`LEMUR-2-HUBBLE-4` and similar). **Don't offer Hubble as a filter.**
- `TIANGONG` isn't the catalog name, but China's station is there as three modules: `CSS
  (TIANHE)`, `CSS (WENTIAN)`, `CSS (MENGTIAN)` - same multi-piece pattern as ISS.
- `STARSHIP` has zero matches - not in this catalog's scope (active + the three debris groups).
  **Don't offer it.**
- Top name-prefix counts: STARLINK 11,152, FENGYUN 1,954, COSMOS 721 (of which `COSMOS 2251 DEB`
  specifically is 576), ONEWEB 651, KUIPER 391, QIANFAN 257, HULIANWANG 191, IRIDIUM 188 (of which
  `IRIDIUM 33 DEB` specifically is 107), YAOGAN 169, NAVSTAR 39 (this catalog's GPS constellation -
  literal "GPS" doesn't appear in any name).

**What this phase adds:**
- **"Objects of interest" filter: ISS and CSS (China's station) only.** Both verified present and
  correctly named above. Selecting one should fly to / highlight all of that station's tracked
  pieces together, not just one - Claude Code's call on the exact camera/selection behavior for a
  multi-piece object, same kind of open decision as Phase 1b's owner-coloring cutoff.
- **Keyword filters, by verified name prefix.** Reuse Phase 1b's per-category visibility-toggle
  mechanism, keyed on name prefix instead of type/owner. Suggested starting set, highest-value
  first: Starlink, OneWeb, Kuiper (the three largest active constellations), `COSMOS 2251 DEB`
  and `FENGYUN 1C DEB` specifically (the two real historical events below, not generic
  "Cosmos"/"Fengyun"), Iridium (active) vs. `IRIDIUM 33 DEB` kept separate, NAVSTAR. Claude Code
  decides the exact cutoff and whether smaller constellations (Qianfan, Hulianwang, Yaogan) are
  worth including - same kind of call as the owner-coloring "top N + other" decision in Phase 1b.
- **Real-collision-history panel**, researched and sourced, not guessed:
  - Feb 10, 2009, Iridium 33 / Cosmos 2251: ~780 km altitude, nearly right angles, over northern
    Russia - the first confirmed accidental collision between two intact satellites in history.
    598 Iridium 33 fragments and 1,603 Cosmos 2251 fragments were catalogued as of 2012; today's
    live catalog shows 107 and 576 respectively (the rest have decayed) - tie this panel's copy
    to the tool's own live counts for `IRIDIUM 33 DEB` / `COSMOS 2251 DEB` rather than hardcoding
    the 2012 numbers as current.
  - Jan 11, 2007, Fengyun-1C ASAT test: a **deliberate** Chinese missile test, not a collision -
    word this distinctly from the 2009 event. 860 km altitude, originally >3,000 trackable
    fragments; today's catalog shows 1,954 under the `FENGYUN` prefix.
  - Framing: exactly one confirmed accidental satellite-satellite collision has ever happened,
    against the thousands of heuristic near-misses this tool flags routinely - context for what
    the risk tiers actually mean (a stated heuristic, not a collision probability, per the
    existing page copy).
  - Sources: [CelesTrak's own collision page](https://www.celestrak.org/events/collision/),
    [Wikipedia: 2007 Chinese anti-satellite missile test](https://en.wikipedia.org/wiki/2007_Chinese_anti-satellite_missile_test).
- **Deeper zoom.** Raise the camera's minimum distance limit so users can get closer than Phase
  1's floor allows. Claude Code picks the new floor - avoid near-plane clipping or point-size/LOD
  breakdown at the new closest zoom, don't just set it to an arbitrarily small number.
- **Nearest-neighbor distance on click-to-inspect.** When any object is selected, compute the
  distance from it to every other currently-tracked object at that same displayed moment and show
  the minimum in the inspect panel (alongside name/type/owner/position already there). This is a
  one-off calculation triggered by the click, not a per-frame cost - comparing one object against
  ~19,246 others once is trivial, nothing like the per-frame propagation budget Phase 1's spike
  was about. Use a fresh, non-stale propagation of all objects to the exact selected moment for
  this specific calculation, since the frame-sliced positions used for rendering can be up to
  ~9 frames stale for any given object.

**Branch:** a fresh branch in `portfolio-site` (e.g. `feat/satellite-globe-phase-1c`), separate
from the merged Phase 1/1b branches.


**2026-10-03 - Globe Phase 1b built; implementation choices.** Per the Phase 1b entry below
(`portfolio-site` `feat/satellite-globe-phase-1b`; details in
`docs/sessions/2026-10-03-globe-phase-1b.md`):
- **Both objects marked:** Phase 1 already ringed both, but identically, and flagged pairs are
  usually sub-pixel apart. The pair now gets two colours and sizes, read as concentric rings.
- **Miss line:** drawn in 3D. Replay can zoom to about 2 km so multi-km lines are visible; the
  on-screen label carries the distance at normal zoom.
- **Picking:** nearest visible point within 10 px (20 px on touch), skipping points behind the
  Earth or the camera.
- **Live speed:** re-anchors on change, so it never jumps, and the readout says when Live is
  running ahead of real time.

**2026-10-03 - Globe Phase 1b scoped: color-category toggles, playback speed control,
near-miss distance callout, click-to-inspect any object.** Follows Max reviewing Phase 1 live on
localhost. All four are additions to the already-shipped and -verified globe (orientation,
propagation and the core camera/data pipeline are untouched) - small, independent, and don't need
to reopen the work that got the careful coordinate-frame verification.

**What this phase adds:**
- **Toggle color categories on/off.** Within whichever coloring mode is active (type or owner),
  each legend swatch gets a checkbox that hides/shows that category's points. Doesn't apply to
  flat mode (nothing to toggle there). This doubles as a cheap filter UI using data already on
  the page - it's not the deferred "true operator filtering" (still blocked on the GCAT join),
  since it filters on the existing `object_type`/`satcat_owner` buckets, not real
  operator-company names.
- **Playback speed control (1x/2x/5x/10x).** A multiplier on how fast simulated time advances
  **during Live playback only** - scrubbing the date slider to a specific point stays a direct
  jump to that moment, unaffected by speed. Default stays 1x, matching the 2026-10-03 "real-time
  by default" decision; this just adds an optional way to see motion faster, it doesn't change
  what a first-time visitor sees.
- **Near-miss replay: highlight both objects, plus a labeled distance line.** Confirm first
  whether Phase 1's "rings it" already marks both objects in the pair or only one (the write-up
  was ambiguous) - fix if it's only one. Add a dotted line between the two objects at the frozen
  TCA moment, labeled with that conjunction's `miss_distance_km` (already in the report, no new
  data needed).

- **Click-to-inspect any object, not just near-miss pairs.** Clicking any of the 19,240 points
  opens the same kind of info panel the near-miss click already shows - name, `norad_id`,
  `object_type`/`active_payload`, `satcat_owner`, and the object's current propagated position
  (lat/lon/altitude) at whatever moment the globe is showing. Most objects have never been in a
  flagged conjunction, so this panel's content is necessarily different from the near-miss one
  (no pair, no miss distance) - same visual treatment, not the same data shape.
  **Implementation note, not a requirement:** picking one point out of 19,240 with a raycast needs
  a screen-space pixel threshold (e.g. nearest point within N pixels of the click), not a fixed
  world-space distance - a world-space threshold gets easier to hit when zoomed in and nearly
  impossible when zoomed out, which is the wrong behavior. Claude Code's call on the exact
  approach and threshold.

**Branch:** a fresh branch in `portfolio-site` (e.g. `feat/satellite-globe-phase-1b`), separate
from the merged Phase 1 branch, per the usual small-PR discipline.


**2026-10-03 - Globe Phase 1 built; implementation-time decisions.** Built per the Globe build
plan below (`portfolio-site` `feat/satellite-globe`; details in
`docs/sessions/2026-10-03-globe-phase-1.md`). Choices the plan left open:
- **Owner colouring is the top 3 plus Other** (US, China, CIS: 89% of objects), keyed by owner
  code, not rank. On a scatter every colour must separate from every other, and the dataviz
  validator fails every four-hue set against the dark globe background.
- **Past days' near misses are summarized server-side** (`/api/satellite/summary?date=`) rather
  than parsing a 78 MB decompressed report in the browser.
- **Vercel preview origins aren't in the bucket's CORS rule,** so previews can't load the globe.
  That's an open review decision.

**2026-10-02 - 7-day dated snapshot retention: ADR 0011 written and implemented.** This is the
prerequisite the Globe build plan amendment set for the time slider's backward range. Each daily
run now also writes `objects/<date>.json.gz` and `reports/<date>.json.gz`, plus a
`history/index.json` of the dates that have both. `<date>` is the run window's UTC date.
- **Encoding:** gzipped, served with `Content-Encoding: gzip`. The report uses level 6 (5.3 MB
  instead of 78 MB).
- **Pruning:** keys dated more than 7 days before the run's date are deleted, so up to 8 dates
  per prefix exist at once and a full 7-day drag always lands on a stored date.
- **Choices this session made that the plan didn't specify:**
  - **The index.** The frontend learns which past dates exist without bucket listing, and gaps
    from skipped runs show up as gaps.
  - **Pruning in code rather than a bucket lifecycle rule.** Expiry is by snapshot date, not
    object age.
  - **A retention failure doesn't undo the publish.** The run logs `retention_error` and exits
    non-zero.
- **Measured:** about 55 MB at most in the bucket, free on Tigris. Peak memory moved from 2.87 GB
  to 2.88 GB.
- **Not yet deployed:** see the to-do list.

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
