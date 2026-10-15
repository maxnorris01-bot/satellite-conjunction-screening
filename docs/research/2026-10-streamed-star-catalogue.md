# Research, 2026-10: streaming many more stars (catalogue data) into the space view

**Question.** How could the `portfolio-site` space view stream millions to hundreds of millions of
stars as the user zooms in, with star selection and info, and a Milky Way built from real stars
instead of a flat image? The site already ships 118,217 Hipparcos stars (CC BY-NC 3.0 IGO; the
site is strictly non-commercial, which the owner confirmed) and a NASA SVS Deep Star Maps Milky
Way image. [`2026-10-deep-sky-imagery.md`](2026-10-deep-sky-imagery.md) covered HiPS *image*
surveys; this round covers *catalogue* data.

**Method.**
- **Facts** come from each provider's own sources: CDS's MocServer and each catalogue HiPS's
  `properties` and `Metadata.xml`, the ESA, CDS and CC licence pages (read as raw text), the TAP
  services' `capabilities` documents, and real requests with an `Origin` header.
- **Measurements:**
  - tile pulls: 49 catalogue tiles
  - source counts by magnitude from the Gaia archive itself
  - two real subset extractions
  - a GPU draw benchmark in headless Chromium on the real M5 GPU (`ANGLE Metal Renderer: Apple
    M5`, per the repo's headless rule)
- **Files** are saved outside the repo in `~/Desktop/Projects/star-catalogue-research-2026-10/`
  (`tiles/`, `props/`, `flux/`, `bench/`, `budget.txt`).

Anything not confirmed from a primary source is marked **unconfirmed**. No code was written in
`portfolio-site`.

## Summary

- **Direct streaming of CDS's catalogue tiles doesn't scale.**
  - Gaia DR3's tiles (CDS "HiPS catalog", CORS `*`) carry **all 225 columns** per row, so they
    cost about **500 bytes per star** on the wire. They're dynamically generated (no `ETag`, no
    `Cache-Control`) at about 1.1 s per tile.
  - 1 million stars would be about 500 MB and 2,000-20,000 requests. 100 million would be about
    50 GB.
- **Our own compact subset does.** At **8 bytes per star** (the layout `hipparcos.bin` already
  uses) 1M, 10M and 100M stars are **8 MB, 80 MB and 800 MB**, about 6.5 B/star after gzip.
  - The Gaia archive's own counts: 7.4 M stars are brighter than G=13, 78 M brighter than G=16,
    and 305 M brighter than G=18.
  - G<16 is about 624 MB packed, which costs about $0.01 a month on Tigris (egress is free).
- **The per-view point count is the binding limit, not the file size.** Measured on the M5 GPU,
  drawing 1M points takes 4.2 ms and 10M takes 47 ms. A view needs a budget of about 1.5M
  (desktop) or about 0.3M (phone, an assumption), and the view's magnitude limit has to track
  field of view.
- **Narrow fields don't need a prebuilt tile set at all.** A VizieR TAP cone query (CORS `*`) of
  Gaia DR3 returned 2k-20k rows in 2-3 s at about 31 bytes per row.
- **The Milky Way can be built from real star flux.** CDS publishes Gaia DR3 colour flux maps
  (all 1.8 billion sources summed per pixel). Binned to HEALPix order 7 they're about **74 KB**,
  and they show the bulge, dust lanes and both Magellanic Clouds.
- **Gaia doesn't replace Hipparcos at the bright end:** of seven famous bright stars checked,
  only Mintaka appears at its true magnitude.
- **Licensing fits the owner's confirmed use** (non-commercial): Gaia is CC BY-NC 3.0 IGO. Tycho-2
  and 2MASS state no licence of their own, so they're the weakest fit.

## 1. Candidate catalogues and licences

| Catalogue | Rows | Fields (relevant) | Licence / credit | Fits non-commercial use? |
|---|---|---|---|---|
| **Gaia DR3** (`gaiadr3.gaia_source`) | 1,811,709,771 | position (RA, Dec), G, BP, RP and BP-RP colour, parallax, proper motion, source_id, 225 columns in CDS tiles | "Gaia data are distributed under the CC BY-NC 3.0 IGO license" (ESA, `gaia-users/license`). Credit line "ESA, Gaia DPAC" (ESA archive terms). | **Yes.** BY-NC allows Share and Adapt with attribution and a link, non-commercially (CC deed). |
| **Tycho-2** (`I/259/tyc2`) | 2,539,913 | position, proper motion, B_T and V_T, HIP and TYC IDs, no parallax | The ReadMe and the Tycho-2 home page state **no licence**. ESA's page covers "the Hipparcos and Tycho Catalogues" as CC BY-NC 3.0 IGO, "Credit: ESA". **Unconfirmed for Tycho-2 itself.** Cite Høg et al. 2000, A&A 355, L27. | Probably, **unconfirmed**. Complete to about V=11.5 (90%), per its ReadMe. |
| **2MASS PSC** (`II/246/out`) | 470,992,970 | position, J/H/K only | IRSA acknowledgement text required. No licence statement for the catalogue found (images are described as public domain). | Probably, **unconfirmed**. Near-infrared only. |
| **Hipparcos** (`I/239/hip_main`) | 118,218 | position, V, B-V, parallax | CC BY-NC 3.0 IGO, "Credit: ESA" (ESA Hipparcos page). | Yes. **Already shipped.** |

Notes:
- **Gaia licence re-verified from ESA's own page text.** An earlier research round's summarizer
  gave the same licence, but a first recollection said CC BY-SA, which was wrong. The ESA page is
  the primary source.
- **ESA's terms** (cosmos.esa.int `esdc/terms-and-conditions`): data are "open and free to use ...
  subject to proper acknowledgment". "Prior to any commercial use ... a detailed request for
  authorisation/licence shall be made" to data.licences@esa.int. Credit lines: Gaia "ESA, Gaia
  DPAC", Hipparcos "ESA".
- **CDS marks these catalogue HiPS "public master unclonable"** (`hips_status`): the HiPS service
  products aren't meant to be mirrored. Our own subset is built from the Gaia archive, not by
  cloning CDS's tiles, and CC BY-NC permits adaptation.
- **Not evaluated:** the LSDB "HiPSCat" (Parquet partitioning) is a different format from CDS's
  `cds.hips.cat` TSV tiles, which is what's measured here.

## 2. Access, tile layout and cost

**CDS catalogue HiPS** (`https://hipscat.cds.unistra.fr/HiPSCatService/...`):
- **CORS:** `Access-Control-Allow-Origin: *` on tiles, `properties` and `Metadata.xml`. No
  rate-limit or terms-of-use statement was found.
- **Layout:** `NorderK/DirD/NpixN.tsv`, the HiPS 1.0 path rule. Orders: Gaia and 2MASS 1-11,
  Tycho-2 1-6. The catalogue was built with `cds.hips.cat` and the Gaia table is "sorted by mean G
  magnitude".
- **Each tile** starts with a `# Completeness = rows/total` comment, then a header and rows. It
  holds the next-brightest sources of its cell **not already held by its ancestors**. The
  magnitude ranges of successive orders continue where the previous one ended, and the
  completeness comments (e.g. `85/85` at order 11 means "all remaining") are consistent with
  this. That reading is inferred from the pulled tiles, not from CDS documentation. A complete
  picture of a cell would then be its tile plus its ancestors' tiles, filtered by position.
- **Headers:** responses are gzip, chunked and dynamically generated, with no `ETag` or
  `Cache-Control`.
- **Latency:** 1.1-1.2 s per tile. Twelve tiles took 14.1 s sequentially and 2.4 s with 6 in
  parallel.

**Measured tiles** (Orion and the Galactic centre, 49 tiles pulled):

| Survey | Columns | Bytes/row on wire | Rows/tile | Deepest order pulled | Faintest magnitude there |
|---|---|---|---|---|---|
| Gaia DR3 | 225 | 380-550 | 17-514 | 11 (the last level) | G ≈ 20.3 (Orion), 21.1 (Galactic centre) |
| Tycho-2 | 37 | 93-104 | 32-205 | 5-6 (the last level) | VT ≈ 12.3-12.6 |
| 2MASS | 16 | 47-71 | 24-500 | 10 (order 11 returned 404) | J ≈ 17.5-17.7 |

In the Orion cell, the faint limit of the tile at each Gaia order rises by about 1.5 magnitudes
per order (G 5.4 at order 1, 8.6 at order 5, 13.6 at order 7, 17.4 at order 10). The same tiles
at the Galactic centre hold more rows at the coarse orders because the sky is denser.

**What a zoom-in costs.** Counts are from the Gaia archive's own `COUNT(*)` (2026-10-14):

| G < | Stars | Packed (8 B) | gzip (~6.5 B) | + details (10 B) | CDS cat tiles (~500 B) |
|---|---|---|---|---|---|
| 10 | 482,106 | 4 MB | 3 MB | 9 MB | 241 MB |
| 12 | 3,087,821 | 25 MB | 20 MB | 56 MB | 1.5 GB |
| 13 | 7,369,627 | 59 MB | 48 MB | 133 MB | 3.7 GB |
| 14 | 16,844,156 | 135 MB | 109 MB | 303 MB | 8.4 GB |
| 15 | 36,909,335 | 295 MB | 240 MB | 664 MB | 18.5 GB |
| **16** | **77,952,319** | **624 MB** | **507 MB** | **1.4 GB** | **39 GB** |
| 17 | 157,731,259 | 1.3 GB | 1.0 GB | 2.8 GB | 79 GB |
| 18 | 304,941,694 | 2.4 GB | 2.0 GB | 5.5 GB | 153 GB |

So **1M ≈ G<10.8, 10M ≈ G<13.4, 100M ≈ G<16.4**.

| Stars | CDS tiles (50-500 rows each) | Own tiles (~25k stars, ~200 KB) |
|---|---|---|
| 1 M | 2,000-20,000 tiles, 500 MB; 6-61 min at 6 parallel | ~40 tiles, 8 MB (6 MB gzip) |
| 10 M | 20,000-200,000 tiles, 5 GB; 1-10 h | ~400 tiles, 80 MB |
| 100 M | 200,000-2,000,000 tiles, 50 GB; 10-100 h | ~4,000 tiles, 800 MB |

The CDS tile route is unusable above a few hundred thousand stars. The own-subset route is
practical, and the packed size is the same as the existing file's.

**Per-view budget (what's actually on screen).** Desktop at 1440 x 900 with a 1.5M-point budget,
phone at 390 x 844 with a 0.3M-point budget (an assumption, see section 4). The G limit that holds
the budget at average sky density (and in the dense plane, about 10x):

| Vertical FOV | Desktop: G limit (avg / plane) | Desktop: MB to load | Phone: G limit (avg / plane) | Phone: MB to load |
|---|---|---|---|---|
| 120° | 11.8 / 9.4 | 12 | 11.4 / 9.1 | 2.4 |
| 60° | 13.5 / 10.8 | 12 | 13.0 / 10.5 | 2.4 |
| 30° | 15.2 / 12.4 | 12 | 14.7 / 12.0 | 2.4 |
| 10° | 18.4 / 15.1 | 12 | 17.8 / 14.6 | 2.4 |
| 3° | 21 (all) / 18.5 | 4.8 | 21 (all) / 18.0 | 1.4 |
| 1° | all, 67k stars | 0.5 | all, 19k stars | 0.2 |

The view area uses the small-angle product, so the 120° row is approximate. The "plane" column
assumes about 10x average density; the measured ratio was 19x between two level-5 cells (Orion
2,381 stars at G<16, Galactic centre 46,151).

**Consequences.**
- A G<16 subset (624 MB) already reaches the full visible budget down to about a 25° field of
  view. Narrower views are limited by the sky's real star count, not by the subset.
- Peak on-screen load happens at mid fields of view (10-60°) and is capped by the magnitude
  limit, not by the catalogue's size.
- Estimate, not measured end to end: a desktop zoom from the whole sky to a 1° field loads on the
  order of 12-20 MB of tiles (the visible budget of about 12 MB plus ancestors). On a phone,
  about 3-5 MB.

**Preprocessing versus reading live.**
- **Extraction.** The Gaia archive's `source_id // 2^35` is the nested level-12 HEALPix index
  (**verified on 110 of 110** real sources), so partitioning by sky cell is a `source_id` range.
  - TAP's output limit is 3,000,000 rows. Single sync queries ran at **0.8-2 k rows/s**
    (2,381 rows in 3.0 s; 46,151 rows in 22.7 s).
  - G<13 (7.4 M rows) would be about 1-2.5 h sequentially. G<16 (78 M) about 11-27 h
    sequentially, less in parallel.
  - The bulk alternative is 3,386 CSV files totalling **0.75 TB** (233 MB each, CORS `*`).
  - The archive was in a downtime window on 2026-10-14, so extraction depends on its
    availability.
- **Hosting** (Tigris pricing page): Standard $0.02/GB-month, first 5 GB free, $0.0005 per 1000
  GET requests (first 100,000 a month free), no egress fees. G<16 packed is about $0.01 a month.
- **Redistribution:** CC BY-NC 3.0 IGO allows Share and Adapt with attribution, a link to the
  licence, and a note of changes, non-commercially. A derived packed subset is within that.
- **Live tiles from CDS** are free to host but are the slow, large path above, with unconfirmed
  terms.

**Narrow-field live queries (measured).** VizieR TAP's copy of Gaia DR3 (`"I/355/gaiadr3"`),
columns Source, RA_ICRS, DE_ICRS, Gmag, BP-RP, Plx, gzip CSV, with an `Origin` header:

| Field | Radius | Rows | On the wire | Time | CORS |
|---|---|---|---|---|---|
| Orion (M42) | 0.25° | 2,172 | 0.07 MB | 2.0 s | `*` |
| Orion (M42) | 0.5° | 5,315 | 0.17 MB | 2.3 s | `*` |
| Galactic centre | 0.1° | 3,052 | 0.09 MB | 2.2 s | `*` |
| Galactic centre | 0.25° | 19,759 | 0.60 MB | 2.7 s | `*` |

About **31-32 bytes per row**, 2-3 s per request. That covers fields of view of about 1° and
below with every Gaia source, and needs no tile build. The service's request-rate policy is
**unconfirmed**.

## 3. Star info lookups

| Service | CORS | Measured | Limits / terms |
|---|---|---|---|
| **SIMBAD TAP** (`simbad.cds.unistra.fr/simbad/sim-tap/sync`) | `*` | `basic`-only cone search 0.57 s and 0.58 s; `ident` lookup by Gaia DR3 ID 0.9 s. A join with `allfluxes` **timed out at 40 s** once. | TAP `capabilities`: 50,000 rows default, 2,000,000 hard; 1,080 s default execution. **No request-rate figure published** in the pages checked. |
| **Sesame** (`cds.unistra.fr/cgi-bin/nph-sesame`) | `*` | name to coordinates, 2.4 s | Not found. |
| **VizieR TAP** | `*` | cone queries above | `capabilities`: 1,000,000,000 rows default. Rates not found. |
| **Gaia archive TAP** (`gea.esac.esa.int`) | **none sent** (sync query returned 200 with no `Access-Control-Allow-Origin`) | counts 2.5-20 s | 3,000,000-row output limit. A browser can't call it directly. |

**What the catalogue itself carries** (Gaia): G, BP-RP colour, parallax (and its error), proper
motion, and the source ID. The 225-column tile row also has astrophysical columns; which are
populated wasn't checked.

**Real lookups that worked** (from Orion tile rows):
- SIMBAD `ident` for `Gaia DR3 3010113299530081664` returned `HD 37306`, spectral type `A1V`,
  parallax 14.38 mas.
- A cone of 0.01° at Alnitak returned `* zet Ori A` (`SB*`, O9.2IbvarNwk), `* zet Ori B`
  (O9.5II-III(n)) and `* zet Ori` (`**`, O9.7Ib+B0III, parallax 4.43 mas).

**Plan for the info card.**
1. On selection, show immediately from the catalogue: Gaia designation, G, BP-RP colour,
   parallax, and a distance only when the parallax is significant (e.g. parallax over error is at
   least 5), otherwise "distance uncertain".
2. In the background, one SIMBAD `ident` query by Gaia DR3 ID (or a small cone as fallback) for
   `main_id`, object type and spectral type. Cache results per session; one request per
   selection.
3. Hipparcos stars keep the existing `hipparcos-details.bin` and IAU names.
4. For a name search box, Sesame turns a name into coordinates.
5. Don't join `allfluxes`; use `basic` only.

Better distances (e.g. Bailer-Jones) in VizieR were **not verified**.

## 4. Rendering millions of points; the Milky Way from stars

**Draw cost, measured** (`gl.POINTS`, WebGL2, additive blending, 1440 x 900, 16 bytes per star,
a forced GPU sync after each draw, ANGLE Metal on the Apple M5, headless Chromium):

| Stars | VBO | Upload | Draw, median (p95) |
|---|---|---|---|
| 1 M | 16 MB | 1 ms | **4.2 ms** (4.4) |
| 3 M | 48 MB | 8 ms | 13.0 ms (14.2) |
| 10 M | 160 MB | 32 ms | **46.7 ms** (49.4) |
| 30 M | 480 MB | 124 ms | 156 ms (172) |

- That's about 4 ns per star on this GPU. 10M points in one draw is about 21 fps on an Apple
  laptop GPU, so a per-view budget is mandatory.
- **Phones were not measured.** Treat the 0.3M phone budget as an assumption to confirm on a
  real device. Phone GPUs are generally much slower, and the page's other rendering shares the
  frame.
- **Memory:** 8 B/star is 8 MB per million. The current 16 B layout would be 160 MB for 10M. A
  design that uploads the packed bytes and unpacks them in the vertex shader (integer
  attributes) halves GPU memory. It was not benchmarked.

**Design points** (building on the existing tile LOD, LRU and request caps):
- **Tiles:** progressive HEALPix NESTED tiles, as CDS's: each tile holds the next-brightest stars
  of its cell not already in its ancestors, capped at about 25k stars (about 200 KB packed).
  Tile selection by `query_disc_inclusive_nest` (`@hscmap/healpix`, MIT, 2.95 KB gzipped, verified
  against astropy in the previous round).
- **Magnitude limit follows the field of view** (Table D above), and a tile's fainter stars fade
  in as the order rises, as the imagery does.
- **Per-star data** the same 8 B as `hipparcos.bin` (24-bit RA and Dec, 8-bit magnitude, 8-bit
  colour). The 24-bit quantization is about 77 mas, well under a pixel at the narrowest field the
  tiles serve. A separate details file (8 B source ID plus a 2 B parallax) is fetched only for a
  tile the user selects from, as `hipparcos-details.bin` is.
- **Selection:** nearest star in screen space over the loaded visible tiles. A linear scan of
  about 1M points is a few milliseconds on a desktop (not measured here).
- **Proper motion and epoch:** Gaia positions are epoch 2016.0. The existing Hipparcos build
  applies proper motion to 2026.0; for fainter stars the 10-year shift is mostly under a pixel
  at fields of 1° and wider.
- **Frames:** positions are ICRS; the sky sphere needs the ICRS to TEME rotation (0.15-0.37° in
  2026, from the previous round).

**The band from real star density.** The density gradient is large: between two level-5 cells the
G<16 count was 2,381 (Orion) against 46,151 (Galactic centre), about 19x. Plotting resolved stars
shows the band emerging from their number. The faint unresolved light needs a separate layer:

- **CDS's Gaia DR3 colour flux map** (`CDS/P/DM/flux-color-Rp-G-Bp/I/355/gaiadr3`, JPEG, order 7,
  `ESA/Gaia mission/DPAC`) sums the flux of all 1.8 billion sources per pixel. Rendered from the
  order-3 Allsky file it's grainy, because each pixel is dominated by a few bright stars. Binned
  to coarser orders it's smooth.

| Binned order | Pixels | As a JPEG atlas (q85) |
|---|---|---|
| 8 | 786,432 | 367 KB |
| **7** | **196,608** | **74 KB** |
| 6 | 49,152 | 16 KB |
| 5 | 12,288 | 5 KB |

- Order 7 reads as a convincing Milky Way: the bulge, dust lanes and both Magellanic Clouds are
  present (see `flux/sky_gaia_color_order7_moll.png`).
- This replaces the 450 KB Deep Star Maps image with 74 KB, and it's *built from the same Gaia
  data* as the stars.
- Draw it additively behind the points. Fade it down as the field narrows and individual stars
  resolve.
- The FITS version (`G-flux-map`) has about 86,000x dynamic range between its 1st and 99.9th
  percentile pixels, so it needs a log stretch.

## 5. Recommended plan

**Layers by field of view**

| Range | Layer | Source |
|---|---|---|
| Any | **Hipparcos** (existing, 118,217) | The brightest stars. Gaia is incomplete here. |
| Any | **Glow**: Gaia colour flux map binned to order 7 (74 KB) | CDS flux map, `ESA/Gaia mission/DPAC` |
| ~60° down to ~1° | **Own Gaia tiles to G<16**, progressive, per-view budget | Built once from the Gaia archive |
| below ~1° | **Live cone query** to VizieR TAP, all Gaia sources | CDS (terms unconfirmed); fall back to the G<16 tiles |

**Build order** (each step is usable on its own):
1. **G<13 (7.4 M, 59 MB packed, about 300-600 tiles).** Proves tiling, budget and selection. About
   1-2.5 h of extraction.
2. **The glow layer** replacing the Milky Way image.
3. **G<16 (78 M, 624 MB packed).** Extraction is parallel by `source_id` range.
4. **Narrow-field live queries and the SIMBAD info card.**
5. G<18 only if the live query path proves unsuitable (2.4 GB packed).

**De-duplication with Hipparcos.** Drop Gaia stars within about 2″ of a Hipparcos star of
similar magnitude at build time (apply proper motion to a common epoch first). Whether a Gaia–
Hipparcos best-neighbour table exists in the archive was **not verified**.

**Bright-end check** (VizieR's Gaia DR3, nearest sources within 40″, brightest first):

| Star | Brightest Gaia source nearby | Reading |
|---|---|---|
| Sirius (V -1.46) | G = 8.5 | companion only; Sirius A absent |
| Rigel (V 0.13) | G = 6.6 | companion only; Rigel A absent |
| Betelgeuse (V ~0.4) | G = 13.4 | absent |
| Vega (V 0.03) | G = 15.8 | absent |
| Alnitak (V 1.77) | G = 16.7 | absent |
| Polaris (V 1.98) | G = 8.6 | companion only |
| **Mintaka (V 2.23)** | **G = 2.25** | **present** |

This is an empirical check, not a quote from ESA's documentation. It supports keeping Hipparcos.
(A first attempt at this check used the ESA archive during its downtime window and parsed an HTML
error page as an empty result; that result was discarded and the check re-run on VizieR.)

**Data budget** (G<16 plan): about 624 MB packed (about 507 MB gzipped) plus about 74 KB of glow,
plus about 780 MB of optional details (10 B per star), loaded per tile on demand. Typical session
download: 12-20 MB on desktop, 3-5 MB on a phone.

**Attribution text**
- Gaia: "Credit: ESA, Gaia DPAC", with the licence CC BY-NC 3.0 IGO linked, a note that the data
  were adapted (packed, magnitude-limited), and the non-commercial statement (as with Hipparcos
  now).
- Hipparcos/Tycho: "Credit: ESA".
- CDS services when used: "This research has made use of the SIMBAD database, CDS, Strasbourg
  Astronomical Observatory, France" (Wenger et al. 2000, A&AS 143, 9), and the same pattern for
  VizieR (Ochsenbein et al. 2000, A&AS 143, 23).
- Tycho-2 or 2MASS, if used: Høg et al. 2000, A&A 355, L27; and 2MASS's standard
  acknowledgement text.

## Risks

- **Licence:** everything here is non-commercial. If the site ever becomes commercial, the Gaia
  tiles, the glow layer and Hipparcos all have to be replaced. ESA asks for authorisation before
  any commercial use.
- **CDS access:** no published terms or rate limits for HiPS, TAP or Sesame. Tiles are slow (about
  1.1 s) and the TAP join timed out once. Plan for failure with the local tiles as the fallback.
- **Gaia archive availability:** it was down for a window on 2026-10-14, which affects a build,
  not serving from our own bucket.
- **Phone performance is unmeasured.**
- **Build effort:** 11-27 h of sequential extraction for G<16, or a 0.75 TB bulk download.
- **Bright end:** Gaia lacks many of the brightest stars, so de-duplication and a Hipparcos
  handoff matter.
- **Tycho-2 and 2MASS licences are unstated.** That's a reason to prefer the Gaia route.

## Open questions

1. Does CDS accept a public portfolio streaming its TAP and Sesame endpoints (a cone query per
   deep-zoom, a SIMBAD lookup per click)? Is there a rate expectation?
2. Which magnitude limit to ship first (G<13 vs G<16)? Table D suggests G<16 for fields down to
   about 25°.
3. How should the handoff between Hipparcos and Gaia be drawn so a star isn't doubled or
   missing: by magnitude (e.g. Hipparcos below V≈8) or by position match?
4. Does the phone budget of 0.3M points hold on a real mid-range phone? It needs a device test.
5. Are the Gaia–Hipparcos best-neighbour table and Bailer-Jones distances available in the
   archive and VizieR (unverified)?
6. Should an infrared (2MASS) mode be offered? It looked dramatic at the Galactic centre in test
   tiles, but that wasn't pursued.
