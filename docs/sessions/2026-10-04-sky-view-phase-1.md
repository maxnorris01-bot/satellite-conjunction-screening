# Session 2026-10-04: Sky view, Phase 1 (portfolio-site)

Implements Phase 1 of the 2026-10-04 "Globe: overhead 'Sky' view scoped (Phase 1 and 1b)"
working-notes entry: location, dome and time.

- **Code:** in `portfolio-site`, on branch `feat/satellite-sky-view`. Three commits, local only and
  not pushed.
- **Not started:** Phase 1b (selection and polish).
- **Untouched:** globe behaviour.

## What changed

- **Toggle and shared state.** A Globe | Sky control sits at the top of the legend panel.
  - **One engine, one WebGL context.** Sky mode adds a second scene and camera that share the
    catalog, the sliced propagation, the colour/filter buffer (so filters, colour modes and dimming
    carry over) and the points material. Nothing is rebuilt and the catalog isn't reloaded.
  - **The clock carries over:** Live, 1x/10x/50x, the slider and historical snapshots all apply.
  - **Switching clears any globe selection** (inspect, pair, station); the Sky view has none in
    Phase 1. Replaying a conjunction from the table while in Sky switches back to the globe. The
    stations row is hidden in Sky.
- **Observer.**
  - **"Use my location":** browser geolocation, with plain messages for denied, unavailable and
    timeout that point to the typed fallback.
  - **"City or address" box:** shows the resolved name and coordinates.
  - **Altitude:** 0, with no elevation lookup.
  - **Privacy:** the coordinates live only in component state. They're never stored, logged or
    sent anywhere; a typed place goes only to the geocoder. A short note next to the controls says
    so.
  - **Panel folds.** Once a location is chosen, the panel folds to a one-line summary (place,
    count, "Change location") so the dome stays visible on a phone. Reopening it shows the
    controls, the resolved place and the note.
- **Geocoder: OpenStreetMap Nominatim.**
  - **Why not Open-Meteo:** both are free, key-less and CORS-enabled (`access-control-allow-origin:
    *`, checked). But only Nominatim resolves addresses: "10 Downing Street London" matched, while
    Open-Meteo's place-name search returned nothing, and the entry asks for city *or* address.
  - **Policy conditions met:** user-triggered searches are allowed. The code sends one request per
    submitted query (no autocomplete), spaces requests at least one second apart, caches results in
    memory only, shows "© OpenStreetMap contributors", and relies on the browser's Referer to
    identify the site.
- **Geometry** (`src/globe/sky.ts`).
  - **Observer frame:** east/north/up on the WGS84 ellipsoid, with the geodetic vertical, rotated by
    the same GMST the globe uses.
  - **Per frame:** each object's sliced position is moved forward by its velocity over its slice's
    staleness, then dotted with the local axes for azimuth (0 = north, clockwise) and elevation.
    That's vector arithmetic over the catalog, not 19,000 look-angle calls. The engine now also
    stores the velocity from the same propagation call.
  - **Why extrapolate:** without it, at 50x each point would jump every 10 frames, by up to several
    degrees overhead.
  - **Below the horizon:** objects sit there under an opaque ground hemisphere, so depth testing
    hides them. Hidden (filtered) objects stay hidden.
  - **Counter:** "N above your horizon" counts shown objects only.
- **Rendering.** An inside-the-sphere camera with the horizon ring, faint 30° and 60° rings, and
  N/E/S/W, ring and zenith labels.
  - **Handedness:** east = +x, up = +y, north = -z, so facing north with up as up, east is on the
    right, as for a person standing there looking up.
  - **Controls:** drag to look (the sky follows the pointer; elevation clamped 0-89°), wheel, ctrl
    or trackpad pinch, or two-finger touch pinch for the field of view (30-100°). The trackball
    controls are disabled in Sky.
- **Initial look:** facing the equator (south from the northern hemisphere, north from the
  southern), with the horizon a few degrees above the bottom edge.
  - **Why this direction:** it's stable and predictable, and it's where the geostationary belt and
    most low-orbit traffic cross the sky. The highest object changes every few seconds, so it would
    make a jumpy starting point.
  - **Deviation from the entry:** "level to the horizon" is read as no roll, with the view tilted up
    so the horizon sits near the bottom rather than at the centre. A level, centred horizon would
    spend half the view on the ground.
- **Empty and error states:** with no location yet, a dark dome with rings and labels and a
  one-line prompt (hidden on a phone, where the panel itself is the prompt). Geolocation or
  geocoder failures say what happened and offer the other route.

## Acceptance

All in `portfolio-site`, headed Chromium on the M5, live data.

- **Unit tests** (`tests/sky.test.ts`, run in `npm test`):
  - **Against satellite.js:** azimuth/elevation/range match its own `ecfToLookAngles` for 5 real
    objects (ISS, Starlink, NAVSTAR, Intelsat, Fengyun-1C debris) from Boulder, Wellington and
    Longyearbyen, within 0.1°.
  - **Synthetic cases:** an observer under each object sees it above 89.9°, and points due north
    and due east give azimuths of 0° and 90°.
  - **Extrapolation:** 5 s stale positions plus velocity land within 0.1° of a fresh propagation.
  - **Orientation:** a scripted projection check that a point a little east of north is right of
    centre, west of north is left, and facing south, west is on the right.
  - **The tests can fail:** mirroring east fails the orientation test, and reversing GMST fails the
    satellite.js and zenith tests.
- **In the running page** (clock frozen at a fixed time):
  - **Geometry:** the dome positions read back for 6 real objects from each of the same three
    observers matched satellite.js computed independently in Node: worst difference 0.0000° over
    18 pairs.
  - **Under an object:** an observer placed under ONEWEB-0302 saw it at 90.000°.
  - **Orientation:** facing north-east, the rendered E label is right of N.
- **Real flows:**
  - **Geolocation granted** (Greenwich, about 1,200 above the horizon), the denied and unavailable
    messages (stubbed, because Playwright can't force a denial), and the timeout message (real).
  - **Real Nominatim requests**, spaced at least a second apart: "Wellington, New Zealand" resolved
    with its coordinates, and a nonsense query got the no-match message.
  - **Filters:** Starlink-only cut the above-horizon count to about 490.
  - **Drag and wheel** changed the look and the field of view.
- **Toggling** 21 times kept the canvas count, WebGL context count and every canvas listener count
  unchanged. (Development StrictMode mounts twice, so the context count was 2 before and after.)
  The colour mode, speed and observer persisted, and an inspected object was cleared.
- **Motion:** at 50x the points visibly cross the sky (up to about 30 dome units in 1 s).
- **Frame time** in Sky at 50x with the full catalog: 16.7 ms mean, p95 17.6, unthrottled; 16.7 ms
  mean, p95 17.6, at 4x CPU throttling.
- **Errors:** none on the page. No horizontal overflow on a phone.
- **Checks:** `npm run lint`, `npx tsc -b` and `npm run build` are clean. `npm test` passes 35/35,
  5 new. The globe chunk is 161.8 KB gzipped (+3.2 KB). The dev hook is absent from the production
  build.
- **Screenshots:** desktop at Greenwich and Wellington, and the phone with controls open and folded.

## Open points

- **Production CORS:** Nominatim and the bucket both allow any origin, so the Sky view works on the
  production alias. Vercel previews still can't load the bucket, as before.
- **Phone layout:** the legend panel still takes the top third of the stage in both views, as it
  does today.
- **Not in Phase 1, per the entry:** pass predictions, visibility, a gyroscope mode, elevation-aware
  observers, a nearest-neighbour line in the sky, and Sky selection (Phase 1b).

## Next commands

```bash
cd ../portfolio-site && git log --oneline main..feat/satellite-sky-view && npm run dev
# open the satellite page, switch to Sky, use your location or type a place
# after review: git push && gh pr create --fill
```
