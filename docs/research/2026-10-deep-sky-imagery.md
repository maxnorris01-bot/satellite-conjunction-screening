# Research, 2026-10: a zoomable deep-sky backdrop from HiPS sky surveys

**Question.** How could the `portfolio-site` space views get a Google Sky / Aladin-style backdrop:
a sphere of streamed sky-survey tiles that gets sharper as the field of view narrows, down to a
"Hubble Deep Field" feel in deep fields? The app already streams Earth imagery tiles (quadtree LOD,
LRU cache, request caps, fades, attribution), so this is about the sky side.

**Method.**
- **Survey facts:** taken from the provider's own sources: each survey's HiPS `properties` file,
  CDS's MocServer registry, the IVOA HiPS 1.0 Recommendation, and the licence page of each data
  owner.
- **Measurements:** CORS and caching from real HTTP headers.
- **Visual results:** 53 test tiles plus layout and alpha checks (about 60 requests in total, with
  a 0.3 s pause between them), saved outside the repo in
  `~/Desktop/Projects/deep-sky-research-2026-10/` (`tiles/`, `tiles/index.csv`,
  `sheet_{orion,galcentre,hdfn}.jpg`, `props/`).

Anything not confirmed from a primary source is marked **unconfirmed**. No code was written in
`portfolio-site`.

## Summary

- **HiPS is the right format, and CDS's servers can be used straight from a browser.** All tiles
  and `properties` files tested return `Access-Control-Allow-Origin: *`, with `ETag` and
  `Last-Modified` but no `Cache-Control`. The `alaskybis` mirror serves identical tiles. **No
  published rate limit or HiPS-specific terms of use were found.** That's the main open question
  for CDS (see Risks).
- **The best-looking layers are not the freely licensed ones:**
  - Mellinger's Milky Way panorama is by far the best wide backdrop, but it's "All rights
    reserved", and educational or commercial use needs a paid licence.
  - DSS2 colour is the only full-sky colour layer that works from wide to mid zoom. It's a
    copyrighted collection that's free for non-profit use, with commercial use prohibited without
    permission.
  - Gaia DR3 maps are CC BY-NC (non-commercial).
- **The Hubble Deep Field feel is achievable.** CDS publishes colour HiPS of the HST and JWST
  outreach images (orders 12-14). At the Hubble Deep Field North they show hundreds of resolved,
  colourful galaxies. These come from ESA/Hubble and ESA/Webb releases, which are CC BY 4.0. They
  cover only small patches of sky, but they're transparent outside their footprints, so they layer
  straight over an all-sky survey.
- **Rendering is a modest extension of the existing Earth tiler:** per-tile curved quads with
  textures, and one 7 KB MIT dependency (`@hscmap/healpix`), verified against astropy. Budget is
  about 6-35 tiles per view. The deep PNG layers are heavy (about 0.55 MB per tile), so phones
  should load them only at named targets.
- **A frame rotation is required.** HiPS is ICRS (J2000); the app's satellites are TEME (of date),
  0.15-0.37° apart in 2026.

## 1. HiPS: layout, access and terms

**Layout** (IVOA HiPS 1.0, REC-HIPS-1.0-20170519, verified in the PDF text):
- **Paths:** "Tile N in order K → NorderK/DirD/NpixN{.ext} where D=(N/10000)*10000 (integer
  division)" (§4.1), e.g. `Norder6/Dir10000/Npix10302.jpg`. Allsky previews are at
  `NorderK/Allsky{.ext}`, for K = 0-3 (§4.3.2).
- **Numbering:** "HiPS must use the NESTED numbering scheme only" (§4.1). Order K has 12·4^K
  tiles.
- **Tile size:** `hips_tile_width` defaults to 512. 512 x 512 is described as "a good compromise"
  (§4.2.1). Every survey below uses 512.
- **Formats:** FITS, PNG or JPEG for images (§4.2.2). "In JPEG and PNG the lines of the pixel array
  are stored in top->down direction." Per survey it's `hips_tile_format`.
- **Pixel size by order** (512 px tiles, HiPS 1.0 table 5): order 0: 6.871′ · 3: 51.5″ · 4: 25.8″
  · 5: 12.9″ · 6: 6.44″ · 7: 3.22″ · 8: 1.61″ · 9: 0.805″ · 10: 0.403″ · 11: 0.201″ ·
  12: 0.101″ · 13: 50.3 mas · 14: 25.2 mas.
- **Frames:** `hips_frame` is `equatorial` (ICRS) for every survey here except Mellinger
  (`galactic`).

**Pixel layout inside a tile (verified empirically; the spec shows it only as a figure).**
- **The test:** a DSS2 order-8 tile and its four order-9 children were matched by image
  correlation (0.991-0.992 for the matching quadrant, about 0 for the others).
- **The result:** nested child 0 is top-left, 1 bottom-left, 2 top-right and 3 bottom-right. So
  HEALPix bit 0 runs down the rows and bit 1 runs right along the columns.
- **In `@hscmap/healpix` terms,** `pixcoord2vec_nest(nside, ipix, ne, nw)` sends `ne` to bit 0 and
  `nw` to bit 1 (checked at orders 3, 8 and 12). So **row-from-top = `ne`** and
  **column-from-left = `nw`**. A mesh vertex built at (ne, nw) samples the tile image at
  (x = nw, y = ne), from the top-left.
- Checked at the quadrant level only. The build should confirm it at pixel level, for example on
  one bright star.

**Access.**
- **CORS:** every tested `properties` file (11 surveys) and tile (53) on `alasky.cds.unistra.fr`
  returned `access-control-allow-origin: *` (`GET, OPTIONS`). So does the mirror
  `alaskybis.cds.unistra.fr`, and so does the old name `alasky.u-strasbg.fr`; all three returned
  the identical tile (same ETag).
- **Caching:** tiles send `ETag` and `Last-Modified` (2014-2022) but **no `Cache-Control`**, so
  browsers use heuristic caching and can revalidate cheaply. The app's own LRU stays the main cache.
- **Rate limits and terms: not found.**
  - `alasky.cds.unistra.fr` itself shows no usage terms.
  - CDS's acknowledgement page asks for "This research has made use of Aladin sky atlas, CDS,
    Strasbourg Astronomical Observatory, France" in research.
  - The VizieR rules ("free of usage in a scientific context"; "commercial usage ... subject to
    rules depending of the origin") cover catalogues, not HiPS tiles.
  - Each HiPS states `hips_copyright = CNRS/Unistra` for the HiPS packaging, and the data owner's
  copyright in `obs_copyright`.
  - **Unconfirmed: whether CDS is happy for a public third-party site to stream its tiles, and any
    request limits.** Aladin Lite, CDS's own embeddable viewer, is generally used against these
    servers, which suggests third-party browser use is tolerated (not verified this session, and
    not a written permission).

## 2. Candidate surveys

Finest-order pixel scale is computed from `hips_order` and a 512 px tile (the HiPS table). A few
`hips_pixel_scale` values in the metadata don't match their order: DSS2 colour gives `0.229`,
Pan-STARRS i-r-g gives `4.473E-4` at order 11, and JWST outreach gives `0.229`. Measured tile sizes
are from the test fetches.

| Survey (HiPS ID) | Coverage | Finest order | Pixel at finest | px/deg | Colour | Licence / permitted use (data owner) |
|---|---|---|---|---|---|---|
| Mellinger (`CDS/P/Mellinger/color`) | all sky (galactic frame) | 4 | 25.8″ | ~140 | colour | "Copyright 2000-2017 Axel Mellinger. All rights reserved." milkywaysky.com: free for **personal use**; "Higher resolutions, commercial & educational use: in most cases ... a license fee". Credit: Mellinger 2009, PASP 121, 1180. **Needs permission for a public portfolio.** |
| Gaia DR3 colour flux map (`CDS/P/DM/flux-color-Rp-G-Bp/I/355/gaiadr3`) | all sky | 7 | 3.22″ | ~1,120 | colour (synthetic) | `obs_copyright` "ESA/Gaia mission/DPAC". ESA Gaia licence page: "Gaia data are distributed under the CC BY-NC 3.0 IGO license", so **non-commercial only**. This map is a CDS product derived from that data. |
| DSS2 colour (`CDS/P/DSS2/color`) | all sky | 9 | 0.805″ | ~4,470 | colour (from red + blue plates) | MAST lists the DSS as a **copyrighted collection**: free for "research, teaching ... or other non-profit activities" with acknowledgement; "Commercial, for-profit use ... is prohibited without written permission". Ack: "The Digitized Sky Surveys were produced at the Space Telescope Science Institute under U.S. Government grant NAG W-2166." Plate copyright holders: Caltech, AAO, UK SERC/PPARC, AURA. |
| 2MASS colour J/H/K (`CDS/P/2MASS/color`) | all sky | 9 | 0.805″ | ~4,470 | false colour (near-IR) | 2MASS FAQ: gallery images "in the public domain"; ack "This publication makes use of data products from the Two Micron All Sky Survey, ...". **Unconfirmed** for the CDS-coloured atlas HiPS specifically. |
| Pan-STARRS DR1 colour z/zg/g (`CDS/P/PanSTARRS/DR1/color-z-zg-g`) | 78% of sky (Dec ≳ −30°) | 11 | 0.201″ | ~17,900 | colour | MAST: "Most data hosted at MAST are in the public domain". PS1 isn't addressed specifically (**unconfirmed**). PS1 ack text on its archive page. |
| SDSS DR9 colour (`CDS/P/SDSS9/color`) | 36% of sky | 10 | 0.403″ | ~8,940 | colour | SDSS image-use policy: CC BY; "images should be credited to the Sloan Digital Sky Survey"; link to sdss.org requested. |
| HST outreach (`CDS/P/HST/EPO`) | 0.081% of sky (patches) | 14 | 25 mas | ~143,000 | colour | `obs_copyright` "NASA, ESA, and STScI"; `obs_ack` "ESA/Hubble". ESA/Hubble: **CC BY 4.0, commercial use allowed**, credit "clearly and visibly" and "wording unaltered". STScI/NASA material: public domain, with credit to NASA and STScI requested. **Per-image credits vary and aren't recorded in the HiPS.** |
| JWST outreach (`CDS/P/JWST/EPO`) | 0.001% of sky | 14 | 25 mas | ~143,000 | colour | 195 images "downloaded on esawebb.org, as of April 24 2025". ESA/Webb: **CC BY 4.0, commercial allowed**, credit unaltered. Image IDs in the HiPS are opaque (`APPEND/P/…`), so credits must come from the release pages. |
| JWST SMACS 0723 (`CDS/P/JWST/Deep-Field-SMAC0723/NIRCam`) | one field | 14 | 25 mas | ~143,000 | colour | Credit (`obs_ack`) "NASA, ESA, CSA, and STScI". |
| GOODS colour (`CDS/P/HST/GOODS/color`) | GOODS-N and GOODS-S | 14 | 25 mas | ~143,000 | colour | `obs_copyright` "NASA/ESA/AURA". MAST HLSPs are "CC BY 4.0"; whether that covers GOODS is **unconfirmed**. |

**Measured tile sizes:** JPEG mean 94 kB (median 84, max 189; 37 tiles); PNG mean 548 kB (max 744;
12 tiles). Mellinger's order-3 `Allsky.jpg` is 2.0 MB.

## 3. What the test tiles look like

Targets were resolved with CDS Sesame: M42 83.820/−5.388, Sgr A* 266.417/−29.008, HDF
189.206/+62.216. Contact sheets are `sheet_*.jpg` in the research folder.

- **Orion (M42):**
  - **Mellinger (orders 3-4)** is the best wide view by far: the constellation with a glowing
    nebula, natural colour.
  - **DSS2** is good at order 5, but M42's core saturates to flat peach by order 7 and is solid
    peach at order 9.
  - **2MASS** is a pretty purple infrared nebula at order 7, with a white-saturated core at order 9.
  - **Pan-STARRS** is badly artefacted on bright nebulosity: red saturated wedges, diagonal
    skycell seams, black masked blobs. Order 11 returned 404.
  - **SDSS** is saturated flat cyan.
  - **Gaia DR3** is nearly black with a faint speckle.
  - **HST outreach (orders 10-12)** is the Orion mosaic in natural colour, with visible rectangular
    image edges.
- **Galactic centre:**
  - **Pan-STARRS (orders 7-11)** is the best: crisp natural-colour star fields, still sharp at
    order 11.
  - **DSS2** is good at orders 7-9 and dark at order 5 (optical extinction).
  - **2MASS** is a dramatic yellow-and-dust infrared view at order 7 and a saturated mush at
    order 9.
  - **Gaia DR3 (order 5)** is a striking orange density texture with dust lanes, just black
    speckle at order 7.
  - **Mellinger** gives soft Milky Way star clouds.
  - **HST outreach** is blurry here (upsampled from a wide outreach image).
- **Hubble Deep Field North:**
  - **HST outreach (orders 10-12)** gives the Hubble Deep Field look: hundreds of small,
    colourful galaxies, clearly resolved at order 12. Order 14 returned 404 at the exact point.
  - **JWST outreach (orders 11-14)** is the richest, most colourful galaxy field, softening at
    order 14.
  - **GOODS** is bluer and noisier; at order 14 it shows pixel noise, magnified past its native
    detail.
  - **The all-sky surveys show almost nothing here:** Mellinger a generic star field, Gaia and
    DSS2 nearly black, SDSS faint smudges, Pan-STARRS blotchy background and noise.

**Best looking:** Mellinger for wide views; DSS2 (and Pan-STARRS in star fields) for mid zoom;
HST and JWST outreach for deep zoom at named targets. **Avoid** Gaia flux maps as a "pretty"
layer, and SDSS or Pan-STARRS on bright nebulae.

## 4. Recommended plan

**Layers by field of view** (vertical FOV; the order follows the "one tile pixel ≤ one CSS pixel
at the centre" rule the Earth imagery uses):

| Range | Layer | Notes |
|---|---|---|
| > ~20° (orders 0-3) | **Wide:** Mellinger *if permission is granted*; otherwise DSS2 colour orders 3-4, under the planned bright-star point layer | Mellinger is the only one that looks like the naked-eye sky. Ask info@milkywaysky.com, describing the use (free, non-commercial portfolio). |
| ~20° → ~0.3° (orders 4-9) | **Mid:** DSS2 colour | The only full-sky colour layer that holds up across this range. It saturates on the brightest nebulae (M42 core). Pan-STARRS z/zg/g is a later option for orders 9-11 in star fields north of Dec −30°, not over bright nebulae. |
| < ~0.3° (orders 10-14) | **Deep:** HST and JWST outreach, where they exist | Patches only. They're transparent outside footprints (91-99% alpha = 0 on an order-6 test tile), so they draw straight over DSS2. Elsewhere, deep zoom stops at DSS2 order 9 (~0.8″), with the same easing into the limit the Earth view uses. |

**Blending.**
- Cross-fade between layers over about one order of FOV, the way Today's imagery fades by pixel
  ratio.
- Keep the parent tile visible until its children load, as the Earth tiler does.
- For deep layers, use the HiPS's own `Moc.fits` coverage (HiPS 1.0 §4.4.2) to skip requests
  outside footprints. Treat a 404 as "no coverage", not as an error.

**"Go to" deep fields.** These are named targets with their release-page credit and position,
verified on the release pages and with Sesame:
- **Hubble Ultra Deep Field** (ESA/Hubble heic0406a): 03h32m38.9s −27°47′29″, 3.1′ x 3.1′.
  Credit "NASA, ESA, and S. Beckwith (STScI) and the HUDF Team".
- **Hubble eXtreme Deep Field** (heic1214a): 03h32m38.8s −27°47′30″, 2.38′ x 2.08′. Credit "NASA,
  ESA, G. Illingworth, D. Magee, and P. Oesch (University of California, Santa Cruz), R. Bouwens
  (Leiden University), and the HUDF09 Team".
- **Hubble Deep Field** (opo9601a): Sesame "HDF" 12h36m49.5s +62°12′58″. Credit "Robert Williams
  and the Hubble Deep Field Team (STScI) and NASA/ESA".
- **Webb's First Deep Field, SMACS 0723:** Sesame 07h23m13.3s −73°27′25″. Credit "NASA, ESA, CSA,
  and STScI" (from its HiPS). The ESA/Webb release page wasn't located (**unconfirmed** ID).
- **Cosmic Cliffs, Carina** (ESA/Webb weic2205a): 10h36m51.0s −58°37′12″, 7.29′ x 4.22′. Credit
  "NASA, ESA, CSA, and STScI".

Each target flies to its position at a field of view a little wider than the image, and shows its
credit line while the image is on screen, with an active link (ESA's credit terms). Coverage was
checked with MocServer point queries:
- **HDF-N:** HST outreach, GOODS colour, JWST outreach.
- **HUDF:** HST outreach, GOODS colour.
- **SMACS 0723:** its own JWST HiPS.

## 5. Rendering on a three.js sphere

**Geometry.** I recommend per-tile curved quads, the same pattern as the Earth tiles.
- **Mesh:** each visible tile is a small grid mesh whose vertices come from
  `pixcoord2vec_nest(nside, ipix, ne, nw)` for (ne, nw) on an n x n grid in [0, 1]². Use a finer
  grid at low orders (16 x 16 at orders 0-3, where tiles span up to 58°) and 2 x 2 to 4 x 4 at
  deep orders.
- **Texture:** UV = (u = nw, v = ne) with the image's top-left as the origin, per the layout check
  above. Draw on the inside of a large sphere, depth-write off, behind everything.
- **Tile selection:** `query_disc_inclusive_nest` over the view cone at the chosen order, plus the
  parent fallback.
- **The alternative,** one sphere with a fragment shader computing each pixel's nested index and
  sampling a texture atlas, avoids seams but needs atlas management and a GLSL port of HEALPix.
  Not worth it at this scale.

**Projection maths and frames.**
- **HiPS frame:** ICRS (J2000). Mellinger is galactic, which needs the fixed galactic → ICRS
  rotation matrix.
- **The app's frame:** satellites are in TEME (of date). Computed with astropy for 2026-10-12, the
  ICRS → TEME direction change is **0.15-0.37°** depending on direction (HDF 0.20°, M42 0.33°,
  Sgr A* 0.37°). That's far larger than a deep field.
- **So apply one precession + nutation rotation (ICRS → TEME of date) to the sky sphere,**
  recomputed per day of the displayed time. Otherwise deep fields would sit visibly off their true
  positions. astronomy-engine, which the Sky view already loads, has a J2000 → equator-of-date
  rotation. How closely that matches TEME (which uses a different equinox) wasn't checked this
  session; the build should compare it with satellite.js or astropy.

**Dependency.**
- **`@hscmap/healpix` 1.4.12:** MIT, no dependencies, 7.1 KB minified (**2.95 KB gzipped**). It
  provides `vec2pix_nest`, `corners_nest`, `pixcoord2vec_nest`, `query_disc_inclusive_nest` and
  `max_pixrad`.
- **Verified** against astropy-healpix at orders 3, 9 and 12-15 for 5 positions: **30/30
  identical**, including indices above 2³¹ (at orders 14-15), so JavaScript's 32-bit bitwise
  limits aren't hit.
- **No precomputed lookup is needed.**
- **Not recommended:** Aladin Lite (`aladin-lite` 3.9.2-beta) is LGPL-3.0-or-later and 2.7 MB
  unpacked, a complete separate viewer and canvas, not composable into the three.js scene.

**Tiles and bytes per view.** Estimates for the rule above: view area / tile area x 1.6 + 4, using
the measured mean sizes.

| Vertical FOV | Phone 390x844: order, tiles, MB (JPEG / PNG) | Desktop 1440x900: order, tiles, MB (JPEG / PNG) |
|---|---|---|
| 60° | 1, ~9, 0.8 / 4.9 | 1, ~16, 1.5 / 8.8 |
| 10° | 4, ~9, 0.8 / 4.9 | 4, ~23, 2.2 / 12.6 |
| 1° | 7, ~7, 0.7 / 3.8 | 7, ~16, 1.5 / 8.8 |
| 0.3° | 9, ~9, 0.8 / 4.9 | 9, ~21, 2.0 / 11.5 |
| 0.03° | 12, ~7, 0.7 / 3.8 | 12, ~15, 1.4 / 8.2 |

A full zoom from 60° to a deep field passes through about 10-12 orders. With the parent fallback
that's roughly 80-120 JPEG tiles (about 8-11 MB), plus 5-15 PNG tiles (3-8 MB) at the end. The
PNG figure is the expensive part.

**Phone budget (proposed, to tune in the build):**
- At most 4 tile requests in flight on phones and 6 on desktop (proposed; align with whatever
  caps the Earth tiler uses).
- An LRU of about 32 decoded tiles on phones (a 512 x 512 RGBA texture is 1 MiB, so about 32 MiB
  of GPU memory) and about 96 on desktop.
- Optionally downsample deep PNGs to 256 px on phones.
- Load the deep outreach layers on phones only when a "go to" target is active, or below 0.3° FOV.
- The wide layer: start from `Norder3/Allsky.jpg` (Mellinger 2.0 MB) or the order-3 tiles, not
  768 separate requests.

## Risks

- **Licensing is the main risk:**
  - Mellinger needs permission.
  - DSS2 is non-profit only. A personal portfolio is arguably non-profit, but it's used for job
    seeking, so it's worth a one-line confirmation.
  - Gaia DR3 is non-commercial.
  - Pan-STARRS and the 2MASS atlas aren't explicitly licensed for this use.
  - The outreach images (CC BY 4.0, or public domain from NASA/STScI) are the cleanest.
- **CDS terms and limits aren't documented.** The app would depend on a research service's
  bandwidth. Ask CDS (contact via cds.unistra.fr) before shipping, and keep a mirror fallback
  (`alaskybis`).
- **Credits for the outreach HiPS aren't per image.** The HST and JWST outreach HiPS merge many
  images, each with its own credit line, and the HiPS IDs don't map back to them. Outside the
  curated "go to" targets, the credit would have to be the general "NASA, ESA, CSA, STScI;
  ESA/Hubble; ESA/Webb", which may not satisfy CC BY's exact-credit wording for every image.
- **Visual artefacts:** DSS2 saturates bright nebulae, Pan-STARRS has skycell seams and masks, and
  the outreach mosaics show image edges and some upsampled areas.
- **Weight:** the deep PNG tiles are about 0.55 MB each.
- **Frame alignment:** the ICRS → TEME rotation (0.15-0.37°) must be applied, or deep fields drift
  off their true positions.

## Open questions

1. Will Axel Mellinger grant use of the panorama on a free portfolio site, and with what credit?
2. Are CDS happy for a public site to stream alasky tiles directly, and is there a request-rate
   expectation?
3. Does the portfolio count as "non-profit" for DSS2? If not, is DSS2 replaced (by Mellinger plus
   points, or a lower-order, CC BY layer)?
4. The ESA/Webb release ID and page for Webb's First Deep Field (SMACS 0723).
5. Confirm the in-tile pixel mapping at pixel level (one bright star) in the build.
6. Should the backdrop appear in the Globe view (TEME) only, or also in Sky (horizon frame) and the
   satellite view? The rotation chain differs per view.
