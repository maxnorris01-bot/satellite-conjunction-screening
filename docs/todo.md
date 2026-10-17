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

- [ ] **Review the proposed bucket CORS change so Vercel previews can load data** (proposal in the
      2026-10-13 working-notes entry; branch `fix/bucket-cors-previews`; nothing applied).
      - [x] 2026-10-13: live rule read back; preview-style origins confirmed rejected (no header,
            preflight 403); Tigris docs checked; proposal, commands and rollback written.
      - [ ] Max: review the rule (one added origin, `https://portfolio-site-*-max-norris.vercel.app`).
      - [ ] Max: step 0, the scratch-bucket test, because Tigris's docs don't say whether a `*`
            inside an origin works. Don't apply to the real bucket if it over-matches.
      - [ ] Max: step 1, apply to the real bucket; step 2, run the verification matrix.
      - [ ] After applying: update ADR 0010's "Bucket CORS" watch item and the 2026-10-12 note.
      - If wildcards aren't supported: pick an alternative from the entry's table (stable branch
        alias, per-branch origins, a proxy for the small artifacts).

- [ ] **Redeploy the daily-run image so `objects/current.json` gains `international_designator`**
      (after `feat/objects-international-designator` merges). Merging doesn't change the daily
      run: GitHub Actions starts a Fly Machine from an already-deployed image.
      1. From up-to-date `main`: `make fly-build`, then
         `make fly-update FLY_MACHINE_ID=1850e47cdd43e8`. This changes only the image; no
         schedule is added (ADR 0012).
      2. Verify with `gh workflow run daily-run.yml` (blocked for 2 h after the last publish), or
         let the next scheduled run do it. Its cron is 10:17 UTC, but runs have started around
         16:45 UTC.
      3. Check that `objects/current.json` has `"international_designator": "1998-067A"` for
         NORAD 25544. Commands are in `docs/sessions/2026-10-06-objects-international-designator.md`.

- [x] **Upload the Gaia G<13 star data** 2026-10-16: uploaded to `stars/v1/` (1,539 files, after
      the glow atlas 4:4:4 fix, PR #64). The viewer round shipped in `portfolio-site` PRs #30 to #34
      (stars, selection, constellations, streamed Gaia stars, glow, sky dimming); see
      `docs/sessions/2026-10-16-space-view-round.md`. Still open: the CORS change for previews
      (first item above) and the real-GPU frame-rate check with ~1M stars.

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
      filtering (blocked on the GCAT join, its own to-do item above), sky-view pass predictions
      and naked-eye visibility (the basic Sky view is scoped, see above; the darkness/sunlit test
      it needs is part of future feature 3 below), and the satellite-POV camera view (merged into
      future feature 4 below).
      Each needs its own Cowork scoping session once Phase 1 is live and reviewed.

- [ ] Sky view depth ideas offered but not chosen (2026-10-04): sky gradient and horizon haze,
      distance-based point size/brightness, short motion trails, a faint background star field.
      Revisit if the sky view still feels flat after the lighter ground.

### Future features (brainstorm, ordered)

Brainstormed and ordered 2026-10-06, **not scoped or committed to** (see that day's working-notes
entry). Each needs its own scoping before any build.

1. [x] **Orbit line for the selected satellite.** Done 2026-10-06, Globe and Sky; see Completed.
       (The number is kept so the references to items 3 and 4 below still hold.)
2. [x] **Satellite age.** Age colour mode done 2026-10-07; see Completed. (The number is kept
       so the references to items 3 and 4 still hold.)
       - [ ] **Follow-up: a launch-year range filter** (part of the original idea, left out of the
             Age commit on purpose). Possible shape: a two-handle year range in the legend under
             the Age buckets, hiding objects outside it through the existing filter path, with
             Unknown objects hidden or shown by their own checkbox. Exact launch dates would
             still need the GCAT join (item above).
3. [x] **Day/night on the globe, matching the displayed time.** Done 2026-10-07 (globe shading
       with city lights, plus Sky twilight and a sun marker); see Completed. Follow-ups, not built,
       all to reuse `sunDirectionEci` / `sunElevationDeg` in `portfolio-site` `src/globe/sun.ts`:
       - [ ] A "sunlit vs in Earth's shadow" satellite state (an exact calculation).
       - [ ] "Visible from your location tonight" logic (observer in darkness, satellite sunlit).
             This is the test the deferred naked-eye visibility item above needs.
       - [x] Sky sun/moon extension: done 2026-10-09 as Sky planets and Moon (all seven planets,
             the Moon with its phase, the Sun clickable); see Completed. The Sun/Moon on the
             globe view is not done.
       - [ ] Physical visibility for sky bodies and satellites: hide or fade what can't be seen
             (a planet in daylight, a satellite in Earth's shadow). Today everything above the
             horizon is drawn.
       - [ ] Star field and constellations on the Sky dome (with labels for the brightest stars
             and constellation lines), sharing the planets' label placement.
4. [ ] **Satellite's-eye view (POV) and space view, as one feature** with look-direction modes:
       down at Earth, forward along the track, outward at space. The camera sits at the satellite,
       oriented from its velocity vector; zoom is field of view. This is the deferred
       satellite-POV view above, merged here.
       - [x] **First version, 2026-10-10** (`portfolio-site` `feat/satellite-pov`, pending
             review): the camera and presets, other satellites removed, NASA GIBS day tiles
             following the slider date, soft tile edges. See Completed and the 2026-10-10
             working-notes entries (it became a Google Earth-style view).
       - [x] **Next round, decided 2026-10-10; built 2026-10-11** (`portfolio-site` PR #27,
             `07d0a75`; see `docs/sessions/2026-10-11-descend-zoom.md`):
             - [x] descend zoom: zoom descends toward the surface;
             - [x] the camera detaches and holds over that ground spot until "Return to satellite"
                   (on zooming past 30 degrees or a double-click/double-tap; a drag while riding
                   still looks around, see the working notes);
             - [x] zoom toward the cursor (scroll/pinch);
             - [x] double-click/double-tap zoom, animated;
             - [x] animated transitions (500 ms, instant under reduced motion);
             - [x] smooth imagery limit (the base imagery is now EOX, not GIBS).
       - [x] **Pause button** (`8897c0c`, PR #27): Pause/Play for the shared clock; Play resumes
             the paused moment, not Live; Space toggles.
       - [x] **Prominent Today's imagery control** (`c188ce9`, PR #27): "Base map | Today's
             imagery" with an explanation and the imagery date; fades out between ~263 and
             ~131 km camera height.
       - Follow-ups from the descend and orientation rounds (2026-10-11):
             - [ ] **Softer detach swing:** detaching from Forward or a sideways look still swings
                   a lot.
             - [ ] **Return restores the previous field of view:** it comes back at 30 degrees,
                   not the starting 70.
             - [ ] **Wheel steps on notched mice** aren't animated.
             - [ ] **Soft imagery below about 10 km** camera height.
             - [ ] **About 13 wheel steps from GEO to the floor:** too many.
             - [ ] **North up while riding:** dragging to look around is off by the roll angle.
             - [ ] **Detaching from Forward changes the compass by about 17 degrees,** because the
                   tilt can't carry into a straight-down view.
             - [x] **Show the Today's imagery explanation on phones:** done 2026-10-12. It's
                   shown in full screen (`portfolio-site` PR #29, `e0fbdf3`).
       - [ ] **Night-lights tiles** (VIIRS Black Marble from GIBS) in place of the 2K night
             texture.
       - [ ] **Star field** behind the Earth. Check the catalog's source, license and size with
             Max before committing any data file. It's shared with the Sky dome star-field item
             above.
       - [ ] **Planets and the Moon seen from the viewpoint** (reuse `src/globe/planets.ts`), with
             no "inspect others".
       - [x] **Higher-resolution close-up imagery.** Done 2026-10-11: EOX Sentinel-2 cloudless
             2016 (CC BY 4.0) is the base surface at every zoom, down to ~9.6 m per pixel; GIBS
             daily is the optional "Today's imagery" overlay. See Completed and
             `docs/sessions/2026-10-11-eox-base-imagery.md`. Follow-ups:
             - [ ] **EOX coastal-water seams:** blocky patches and straight diagonal lines in the
                   sea near coasts (Sentinel-2 scene edges in EOX's 2016 mosaic, not our tiles).
                   Options: fade EOX out over open water, or blend toward the 2K texture's ocean.
             - [ ] **Near the poles** the geographic grid's tiles narrow, so the 140-tile budget
                   stops at levels 11-12 (at 81 N, FOV 1 degree) instead of 13. A latitude-aware
                   budget or level choice would fix it.
             - [ ] **Frame rate:** about twice as many (smaller) tiles are drawn as with GIBS
                   alone; software-GL fps at medium zoom went 12.8 -> 9.3-9.8. Check on a real
                   GPU; merge small tiles or raise the texel target if needed.
             - [x] **Attribution wording:** done 2026-10-11 (`1357cdf`, PR #27). The footnote now
                   uses EOX's current wording, "EOxCloudless https://cloudless.eox.at by EOX IT
                   Services GmbH (Contains modified Copernicus Sentinel data 2016)".
       - [x] **Phone layout rework:** done 2026-10-12 (`portfolio-site` PR #29, `e0fbdf3`). The
             embedded phone map is clean, and details and controls live in a full-screen mode
             (bottom sheet, folded filters). See `docs/sessions/2026-10-12-fullscreen-map.md`.
       - [x] **Sideways scroll on phones:** done 2026-10-12 (`b0888ca`, PR #29). The table's
             hidden "Replay" labels widened the page to ~691 px at 390 px, so browsers zoomed out.
             The page is now exactly screen width.
       - Follow-ups from the full-screen round (2026-10-12):
             - [ ] **A compact Globe | Sky | Satellite toggle inside full screen.** It's missing
                   there; switching works from the selection panel.
             - [ ] **Bucket CORS for Vercel preview addresses:** cause confirmed 2026-10-13
                   (the live rule lists only production and localhost, so previews get no
                   `Access-Control-Allow-Origin`); fix proposed, awaiting review. See the Up
                   next item below.
             - [ ] **Detailed real-device checks:** iPhone Safari toolbar and safe-area
                   behaviour; Android Chrome native full screen; rotation in full screen.
       - [ ] **Tilt/rotate** the camera (roll, and an oblique look at the ground).
       - [x] **Orientation option:** done 2026-10-11 (`e3d3667`, PR #28; in `main` via #27,
             `56100cc`). Heading up is the
             default, North up an option, with a compass; held views keep the screen-up ground
             direction from detach.
5. [ ] **Longer conjunction screening window** (about a week), with miss distance and an explicit
       uncertainty note.
       - **Constraint:** predictions from public TLE/GP elements lose roughly a kilometer or more
         per day, so months-or-years-out collision predictions aren't meaningful, and real
         collisions are very rare. Don't promise "will collide" claims.
       - Probabilities would need covariance data from Space-Track, which needs its own ADR
         (a revision to ADR 0001). The Space-Track item above is the related, separate decision.
6. [ ] **Featured satellites.** A curated set of roughly 20-50 well-known objects (ISS, Hubble,
       a GPS satellite, a Starlink and similar) rendered with NASA public-domain 3D models,
       self-hosted with attribution. Not feasible for the whole catalog (most objects are debris
       or unnamed). No runtime hotlinking of web images (licensing and reliability).
7. [ ] **Sky view terrain horizon.** Build a horizon profile from free elevation data for the
       user's location, so terrain hides the sky and any satellite below the skyline. Large; last
       in the order.
       - **Explicitly not doing:** CCTV or webcam feeds (privacy, legality, reliability), or
         photoreal 3D tiles (paid API key, restrictive terms, key exposure in client code).
8. [ ] **Sharper US close-up imagery** (backlog, added 2026-10-11): fade in free USGS National
       Map aerial imagery (~1 m/px, public domain) over the United States at close zoom, allowing
       deeper zoom there. The rest of the world stays at the 10 m Sentinel-2 limit. Needs a
       licence/attribution check, a tile-service endpoint and a US-only coverage mask.
9. [ ] **Zoomable deep-sky backdrop (HiPS), build round** (researched 2026-10-12;
       `docs/research/2026-10-deep-sky-imagery.md`). Before building:
       - [ ] Ask CDS whether a public site may stream alasky tiles, and about any rate limit.
       - [ ] Ask Axel Mellinger for permission to use the panorama on the portfolio, and the credit
             line; otherwise use DSS2 colour plus bright-star points for the wide view.
       - [ ] Confirm the portfolio counts as non-profit use for DSS2 (MAST copyrighted collection).

       Then build:
       - [ ] Per-tile HEALPix quads via `@hscmap/healpix`.
       - [ ] An ICRS → TEME rotation.
       - [ ] DSS2 colour for mid zoom.
       - [ ] HST/JWST outreach layers at named "go to" targets (HUDF, XDF, HDF, SMACS 0723,
             Cosmic Cliffs) with release-page credits.
       - [ ] A phone budget (LRU about 32 tiles; deep layers only at targets).
10. [ ] **Streamed star catalogue (Gaia), build round** (researched 2026-10-14;
        `docs/research/2026-10-streamed-star-catalogue.md`). Before building:
        - [ ] Ask CDS whether a public site may call its TAP, Sesame and HiPS endpoints, and at
              what rate.
        - [ ] Test the point budget on a real phone (the 0.3M figure is an assumption).
        - [ ] Decide the Hipparcos/Gaia handoff (by magnitude or by position match).

        Then build, in order:
        - [ ] A one-off extraction of Gaia DR3 to G<13 (7.4 M stars, about 59 MB packed) into
              progressive HEALPix tiles in the existing 8 B/star layout, plus details files.
        - [ ] Streaming, a per-view magnitude budget by field of view, and selection.
        - [ ] The glow layer from CDS's Gaia colour flux map (order 7, about 74 KB).
        - [ ] The SIMBAD info card (`ident` lookup by Gaia DR3 ID, `basic` table only).
        - [ ] Extend to G<16 (78 M, 624 MB) and add narrow-field live cone queries.

## Lower priority / opportunistic

- [ ] **Dark outline on rings and lines** (2026-10-07). With no dark rim, rings and lines (white
      neighbour line and pair ring, gold ring, cyan ring, orbit line) are 1.0-2.1:1 against the
      brightest city-light cores on the night side, and also against bright clouds and desert on
      the day side (as before day/night). A 1 px dark outline, like the points' rim, would fix both.

- [ ] **Shared colours: green vs grey are weak for colour-blind viewers** (2026-10-07). Rocket
      body / "Over 10 years" `#199e70` vs the shared grey `#8b8f98` is 13.5 normal and 5.1 deutan
      (OKLab x100). A lighter grey (about `#a3a5a7`) fixes that pair but comes within 5.8 of the
      orbit line, so it needs a choice. It's rarely visible in Age (Unknown and the known buckets
      seldom coexist) but affects Type mode.

- [ ] **Time slider: arrow keys don't move it while the clock runs** (found 2026-10-07 in
      `portfolio-site`). Its value is the live, unrounded time and its step is 1 minute, so
      Chromium snaps each key press back to the current minute and the thumb never gets anywhere;
      Home/End did nothing on macOS. Mouse and touch work. Likely fix: give it a step-aligned
      value, or handle the keys itself (e.g. -/+ 10 minutes, Home/End to the range ends).
      Checked 2026-10-08: not the same root cause as the speed bug (that was the clock model;
      this is the input's value/step), so still open; still reproduces after the speed fix.

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
- [x] 2026-10-12 - Full-screen map and the phone page-width fix (`portfolio-site` PR #29, merged
      as `e0fbdf3`):
      - The page is exactly screen width on phones; the table scrolls in its card.
      - A clean embedded phone map, and a full-screen mode with a bottom sheet (side sheet in
        landscape), folded filters and the controls. It's a CSS full-viewport mode, plus native
        full screen where available.
      - 153 tests (7 new). Headless at 390x844, 360x740, 844x390 and desktop. Full screen and
        Today's imagery confirmed by hand on Max's phone. See
        `docs/sessions/2026-10-12-fullscreen-map.md`.
- [x] 2026-10-11 - Satellite view rounds in `portfolio-site`:
      - All merged to `main` as one squash commit, `56100cc` (PR #27). PR #28 was merged into
        `feat/descend-zoom` first, so #27 carried it into `main`.
      - **From #27:** descend zoom with a ground-held view, Pause/Play, the "Base map | Today's
        imagery" control with its fade rule, EOX attribution wording.
      - **From #28** (`e3d3667`, `262399c`): heading-up orientation with north up as an option,
        and closest zoom 10.27 km desktop / 19.26 km phone.
      - 146 tests. Real-GPU frame rate and touch still to check by hand. See
        `docs/sessions/2026-10-11-descend-zoom.md`.
- [x] 2026-10-11 - EOX Sentinel-2 cloudless 2016 as the Satellite view's base imagery
      (`portfolio-site` `feat/eox-base-imagery`, merged via PR #26 as `7033220`):
      - One seamless, cloud-free mosaic at every zoom, ~9.6 m per pixel at its finest level
        (desktop level 13, phones 12); the narrowest zoom from the ISS is now the 1 degree floor
        (it was 9.7).
      - NASA GIBS daily is a "Today's imagery" overlay, off by default, with "Daily mosaic;
        swath edges are visible."; credits follow what's on screen.
      - EOX's contrasty rendering calibrated to the 2K texture so deserts don't clip under the
        day/night gain; the shading itself is unchanged.
      See `docs/sessions/2026-10-11-eox-base-imagery.md`.
- [x] 2026-10-10 - Satellite view, first version (`portfolio-site` `feat/satellite-pov`, six
      commits, pending review):
      - Globe | Sky | Satellite toggle; the camera rides the selected satellite (LVLH) with
        Down / Forward / Out presets, drag/arrow-key look and field-of-view zoom.
      - Only the Earth and the Sun are drawn; the catalog is paused while the view is open.
      - NASA GIBS VIIRS NOAA-20 true-colour tiles following the slider date (about 244 m per
        pixel), with the GIBS acknowledgment; offline falls back to the 2K texture.
      - Soft tile edges (cross-fades, feathered seams), cheaper frames, and GIBS's black no-data
        masked so dark water stays real.
      See `docs/sessions/2026-10-10-satellite-pov.md`.
- [x] 2026-10-09 - Sky planets and Moon (`portfolio-site` `feat/sky-planets`, pending review):
      - All seven planets and the Moon on the dome, topocentric, above the horizon only, labelled;
        planets sized by magnitude; the Moon with its phase and lit limb toward the Sun.
      - Planets, Moon and Sun clickable in the shared single selection, with a panel; the Your sky
        panel lists what's up.
      - astronomy-engine, lazy-loaded (22.7 kB gzipped chunk), no physical visibility model.
      See `docs/sessions/2026-10-09-sky-planets.md`.
- [x] 2026-10-08 - Playback speed from any time, and clearer day/night (`portfolio-site`
      `fix/time-speed-and-day-night`, pending review):
      - Speed buttons work from a scrubbed or paused time, not just Live; scrubbing keeps the
        speed; a near-miss replay plays on from its TCA; the selection survives a snapshot change.
      - Day side 1.6x brighter, night floor 8% -> 3%: lit/night luminance ratio 1.55-1.62 ->
        1.95-2.46 in a crowded view.
      See `docs/sessions/2026-10-08-time-speed-and-day-night.md`.
- [x] 2026-10-07 - Day/night (`portfolio-site` `feat/day-night`, pending review), two commits:
      - **Globe:** shaded by the Sun at the displayed time, with a soft +3 to -12 degree twilight
        band, NASA Black Marble 2016 city lights at night, and a Day/night switch (default on).
      - **Sky:** a twilight sky (night, astronomical, nautical, civil, day) with a horizon glow
        and a sun marker; the phase and sun elevation in the Your sky panel. The day sky is capped
        so dots stay legible.
      - **Accuracy:** the sun module (satellite.js `sunPos`) is within 0.012 degrees of
        astronomy-engine over 2026.
      See `docs/sessions/2026-10-07-day-night.md`.
- [x] 2026-10-07 - Orbit lines for pair and station views (`portfolio-site` `feat/age-color-mode`,
      pending review). The conjunctions and Stations lists now draw orbits: both loops for a pair,
      sampled around the closest approach; the station's loop for a station.
      See `docs/sessions/2026-10-07-age-color-mode.md`.
- [x] 2026-10-07 - Satellite Age colour mode (`portfolio-site` `feat/age-color-mode`, pending
      review).
      - Buckets: under 2 / 2 to 10 / over 10 years, plus Unknown. The launch year is parsed from
        `international_designator` (`YYYY-NNNA` only); missing, null or malformed values are
        Unknown.
      - Age is the snapshot's run year minus the launch year (±1 year at the edges, noted in the
        legend).
      - Colours: the shared category colours (first three) and the shared grey for Unknown.
      - Today (2026-10-07): 7,530 / 8,332 / 3,452 / 0. Oldest retained (2026-10-03): 0 / 0 / 0 /
        19,246.
      See `docs/sessions/2026-10-07-age-color-mode.md`.
- [x] 2026-10-06 - Orbit line for the selected satellite (`portfolio-site`
      `feat/orbit-line-and-age`, pending review).
      - One period of the object's own SGP4 track (360 samples), closed loop, centred on the
        moment it was sampled; resampled once the displayed time is half a period away.
      - Pale periwinkle `#b0a8ff`, 2 px wide lines; not dimmed, not frustum-culled, no effect on
        picking. Also in Sky, where the ground hides the part below the horizon.
      - On screen the object sits 0 px from its line; 60 fps at 50x under 4x CPU throttle.
      See `docs/sessions/2026-10-06-orbit-line-and-age.md`.
- [x] 2026-10-06 - Sky polish (`portfolio-site` `fix/sky-polish`, pending review):
      - Screen readers hear only selection changes ("Selected …", "Deselected") and a new
        location; the live az/el/range and above-horizon count are no longer in live regions.
      - Sky on phones: the legend folds to one line, folded by default (was: a selected ring under
        the legend stayed covered, 2026-10-04).
      - The 30°/60° labels move off the geostationary row when it runs along their ring (London,
        Berlin: 30°; around 25° latitude: 60°).
      See the 2026-10-06 "Sky polish" working-notes entry.
- [x] 2026-10-06 - Daily-run workflow runner upkeep (`chore/daily-run-runner-upkeep`):
      - `runs-on` pinned to `ubuntu-24.04` ahead of `ubuntu-latest` moving to Ubuntu 26 on
        2026-10-19.
      - `actions/checkout` bumped from v4.4.0 (node20) to v7.0.1 (node24), pinned to
        `3d3c42e5aac5ba805825da76410c181273ba90b1`, verified against the tag.
      - Token scoping, `persist-credentials: false` and the concurrency group unchanged.
      - Confirmation is one manual run after merge.
- [x] 2026-10-06 - Daily run on GitHub Actions confirmed end to end: manual run green, cooldown
      pre-check fails red and early, scheduled runs 37362248668 and 37498410006 succeeded
      unattended and added dates to `history/index.json`. Scheduled starts landed around
      16:45 UTC, not 10:17 (GitHub best-effort cron). The wrong-machine-id failure case was
      deliberately not tested. See the 2026-10-06 working-notes entry.
- [x] 2026-10-04 - Sky view Phase 1b implemented (`portfolio-site` `feat/satellite-sky-1b`, pending
      review).
      - Globe | Sky toggle in the section heading row; the page owns the mode.
      - Click/tap to select in the dome: 8/8 scripted picks at two observers, az/el matches
        satellite.js to the displayed 0.1 degrees; the selection survives the toggle.
      - Phones: two-line selected-object panel with Details; the side column moves off the ring.
      - 60 fps at 50x with a selection under 4x CPU throttle.
      See `docs/sessions/2026-10-04-sky-1b.md`.
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
- [ ] **Gaia G<16 data round** (about 78 million stars). Two routes: live paging through the archive
      in cells (estimated 11 to 27 hours at the polite rate used for G<13) or the bulk download of
      the Gaia source files (about 0.75 TB, filtered locally). Needs a second, finer tile order.

## Backlog: space view (added 2026-10-16)

Small items, in no priority order. Details in `docs/sessions/2026-10-16-space-view-round.md`.

- [ ] **Deep-sky layer using HST/JWST named targets.** Follow-on to the Gaia stars; see
      `docs/research/2026-10-deep-sky-imagery.md`.
- [ ] **Moon pops off at the horizon without a fade.** Needs a fade.
- [ ] **Night lights blocky below about 80 km.** Seen when low; the streamed Black Marble tiles
      are about 490 m per pixel at their finest level.
- [ ] **Compact view toggle in full screen.** A way to shrink the controls.
- [ ] **Softer detach swing.** Make the camera swing when leaving the riding view gentler.
- [ ] **Return restores the previous FOV.** Return should put the field of view back as it was.
- [ ] **Slider arrow-key bug.** Arrow keys on the slider don't behave correctly.
- [ ] **Drag direction off in North-up while riding.** Drag direction is wrong in that mode.
- [ ] **Possible G<16 Gaia round.** About 78 million stars: 11 to 27 hours of extraction, or the 0.75 TB
      bulk download filtered locally (see the G<16 item above).
- [ ] **US USGS aerial imagery (about 1 m).** Sharper low-orbit views over the US than Sentinel-2.
- [ ] **Spacecraft view beyond Earth.** *Not started, decided later.* The tool has outgrown the
      conjunction premise and could extend to non-Earth spacecraft: Mars and Venus orbiters,
      Sun-centred craft such as Parker Solar Probe and SOHO, JWST at L2, the Voyagers.
      - Trajectory data would come from NASA JPL Horizons or SPICE kernels, fetched by this repo's
        pipeline and published to the bucket; the viewer interpolates position tables (no TLE or
        SGP4 for deep space).
      - The viewer needs a central-body globe per view (public-domain Mars and Moon mosaics, at a
        lower resolution than Sentinel-2; Venus's surface is radar-only).
      - Craft like Voyager have no "down", so they would use free look with the Sun as a star.
      - Cheapest first step: JWST, SOHO, Parker and the Voyagers, which need no new globe.
      - The page and tool name could change; conjunction screening stays as the data-pipeline
        feature.
      - Next step is a research round on Horizons licensing and rate limits, data size and imagery
        availability.
