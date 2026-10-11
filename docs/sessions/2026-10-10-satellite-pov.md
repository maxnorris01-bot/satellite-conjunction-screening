# Session 2026-10-08 to 2026-10-10: the Satellite view (portfolio-site)

- **Code:** `portfolio-site`, branch `feat/satellite-pov`, six commits, local only:
  - `f23981c` feat: satellite view, looking out from the selected satellite
  - `730c683` feat: show only the Earth and the Sun in the satellite view
  - `c657cde` feat: tiled NASA GIBS imagery on the satellite view's Earth
  - `c8d5ebb` fix: soft edges between satellite-view imagery tiles
  - `8f8ae77` perf: cheaper satellite-view frames with imagery tiles
  - `cab28d9` fix: GIBS no-data shows the Earth beneath, dark water stays real
- **Docs:** this repo, branch `docs/satellite-pov`.
- **Browser checks:** headless Chromium only (Playwright, SwiftShader WebGL), per the repo's
  headless rule. Screenshots are on disk (paths at the end).

## Direction change

The first commit built a cockpit-style view from the selected satellite that still drew the
catalog around it. After reviewing it, Max redirected the feature: the Satellite view should feel
like Google Earth seen from the satellite. So commit 2 removed every other satellite from the
view, and commit 3 replaced the soft 2K Earth texture with real daily satellite imagery from NASA
GIBS. The next round (descending zoom, detaching from the satellite and so on) is decided but not
built; see the 2026-10-10 working-notes entries and `docs/todo.md`.

## What changed

- **Commit 1, the view:**
  - **Toggle:** a third view, Globe | Sky | Satellite. Satellite needs a selected object; Back
    returns to the view it came from.
  - **Camera:** a nadir-locked (LVLH) frame with three presets:
    - Down at Earth: up = along-track.
    - Forward along the orbit: up = away from the Earth.
    - Outward at space.
  - **Controls:** drag or arrow keys look around, pitch is limited to 85 degrees, and scroll,
    pinch or +/- zoom the field of view logarithmically.
  - **Propagation:** the viewpoint is propagated exactly every frame, so it never jitters.
  - **Sun:** a disc on the true direction, hidden by the Earth when the satellite is in shadow.
- **Commit 2, only the Earth and the Sun:**
  - No dots, rings, neighbour line or orbit lines.
  - The catalog isn't propagated while the view is open. Leaving propagates everything at once
    and refreshes the nearest neighbour, so the Globe and Sky come back as they were, selection
    included.
- **Commit 3, NASA GIBS day imagery:**
  - **Layer and grid:** `VIIRS_NOAA20_CorrectedReflectance_TrueColor` tiles (EPSG:4326, `250m`
    tile matrix set, 512 px JPEG, levels 0-8, about 244 m per pixel at level 8). Tiles are drawn
    on the rotating Earth with the same day/night shader and night-lights texture.
  - **Date:** the imagery date follows the shared clock. It's the newest complete day on or
    before the displayed date, from DescribeDomains; the panel shows "Imagery: YYYY-MM-DD (NASA
    GIBS)".
  - **Level of detail:** a quadtree selected by screen-space error, with frustum and horizon
    culling, capped at 80 tiles (40 on phones). Detail is capped while playback moves the ground
    fast.
  - **Requests and cache:** an LRU cache, a concurrency cap, a token-bucket request rate, and
    cancellation of tiles no longer wanted.
  - **Zoom limit:** computed from the imagery resolution and the altitude.
  - **Loading:** the tile code is a lazy chunk and makes no requests outside the Satellite view.
  - **Offline:** falls back to the 2K texture with a quiet note.
- **Commit 4, soft tile edges:**
  - **Zoom in:** finer tiles fade in over what was there (300 ms).
  - **Zoom out:** finer tiles stay until the coarser tile has loaded, then fade out over it.
  - **Seams:** edges that meet an older day's copy, a coarser stand-in or a missing tile fade
    over 8% of the tile into what's beneath. The stand-in is drawn beneath such a tile, so
    fallback seams no longer show as hard rectangles.
  - **Reduced motion:** fades are skipped under `prefers-reduced-motion`.
- **Commit 5, performance:**
  - While the tiles cover the view, the 2K Earth beneath is drawn depth-only (it still hides the
    Sun).
  - Tiles read the 2K texture only where they have no data, and the night lights only on the
    night side.
  - At most two tiles are uploaded to the GPU per frame.
- **Commit 6, no-data:**
  - **The bug:** the shader used to swap anything darker than linear 0.012 for the 2K texture.
    That caught 1.5-6.6% of real dark ocean per tile, putting bright Blue Marble patches with
    hard outlines into the Black Sea, the Caspian and the Mediterranean.
  - **The fix:** each tile's exact-black no-data pixels, plus a 2 px compression ring, are now
    made transparent once on load, and the 2K texture blends in by that alpha.

## GIBS findings (verified against the GIBS docs and GetCapabilities)

- **Tile URL:** `https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/{Layer}/default/{YYYY-MM-DD}/250m/{z}/{row}/{col}.jpeg`.
- **Tile grid:** top-left corner at (-180, 90); each tile spans 288 / 2^z degrees; matrices are
  2x1 at level 0 up to 320x160 at level 8. Level 9 returns 400.
- **Format:** JPEG only. A PNG request returns 400, and GetCapabilities lists only `image/jpeg`.
- **No-data:** exact black (0,0,0), seen as the Arctic polar night and the unfinished newest day.
  NOAA-20 has no equatorial swath gaps. The pale bands seen from GEO are sun glint in real data.
- **CORS:** tiles send `access-control-allow-origin: *` and `cache-control: no-store`. A date with
  no imagery returns 404 without the CORS header, so dates are always picked from DescribeDomains
  first.
- **Usage:** no API key. "Bulk download" is more than 1,000,000 tiles in 24 h, which needs 48 h
  notice to GIBS. The docs give no other rate limit.
- **Acknowledgment (in the page footnote):** "We acknowledge the use of imagery provided by
  services from NASA's Global Imagery Browse Services (GIBS), part of NASA's Earth Science Data
  and Information System (ESDIS)."

## Numbers

- **Narrowest zoom:** about 9.7 degrees at the ISS on desktop, 18.1 on a phone, and the 1 degree
  floor at GEO. It's 15 degrees with the 2K texture alone (offline).
- **Caps:**

  | | Max level | Tiles cached | In flight | Requests/s | Tiles drawn |
  |---|---|---|---|---|---|
  | Desktop | 8 | 96 | 6 | 12 | 80 |
  | Phone (under 640 px) | 7 | 32 | 4 | 6 | 40 |

- **Requests per zoom step** (ISS looking down over the Red Sea, 2026-10-08):

  | Field of view | New requests | Data |
  |---|---|---|
  | 120 degrees | 20 | 1,112 kB |
  | 60 degrees | 30 | 986 kB |
  | 30 degrees | 24 | 496 kB |
  | 15 degrees and 9.7 degrees | 0 | cached |

- **Request rate during playback:** 1.2-1.4 requests/s at 1x; 2.8/s at 50x, with detail capped
  at levels 4-5.
- **Frame rate** (software WebGL, comparison only; ISS Down at 60 degrees):

  | Playback | Before commits 4-6 | After |
  |---|---|---|
  | 1x | 9.3 fps | 14.0 fps |
  | 50x | 9.4 fps | 11.4 fps |

  - Frozen time also improved: GEO at 8 degrees went 9.4 -> 10.5 fps, ISS at 30 degrees 11.9 ->
    13.6.
  - Draw calls are unchanged (37 at ISS 60 degrees, 36 at GEO 8 degrees). Parents were already
    dropped once all their children loaded.
- **Bundle:** the lazy `earthTiles` chunk is 8.6 kB (3.5 kB gzipped). The globe chunk is 488 kB
  (130 kB gzipped).

## Verification

- **Tests:** `portfolio-site` `npm test` 108/108. That includes 13 GIBS tests:
  - tile index and lat/lon conversion, including the antimeridian and the poles;
  - level selection and the visible set;
  - date fallback, URL construction and LRU eviction;
  - edge feathering and the no-data mask.
- **Lint, typecheck and build:** clean.
- **Coastlines:** tiles line up with the 2K texture to about 13 km, under one 2K pixel, so the 2K
  reference limits the check. Placement uses the same lat/lon mapping as the 2K sphere.
- **Hairline gaps:** with the Earth beneath painted magenta, 0 magenta pixels showed between
  tiles. That held at the ISS (120, 60, 30 and 10 degrees, and Forward at 90) and at GEO (25 and
  8 degrees). A control with half the tiles hidden showed 426k.
- **Fades** (per-frame tile state over 6 s):
  - **Zoom in:** fade-in frames present.
  - **Zoom out:** fade-out frames present.
  - **Date swap:** fade-in frames present.
  - **Coverage:** no frame drew fewer than 9 tiles.
  - **Reduced motion:** no fade frames at all.
- **Seams:** a date seam was forced by failing half of the new day's tiles in a checkerboard.
  Before, it showed hard rectangles; after, soft transitions with no outlines. A level seam
  (half the finest tiles failing) was soft before and is unchanged in character.
- **No requests** to GIBS before entering the view or after Back. No page or console errors.

### What headless couldn't check

- Real-GPU frame rates: SwiftShader numbers are only relative.
- The feel of the 300 ms fades in motion (only frame counts and stills were checked).
- Touch gestures on a real phone.

## Choices made mid-session

- **The direction change above,** from Max's review of commit 1.
- **Layer: VIIRS NOAA-20 over SNPP and MODIS Terra,** for daily continuity.
- **Imagery date skips the layer's newest listed day,** which is still mostly black while it
  fills in.

## Open questions for review

- **Close-up softness:** at the narrowest zoom from the ISS the imagery is soft (244 m per
  pixel). Sharper imagery is a to-do item (Sentinel-2 cloudless or other layers), pending a
  license and usage check.
- **Phone layout:** the panels cover much of the view on a phone (a to-do item).
- **VIIRS swath boundaries:** occasional diagonal lines where clouds moved between overpasses.
  They're in the source data, not tile seams.

## Screenshots (headless)

All under the portfolio session's scratchpad `shots/` folder:
- **Commit 3:** `tiles-iss-down-{120,60,30,15,10}.png`, `tiles-iss-down-60-2k-only.png`,
  `tiles-iss-terminator-{forward,down}.png`, `tiles-geo-down-2026-10-0{5,8}.png`,
  `tiles-geo-down-8.png`, `tiles-phone-narrow.png`.
- **Commits 4-6:** `edges/edges-{before,after}-{iss-60,iss-30,geo-25,geo-8,geo-north,dateseam,dateseam-crop,levelseam,levelseam-crop}.png`,
  and the crops `edges/crop-{before,after}-north.png` (the dark-water fix).

## Next commands

```bash
cd ~/Desktop/Projects/portfolio-site && git checkout feat/satellite-pov && git log --oneline main..HEAD
```
