# 2026-10-16 - The space view round (portfolio-site PRs #30 to #34)

A docs-only record of what shipped in the sibling `portfolio-site` repo between 2026-10-13 and
2026-10-16, written from that repo's git log, PR descriptions, `README.md`, `src/globe/*` and
`public/data/stars/ATTRIBUTION.md`. Nothing in this repo's code changed. The data half (the Gaia
tiles and glow atlas) is in [`2026-10-14-gaia-star-data.md`](2026-10-14-gaia-star-data.md); the
format is in [`../star-data-format.md`](../star-data-format.md).

| PR | Merged | What |
|---|---|---|
| #30 `feat/space view` | 2026-10-13 | Stars, Sun/Moon/planets from the satellite, limb glow, night lights |
| #31 `feat/star selection` | 2026-10-14 | Selecting stars, info cards, IAU names, Find a star |
| #32 `feat/constellations` | 2026-10-14 | Figures, names, IAU boundaries |
| #33 `feat/streamed stars` | 2026-10-16 | Gaia tile loader, glow atlas, SIMBAD lookups for Gaia stars |
| #34 `fix: dim the glow and stars...` | 2026-10-16 | Sky dimming when looking at the Earth |

## The satellite POV space view (#30)

- **Stars.** 118,217 Hipparcos stars (ESA 1997, CDS/VizieR I/239) with positions moved to epoch
  2026.0, V magnitude and B-V colour, in a column-wise binary (`scripts/build-hipparcos.mjs`, 946 kB,
  816 kB gzipped) behind a small `StarCatalog` interface. Drawn as one point-sprite shader at
  infinity in the inertial frame. Phones read only stars to magnitude 8 (about 42,000) at this point.
- **Sun, Moon and planets** at their true direction from the viewing satellite, not from the Earth's
  centre. The Moon's parallax from low orbit is real (0.22 to 0.97 degrees from the ISS, 2.5 to 6.0
  degrees from GEO), and its phase is the Sun-Moon-satellite angle at the Moon. Tapping one opens a
  small card.
- **Limb glow.** A thin back-face shell shaded by grazing height, scaled by the Sun angle.
- **Night lights.** NASA GIBS `VIIRS_Black_Marble` (2016 annual composite) streamed as tiles over
  the dark side, with the bundled 2K texture as the first paint and a small tile budget (36 cached,
  12 drawn, 4 in flight on desktop; 12, 6 and 3 on phones).
- **Zoom** narrows to 0.05 degrees when looking out (later 0.01, see #31); the Earth keeps its
  30 degree riding limit.

## Star selection and cards (#31)

- A click or tap picks the nearest star within 12 CSS px (20 for touch); among close stars the
  brighter wins (1.5 px per magnitude). A Sun, Moon or planet disc under the tap wins over a star.
- The card shows the IAU name (or HIP number), constellation, position (J2000 moved to 2026), V,
  distance, spectral type in words, colour, temperature and luminosity, only where supportable.
  Estimates say so, with the method: distance from parallax (a value if better than 10%, a range
  10 to 30%, "uncertain" beyond, nothing if no parallax); temperature from B-V (Ballesteros 2012,
  ignores dust reddening); luminosity from absolute magnitude plus a bolometric correction (Torres
  2010), only for parallaxes better than 30%, ignoring extinction and treating a double star as one.
  Checked on Sirius, Polaris, Vega, Betelgeuse and Barnard's Star in the portfolio repo's tests.
- Data: `hipparcos-details.bin` (HIP number, parallax and error, spectral type, variability; 1.10 MB,
  714 kB gzipped), fetched only when a star is selected or searched for, and `iau-names.json`
  (410 IAU names for stars with a Hipparcos number, from the IAU WGSN's IAU-CSN.txt, last updated
  2022-04-04; the IAU has named more stars since that are not included).
- **Find a star**: search by IAU name or HIP number, animated turn to the star, and tracking so the
  star can be zoomed on (the view is locked to the orbit, so the sky sweeps past at about 0.065
  degrees a second). Zoom floor 0.01 degrees.

## Constellations (#32)

- 88 stick figures (`constellations.json`, 10 kB) and IAU boundaries (`constellation-bounds.json`,
  43 kB), both loaded lazily the first time the Constellations switch (off by default) or a star's
  constellation button is used. Names and Boundaries are separate options.
- **Sources and licences.** Figures: `data/constellations.lines.json` from d3-celestial (Olaf Frohn,
  BSD-3-Clause, commit `7e720a3`, retrieved 2026-10-14); the licence text is kept beside the data.
  All 893 line vertices matched a Hipparcos star (worst 0.025 degrees). Boundaries: rebuilt from the
  Delporte table that `astronomy-engine`'s `Constellation()` searches (MIT), so the drawn boundary
  and the star card's constellation always agree.
- **Stellarium's western sky culture was evaluated and rejected**: its description says "Text and
  data: CC BY-SA" with no version, in a repository carrying an AGPL-3.0 licence file, so the data
  would have to be share-alike under unclear terms. GPL data was not used.

## Streamed Gaia stars (#33)

- **Data.** The `stars/v1/` prefix of the public bucket, built by this repo's `scripts/star_data/`:
  7,251,917 Gaia DR3 stars brighter than G=13 in 768 HEALPix order-3 tiles, plus details files, a
  manifest and the glow atlas. **Uploaded on 2026-10-16, 1,539 files** (checked: the manifest and
  the 74,682-byte atlas are live under `stars/v1/`).
- **Loader.** `tilestream.ts` plans which tiles a view needs (nearest the centre first), caps
  concurrent requests, cancels tiles that leave the view, keeps an LRU cache by decoded star count,
  and gives up with "data unavailable" after repeated failures with nothing loaded. Tiles decode to
  J2000 unit vectors, a V-equivalent magnitude and a colour from the Hipparcos B-V ramp.
- **Whole-tile fetch rule.** The tiles are gzipped columns with no byte offsets, so a tile can't be
  fetched as a prefix. A tile is fetched whole, and only when at least 10 of its stars are brighter
  than the view's limiting magnitude: most tiles hold a stray bright Gaia star Hipparcos lacks, and
  fetching them for a wide field would cost 18 MB for a thousand stars. Tiles are brightest first,
  so a tile draws a prefix.
- **Budgets.** 1.5 million stars per view on desktop, 300,000 on a phone (a narrow or short stage).
  When the tiles in view exceed it the limiting magnitude is lowered until they fit. A frame-time
  guard cuts the budget when the average frame is over 28 ms and restores it when under 18 ms.
- **Hipparcos fallback.** Hipparcos loads first; if the manifest or tiles can't load, the sky is
  Hipparcos stars only and the panel says so. Phones now keep every Hipparcos star, because the
  Gaia tiles drop the ones Hipparcos covers and a missing one would be a hole.
- **G to V.** Gaia G is converted to the V the sky is drawn in with the Gaia EDR3 documentation's
  relation (Riello et al. 2021) over its range and a line through medians measured on 117,026 stars
  in both catalogues beyond it, so there is no seam at the handover.
- **Gaia selection and SIMBAD.** Gaia stars are picked with the same radius and score as Hipparcos
  stars. The card shows constellation, position, G (and about V), BP-RP colour, and from the details
  file the Gaia source ID and parallax. Name, object type and spectral type come from SIMBAD (one
  request per selection at most, debounced 0.4 s, cached, one second apart, 8 s timeout); the
  footnote carries CDS's acknowledgement while a result is shown.
- **The glow atlas replaces the Milky Way picture.** The NASA SVS Deep Star Maps picture (450 kB) was
  removed with its credit. The atlas is interpolated bilinearly (HEALPix weights) into a 1024 x 512
  texture so the 0.46 degree pixels never show, and dims as the field narrows (to 30% by 1 degree).
  *The 4:2:0 defect:* the first atlas was a JPEG at quality 85 with 4:2:0 chroma subsampling. In a
  HEALPix order-7 layout vertically adjacent pixels are unrelated sky positions, so the subsampling
  bled colour between them and showed as blocky colour patches. It was fixed here (PR #64) by saving
  at quality 92, 4:4:4: 40,542 B to 74,682 B, see the correction in
  [`2026-10-14-gaia-star-data.md`](2026-10-14-gaia-star-data.md). The upload happened after the fix,
  so the path stayed `stars/v1/`. (The #33 commit message still says "40 kB"; the live file is
  74.7 kB.)

## Sky dimming when looking at the Earth (#34, branch `fix/dim-sky-looking-down`)

A camera exposed for the sunlit Earth would show little sky, but the glow and stars were at full
brightness around the Earth's edge. The glow and stars are now multiplied by a factor that depends on
how much of the view is Earth (a cap of the view's field of view sampled at 48 directions, tested
against the Earth's disc, through a smoothstep from 5% to 60%) and whether the point below the
satellite is sunlit (blended through twilight), eased over 400 ms (1 s under reduced motion).

- **Defaults as merged** (`SKY_DIM_DEFAULT` in `skydim.ts`): glow x0.20 and stars x0.45 sunlit;
  glow x0.50 and stars x0.75 on the night side. **These may be retuned**; Max has not confirmed final
  values. Only brightness changes: which stars load, draw or can be picked is unchanged, and the Sun,
  Moon, planets, constellations, the Earth and the selection are not dimmed.
- **Debug hook.** `__globe.skyDim` holds the four values and is read every frame, so they can be
  retuned from the console; `?debug=1` exposes `__globe` on the live site and adds a "sky dim" line.

## Measured and recorded, not reproduced here

Software-GL frame times with the star count drawn, as reported by Max (not reproducible from either
repo's files): 50 ms with no Gaia stars, 67 ms at 117k, 100 ms at 341k, 167 ms at 817k, 217 ms at
1.06M. Software GL is not a real GPU. The real-GPU frame rate with about a million stars is
unverified (see the working notes).

## Next command

`git diff main --stat`
