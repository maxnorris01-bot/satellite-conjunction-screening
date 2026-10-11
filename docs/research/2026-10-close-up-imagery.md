# Research: sharper close-up Earth imagery for the Satellite view (2026-10-10)

**Status:** research only. Nothing here has been added to `portfolio-site`, and no imagery is
committed.

**Why:** the Satellite view draws NASA GIBS
`VIIRS_NOAA20_CorrectedReflectance_TrueColor` (about 244 m per pixel at its finest level).
Zoomed in from the ISS it looks blurry, and Max wants a Google Earth-style close-up.

**Sources checked on 2026-10-10:**
- GIBS `epsg4326/best` GetCapabilities (5.3 MB, `access-control-allow-origin: *`).
- The GIBS API docs.
- The NASA HLS data-products page and the HLSS30 v2.0 catalog entry.
- NASA CMR granule search.
- EOX's WMTS GetCapabilities, and EOX's License Summary and Pricing pages.

**Sample imagery** (crops and raw tiles) is on disk, not in git:
- `~/Desktop/Projects/imagery-research-2026-10/crops/`
- `~/Desktop/Projects/imagery-research-2026-10/tiles/`

## 1. NASA GIBS layers sharper than 250 m

GIBS serves its 30 m layers in the **`31.25m` tile matrix set**:
- CRS84, 512 px tiles, with the same 288-degree grid as the `250m` set the app already uses.
- Levels 0-11. Level 11 is 2560 x 1280 tiles of 0.1406 degrees, about **30.6 m per pixel**,
  so the current tile maths extends to it unchanged.
- No finer true-colour set exists. `15.625m` is used only for reference overlays (coastlines,
  labels, graticule) and NISAR radar.

| Layer | Native res. | Coverage | Time | Dates in GetCapabilities | Format | CORS |
|---|---|---|---|---|---|---|
| `HLS_S30_Nadir_BRDF_Adjusted_Reflectance` (Sentinel-2A/B/C MSI) | 30 m | Land only, global except Antarctica; patchy per day | Daily granules | 2015-11-28 to 2026-10-08, in 13 ranges with gaps of a few days | PNG, transparent no-data | `*` |
| `HLS_L30_Nadir_BRDF_Adjusted_Reflectance` (Landsat 8/9 OLI) | 30 m | Same | Daily granules | 2013-03-22 to 2026-10-08, in 12 ranges | PNG, transparent no-data | `*` |
| `Landsat_WELD_CorrectedReflectance_TrueColor_Global_Annual` | 30 m | Global land | Annual composite | **1984-1986, 1989-1991, 1999-2001 only** | JPEG | `*` |
| `Landsat_WELD_CorrectedReflectance_TrueColor_Global_Monthly` | 30 m | Global land | Monthly composite | 1984-1986, 1989-1991, 1998-2001 only | JPEG | `*` |

Other 30 m layers in GIBS are thematic, not true colour: OPERA surface water and disturbance,
ASTER/SRTM relief, and Landsat built-up extent.

### HLS (Harmonized Landsat Sentinel-2)

- **Coverage, from hls.gsfc.nasa.gov:**
  - "HLS v2.0 covers all the global land area except Antarctica" and "major islands".
  - There's no regular acquisition beyond about 82 degrees latitude, nor at high latitudes in
    winter.
  - No open ocean: CMR found **0 granules** in seven weeks at 30 S, 140 W, and the sample ocean
    tile is 100% transparent. Coastal water inside a land MGRS tile is included.
- **Granules:** MGRS tiles about 110 km across. A single day covers only the swaths acquired
  that day.
- **Revisit:** "three days or fewer per tile in most regions"; a median of 1.4 days for both
  sensors combined.
- **Latency:** "typically 2-3 days". The newest date in GetCapabilities on 2026-10-10 was
  2026-10-08.
- **What a date means:** the GetCapabilities date ranges only say that some granule exists
  somewhere that day. Whether a given place has imagery on a given date isn't in the WMTS
  metadata. It needs a CMR granule search, or a fetch that may come back transparent.
- **Data use** (HLSS30 catalog entry): "openly shared, without restriction, in accordance with
  the EOSDIS Data Use and Citation Guidance".
  - **Citation:** Neigh, C. et al. (2021), *HLS Sentinel-2 Multi-spectral Instrument Surface
    Reflectance Daily Global 30m v2.0*, NASA LP DAAC, https://doi.org/10.5067/HLS/HLSS30.002
    (HLSL30 has its own DOI, 10.5067/HLS/HLSL30.002).
  - **GIBS acknowledgment:** the same text the app already shows.
  - **Unclear:** S30 is derived from Copernicus Sentinel-2 data. Neither GIBS nor the catalog
    page says whether a "Contains modified Copernicus Sentinel data" notice is also expected.
- **Caching:** tiles send `cache-control: no-store` (as VIIRS does), so the browser won't reuse
  them across visits.

### WELD (Web-Enabled Landsat Data)

- Sharp, seamless, cloud-free 30 m composites, but the newest is the 2000 annual mosaic (WELD
  v3.1 covers 1984-2001).
- 25 years out of date, so it's not a candidate for showing the present.
- Tiles are cacheable for 30 days (`max-age=2592000`).

## 2. Evidence: sample tiles and crops

**Downloads, all single requests, well within GIBS guidance:**

| What | Requests | Size |
|---|---|---|
| GIBS tiles | 17 | 3.07 MB |
| EOX tiles | 4 | 54 kB |
| Malformed EOX requests (my shell error) | 2 | 404, 1.2 kB each |
| CMR granule searches (JSON) | 8 | |
| Capabilities documents (GIBS 5.3 MB, EOX 68 kB) | 2 | |

**Per tile:**

| Layer | Level | Size per tile |
|---|---|---|
| VIIRS | 8 (JPEG) | 17-42 kB |
| HLS | 11 (PNG) | **222-532 kB**, about 10x VIIRS |
| WELD | 11 (JPEG) | 28-77 kB |
| EOX | 13 (256 px JPEG) | 10-18 kB |

**Locations and dates.** Each HLS date was the clearest recent granule CMR found for that
place; VIIRS is shown for the same date.

| Location | Point | HLS sensor | Date |
|---|---|---|---|
| SF Bay | 37.80 N, 122.30 W | S30 | 2026-09-12 |
| Nile delta | 30.80 N, 31.00 E | L30 | 2026-09-07 |
| Alps | 46.55 N, 7.98 E | S30 | 2026-09-27 |
| Richat structure, Sahara | 21.12 N, 11.40 W | L30 | 2026-08-28 |
| South Pacific | 30 S, 140 W | S30 | 2026-10-05 |

**Crops** (`crops/<place>.png`): each shows one HLS level-11 tile (about 15.6 km across).
- **Left:** the matching 1/8 of the VIIRS level-8 tile, upscaled.
- **Middle:** HLS.
- **Right:** WELD 2000.

**What they show:**

- **Sharpness:** HLS and WELD are dramatically sharper than VIIRS, as the 8x pixel ratio
  predicts.
  - **SF Bay:** Oakland airport's runways, the Port of Oakland's container stacks, the estuary
    and street grids are clear; VIIRS shows a blurred coastline.
  - **Nile delta:** individual fields, roads and villages, where VIIRS shows soft blotches.
  - **Richat:** the rings resolve into fine strata.
- **Clouds and dates:** HLS is one overpass, so its clouds and shadows are that day's.
  - On 2026-08-28 VIIRS had cloud over the Richat while the HLS (Landsat) pass was clear.
    Overpass times differ (VIIRS about 13:30 local; Landsat about 10:00; Sentinel-2 about
    10:30), so "the same date" doesn't mean the same clouds.
  - The SF granule on 2026-10-05 reported 46% cloud, yet the Oakland tile was clear: cloud is
    per place.
- **Terrain shadow:** the late-September Alps tile has deep black shadow on north-facing slopes
  (low sun). WELD's composite and EOX's summer mosaic show those slopes lit.
- **Gaps and seams:**
  - A level-8 HLS tile around SF on 2026-09-12 (`tiles/sf-bay-hls_s30-z8-2026-09-12.png`) is
    18% transparent. A whole MGRS granule wasn't acquired that day, leaving a hard-edged
    rectangular hole.
  - Small colour steps are visible where neighbouring granules meet.
  - In the Alps tile, 0.9% of pixels (shadow and cloud-masked) are transparent.
  - The ocean tile is 100% transparent.
- **WELD:** sharp and seamless, but the city, fields and shoreline are as of 2000 (and its
  greens are more saturated).

## 3. Comparison: Sentinel-2 cloudless by EOX (about 10 m)

**WMTS service:**
- **Capabilities:** `https://tiles.maps.eox.at/wmts/1.0.0/WMTSCapabilities.xml`, served with
  `access-control-allow-origin: *`.
- **Tile URL:**
  `https://tiles.maps.eox.at/wmts/1.0.0/{layer}/default/{TileMatrixSet}/{z}/{row}/{col}.jpg`
  (the template in the file says `http://`, but `https://` works).
- **Layers:** `s2cloudless` (the 2016 edition) and `s2cloudless-2017` through
  `s2cloudless-2025`, each with a `_3857` variant.
- **Tile matrix sets:** `WGS84` (EPSG:4326, levels 0-17, **256 px** tiles, 180/2^z degrees
  per tile, top-left at (-180, 90)) and `GoogleMapsCompatible` (EPSG:3857, levels 0-21).
  - Level 13 in WGS84 is about **9.6 m per pixel**, matching the native 10 m.
  - Note the grid isn't GIBS's 288-degree one, so the tile maths would need parameterizing.
- **Tiles:** JPEG, about 10-18 kB at level 13, `cache-control: max-age=604800` (7 days).
- **Crops:**
  - `crops/sf-bay-eox-2.4km.png` and `crops/alps-eox-2.4km.png`: one EOX level-13 tile (2.45
    km) against the same area from HLS (80 px upscaled) and VIIRS (10 px upscaled). At this
    scale VIIRS is a flat colour and HLS is blocky. EOX shows rail lines, container rows and
    individual buildings at the Port of Oakland, and roads and streams on Alpine slopes.
  - `crops/sf-bay-eox-2016-vs-2024.png`: the 2016 edition is hazier, lower in contrast and out
    of date (buildings differ); 2024 is crisp.

### License, quoted from EOX's own pages (2026-10-10)

- **Layer abstracts in the WMTS capabilities:**
  - **2016 (`s2cloudless`):** "released under ... Creative Commons Attribution 4.0
    International License."
  - **2018 to 2025:** "released under ... Creative Commons Attribution-NonCommercial-ShareAlike
    4.0 International License. For commercial usage please see https://cloudless.eox.at".
  - The 2017 edition's abstract wasn't checked.
- **License Summary page** (cloudless.eox.at/documentation/license):
  - It "does not replace the official license (EOX Commercial Attribution-RestrictedUse 1.2
    License), which remains the legally binding source. The EOX General Terms and Conditions
    ... also apply."
  - **Attribution:** "All uses of EOxCloudless require the following attribution: ... EOxCloudless
    https://cloudless.eox.at by EOX IT Services GmbH (Contains modified Copernicus Sentinel data
    "year")". "Attribution must be clearly visible wherever the imagery is displayed. For
    interactive maps, the credit should appear in the map interface."
  - **Non-commercial:** "You may use EOxCloudless freely for non-commercial purposes under the
    terms of the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
    License, including: Academic research; Educational materials, school and university
    projects; NGO publications and humanitarian mapping; Personal use".
  - **Commercial:** "You may use EOxCloudless for commercial purposes, given that you obtained
    an EOX Commercial Attribution-RestrictedUse 1.2 License from EOX, including: Web services
    and commercial dashboards; Paid software or GIS tools; Client-facing work or consulting
    deliverables; Printed map products sold for profit".
  - **Endorsement:** you "must not imply endorsement by European Commission (EC) or the
    European Space Agency (ESA)".
- **Pricing page:** "Feel free to use the provided service endpoints (WMS or WMTS) directly in
  your application" with attribution. It lists 2016 as CC BY 4.0 and 2018-2025 as CC BY-NC-SA
  4.0.
- **Fair use and rate limits:** none stated on the License Summary, Pricing or WMTS pages. The
  eox.at terms page didn't render readable content, so its clauses weren't checked.

**Unclear, and not resolved here:**
- **Personal portfolio:** whether a public personal portfolio site falls under "personal use",
  or counts as a "web service". The summary doesn't mention portfolios, and a portfolio may
  serve job seeking.
- **Which document governs:** the summary calls the EOX Commercial Attribution-RestrictedUse
  1.2 License "the legally binding source" even for non-commercial use. The layer abstracts
  give only CC licences, and I didn't find or read the 1.2 licence text.
- **ShareAlike:** how CC BY-NC-SA's ShareAlike would apply to a site that displays tiles
  (rather than redistributing modified imagery).
- **Attribution wording:** the unified text differs from the older s2maps.eu wording, though
  the page says old text needn't change. The 2016 abstract uses the new wording too.
- **Public endpoint limits:** whether `tiles.maps.eox.at` has unpublished limits or service
  guarantees.

Only the 2016 edition is CC BY 4.0, with no non-commercial clause.

## 4. Recommendation

The daily VIIRS layer stays the default for wide and medium zoom, since it follows the slider
date. A sharper layer would fade in only at close zoom.

**Shared design, whichever source is chosen:**
- **Fade:** fade the close-up layer in as the screen pixel size passes from about 250 m to
  about 60 m, reusing the existing fade and feather machinery.
- **Label it:** the panel should name it when visible, e.g. "Close-up: Sentinel-2 cloudless
  2024 (EOX), not the slider date", with its attribution in the map interface.
- **Clouds:** a cloud-free layer makes clouds dissolve as you zoom in. The fade band and the
  label make that honest rather than hidden.
- **Zoom limit:** stop no finer than one image pixel per two screen pixels (about 0.4 degrees
  of field of view at the ISS for 10 m, about 1.2 degrees for 30 m). The next round's
  "descend" camera changes these numbers.
- **Phones:** cap one level coarser (e.g. EOX level 12, or HLS level 10) and keep the 32-tile
  cache.

**Recommended: EOX Sentinel-2 cloudless as the close-up layer.** Use the 2016 edition (CC BY
4.0) by default, and switch to the newest edition only if Max confirms the site qualifies as
non-commercial (for example by asking EOX).
- **Why:** it's the only option that looks like Google Earth up close. It's 10 m, cloud-free,
  seamless and sunlit, and has no daily holes. Its ocean and polar coverage wasn't sampled
  here; check that before building.
- **Cost:** small cacheable JPEGs. A close ISS view at about 1-4 degrees of field of view needs
  about 15-25 level-12/13 tiles, roughly 0.2-0.4 MB.
- **Memory:** about 0.35 MB per 256 px tile with mipmaps on the GPU (96 tiles about 34 MB;
  phones, 32 tiles, about 11 MB).
- **Code:** no new library. It needs a second tile source in `earthTiles.ts` (a WGS84 grid of
  256 px tiles), probably 2-4 kB.
- **Main risk: licence and dependency.**
  - The sharp, current editions are non-commercial, and whether a portfolio qualifies is
    unclear.
  - The 2016 edition is visibly hazier and ten years old.
  - The public endpoint has no stated service guarantee or fair-use terms.

**Runner-up: GIBS HLS (S30, then L30) as the close-up layer.**
- **Rule:** the newest granule on or before the slider date, falling back day by day.
- **Why:**
  - Same provider and terms as today ("openly shared, without restriction"); no licence
    question.
  - Same tile grid (`31.25m` level 11 just extends the current maths).
  - CORS `*`, and it can loosely follow the slider date.
- **Cost:** 30 m (about 3x coarser than EOX) and about 10x the bytes of VIIRS. HLS PNGs run
  about 0.2-0.5 MB, so a close view of 4-8 tiles is 2-4 MB; at about 1.4 MB per 512 px tile on
  the GPU, phones would need tighter caps.
- **Main risk: incompleteness.**
  - No ocean; per-day holes (hard-edged granule rectangles); that day's clouds and low-sun
    shadows.
  - Which date has data at a given place isn't in the WMTS metadata, so a per-tile fallback
    either costs extra requests (transparent tiles) or a CMR search.
  - It will often look patchy rather than Google Earth-like.

**Not recommended:** WELD. It's sharp and seamless but frozen at 1999-2001.

## Sample files (on disk, not committed)

All under `~/Desktop/Projects/imagery-research-2026-10/`:
- **`crops/` (8.4 MB):** `sf-bay.png`, `nile-delta.png`, `alps.png`, `sahara-richat.png`,
  `ocean.png`, `sf-bay-eox-2.4km.png`, `alps-eox-2.4km.png`, `sf-bay-eox-2016-vs-2024.png`.
- **`tiles/` (3.1 MB):** the raw tiles above, named `<place>-<layer>-z<level>-<date>`.

They aren't committed because they contain third-party imagery, including the CC BY-NC-SA EOX
2024 edition, and the brief said not to commit downloaded imagery.
