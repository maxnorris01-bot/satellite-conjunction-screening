# Session 2026-10-11: EOX Sentinel-2 cloudless as the Satellite view's base imagery (portfolio-site)

- **Code:** `portfolio-site`, branch `feat/eox-base-imagery`, one commit, merged via PR #26 as
  `7033220`:
  - `e57c548` feat: EOX Sentinel-2 cloudless 2016 as the satellite view's base imagery
- **Browser checks:** headless Chromium only (Playwright, SwiftShader WebGL), per the headless
  rule.

## Why

The Satellite view drew NASA GIBS's daily VIIRS mosaic.
- **Seams:** its visible seams are scan-swath edges baked into NASA's data, so no blending on our
  side removes them.
- **Resolution:** it stops at ~244 m per pixel, so close zoom is blurry.

EOX Sentinel-2 cloudless 2016 is one seamless, cloud-free global image at ~10 m per pixel, free
under CC BY 4.0. It's now the base surface at every zoom, and GIBS is an optional overlay. Only
the 2016 edition is used: the later editions are CC BY-NC-SA (see
`docs/research/2026-10-close-up-imagery.md`).

## What changed

- **Tile maths:**
  - The GIBS quadtree functions (`gibs.ts`) now take a tile grid; GIBS's is the default, so its
    callers and tests didn't change.
  - `src/globe/eox.ts` defines EOX's `WGS84` grid: 256 px tiles of 180/2^z degrees, 2^(z+1) x 2^z
    of them, origin (-180, 90).
  - It's geographic like the globe mesh (not Mercator), so tiles meet the poles and the 180th
    meridian exactly.
  - Level 13 is ~9.6 m per pixel, the native resolution. `eoxTileUrl` throws for any layer but
    `s2cloudless`.
- **Two layers, one machine:** `EarthTiles` runs one instance per layer (`ImagerySource`), with
  the same LOD selection, LRU cache, concurrency and rate limits, fades and edge feathering.
  - **Base:** EOX. The bundled 2K texture stays underneath as the first paint.
  - **Failed tiles:** not retried for a minute (`FailedTiles`); the nearest loaded ancestor
    stands in (`pickStandIn`), so there are no holes and no request spam.
  - **Backstop requests:** when nothing loaded covers a wanted tile, its ancestor three levels
    up is requested too. Without that, Live playback at close zoom drew nothing (fine tiles left
    the view before they arrived and were cancelled), and the 2K texture showed.
- **"Today's imagery" switch** in the Satellite panel, off by default, kept next to the Day/night
  setting.
  - **On:** GIBS (date following the slider) draws over EOX with its fades and feathering. Its
    black no-data is transparent, so EOX shows through.
  - **Note beside it:** "Daily mosaic; swath edges are visible."
- **Panel line:** "Imagery: Sentinel-2 cloudless, 2016 composite" with the switch off, and
  "Imagery: YYYY-MM-DD (NASA GIBS)" with it on.
- **Footnote credits** (`imagery.ts`):
  - EOX's "Sentinel-2 cloudless - https://s2maps.eu by EOX IT Services GmbH (Contains modified
    Copernicus Sentinel data 2016)" while EOX tiles are on screen.
  - NASA's GIBS acknowledgment only while the overlay is on.
- **Brightness calibration:** EOX's rendering is much more contrasty than the 2K texture the
  day/night shading was tuned on, so its deserts clipped to white under the lit side's 1.6x gain.
  - **Measured** (linear luminance on the level-0 tiles): Sahara mean 0.81 (2K texture 0.34,
    GIBS 0.40); land median 0.079 (2K texture 0.092).
  - **Fix:** a per-source curve k * L^gamma (k 0.455, gamma 0.63), fitted to those two anchors,
    is applied to EOX tiles before shading. The day/night model itself is unchanged; GIBS keeps
    an identity curve.
- **Zoom limit:** now follows EOX: the 1 degree floor from the ISS (was 9.7 degrees), and 15
  degrees if EOX is unreachable.

## Budgets

| | Max level | Tiles cached | In flight | Requests/s | Tiles drawn | GPU (cache full) |
|---|---|---|---|---|---|---|
| EOX desktop | 13 (~9.6 m) | 192 | 6 | 20 | 140 | ~67 MB |
| EOX phone | 12 (~19 m) | 64 | 4 | 10 | 60 | ~22 MB |
| GIBS overlay desktop | 8 | 64 | 6 | 12 | 80 | ~90 MB |
| GIBS overlay phone | 7 | 24 | 4 | 6 | 40 | ~34 MB |

- **While time plays,** EOX keeps a tile for 0.5 s (GIBS 2 s): at the ISS's 7.2 km/s ground
  speed (Live, 1x), that's level 12 on both desktop and phone. When paused it's level 13 on
  desktop and 12 on phones.
- **Live 1x at close zoom** (headless, 10 s): never an empty frame, never the 2K texture; 5-8
  EOX requests/s.

**Typical zoom-in, ISS looking down at San Francisco Bay** (desktop, switch off):

| Field of view | EOX tiles drawn | Levels | New requests | Data |
|---|---|---|---|---|
| 120 degrees | 40 | 2-5 | 43 | 475 kB |
| 30 degrees | 61 | 5, 8 | 58 | 752 kB |
| 1 degree | 58 | 13 | 63 | 733 kB |

- **Nile delta:** about the same (39 / 58 / 75 requests).
- **With the switch on:** GIBS adds 25-30 requests (0.9-1.7 MB) at wide and medium zoom, and
  none at close zoom, where it's capped at level 8.
- **Bundle:** the `earthTiles` lazy chunk grew 8.56 -> 9.52 kB (3.54 -> 3.91 kB gzipped); the
  globe chunk 491.2 -> 492.2 kB (131.4 -> 131.7 kB gzipped).

## Verification

- **Tests:** `npm test` 125/125, including 9 new EOX tests:
  - the grid at every level, with neighbours, the 180th meridian and the poles meeting exactly;
  - URLs that refuse later editions;
  - level selection and caps;
  - stand-in fallback and retry backoff;
  - the switch default and panel line;
  - attribution per layer state;
  - the tone calibration.
- **Checks:** typecheck, lint and build clean.
- **Hairline seams:** with the Earth beneath painted magenta, 0 pixels showed between EOX tiles
  in two places, at FOV 120, 30, 5 and 1 degrees. A control with half the tiles hidden showed
  1.1-1.3 million.
  - **ISS over the 180th meridian** (levels 3-13).
  - **NOAA-20 at 81 N,** with the pole in view at 120 degrees.
- **Screenshots** (headless, in the session scratchpad `shots/eox/`):
  - `after-{sf-bay,nile-delta}-{off,on}-{wide,medium,close}.png`
  - `before-*` from `main`
  - `after-geo-{25,8}-off.png`, `after-geo-8-on.png`, `before-geo-*.png`
  - `after-{antimeridian,pole}-fov{30,1}.png`
  - `after-{phone,desktop}-live-close.png`
- **What it looks like:**
  - **Close (1 degree from the ISS):** dramatically sharper. Alameda's streets, the Oakland
    airport's runways and the marinas are clear; on the Nile delta, a town's street grid, field
    boundaries and an airfield. `main` stopped at 9.7 degrees with a blur.
  - **GEO:** a clean cloud-free disc, with none of the daily mosaic's swath lines and sun-glint
    bands.
  - **Overlay on:** that day's clouds over the same view (the marine layer at the Golden Gate on
    2026-10-08).
- **Where it's still soft or wrong:**
  - **Detail:** imagery ~10 m per pixel, so at the 1 degree floor from the ISS (~12 m per screen
    pixel) it's sharp, but there's no building-level detail; slightly hazy after the tone
    calibration.
  - **Coastal water:** blocky patches and straight diagonal lines near coasts (Sentinel-2 scene
    edges in EOX's 2016 mosaic), visible at medium zoom (FOV ~30 degrees from the ISS) off San
    Francisco and the Nile delta.
  - **Near the poles:** stops at levels 11-12.
  - **Out of date:** the 2016 imagery is ten years old (newer construction is missing), and
    snow and ice are a light grey after calibration.
- **Frame rate** (software GL, relative only): about twice as many (smaller) tiles are drawn;
  SF medium zoom went 12.8 fps (`main`) -> 9.3-9.8 fps.

### Not checkable headless

- Real-GPU frame rate.
- How the fades and Live-mode tile turnover feel in motion.
- Real phones and touch.

## Open questions for review

- **Attribution wording:** the footnote uses the s2maps.eu wording from the brief. EOX's
  capabilities now give "EOxCloudless https://cloudless.eox.at by EOX IT Services GmbH
  (Contains modified Copernicus Sentinel data 2016)", and its licence page says the older
  wording needn't change. Keep one or the other.
- **Coastal-water seams and polar resolution:** follow-ups in `docs/todo.md`.

## Next commands

```bash
cd ~/Desktop/Projects/portfolio-site && git checkout feat/eox-base-imagery && npm test
```
