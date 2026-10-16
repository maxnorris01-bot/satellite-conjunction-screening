# Star data format (version 1)

The data half of the streamed star layer for the `portfolio-site` space view. Built from the Gaia
DR3 archive by `scripts/star_data/` (see that folder's README for how to run it). The viewer round
in `portfolio-site` reads these files; this document is its contract.

Background and the reasoning behind the choices:
[`docs/research/2026-10-streamed-star-catalogue.md`](research/2026-10-streamed-star-catalogue.md).

## What's in a build

```
stars/v1/
  manifest.json            the index: tiles, counts, sizes, checksums, encodings, attribution
  tiles/o3-NNNN.bin.gz     one file per HEALPix order-3 tile: position, magnitude, colour
  details/o3-NNNN.bin.gz   the same stars, same order: source ID and parallax (loaded on demand)
  glow-o7.jpg              the Milky Way glow atlas (512 x 384 RGB, HEALPix order 7)
  glow.json                how to read and credit the glow atlas
```

Everything is **stored gzip-compressed** and should be served with `Content-Encoding: gzip` and
`Content-Type: application/octet-stream` (JSON files: `application/json`; the JPEG is already
compressed and is served as is). A browser `fetch` then returns the decoded bytes, as it does for
`objects/current.json`. The manifest's `bytes` are the decoded sizes and `gz_bytes` what's stored.

## Which stars

- **Gaia DR3 sources brighter than G = 13.0** (`phot_g_mean_mag < 13`): 7,369,627 rows extracted, 7,251,917 kept after the handover.
- **Minus the stars the Hipparcos file already covers.** The viewer draws `hipparcos.bin` and these
  tiles together; a Gaia source that is a Hipparcos star is left out so nothing is drawn twice.
  The rule (`scripts/star_data/crossmatch.py`):
  - both catalogues at epoch 2026.0 (Gaia positions are moved with Gaia proper motions);
  - a Gaia source is dropped when a Hipparcos star lies within **3.0 arcsec** and
    **|G - V| <= guard**, where `guard = min(6, 1 + 0.5 * max(0, BP-RP)^2)` (3 if the source has no
    colour). V - G grows with redness (median 0.03 for blue stars, 2.2 above BP-RP 4), so a fixed
    tolerance left Proxima Centauri drawn twice. Only the single best match per Hipparcos star is
    dropped;
  - result: 117,710 of the 118,217 Hipparcos stars have a Gaia counterpart and 117,710 Gaia sources
    were dropped; the other 507 Hipparcos stars (mostly very bright, or close binaries Gaia
    resolves differently) stay Hipparcos-only;
  - no magnitude cut: every Hipparcos star stays in the Hipparcos layer, and every other Gaia star
    is in the tiles.
  - Why a rule and not "Hipparcos brighter than V = N": Gaia is missing many of the brightest
    stars (Sirius A, Vega, Betelgeuse, Alnitak, Rigel A and Polaris A are absent), and Hipparcos is
    patchy near V = 8-9, so a magnitude cut would lose stars or double them. A position match
    keeps exactly one copy of each. The magnitude guard keeps faint companions next to bright
    stars (Sirius B, Rigel B, Polaris B stay in the Gaia tiles).
- **Epoch 2026.0**, ICRS (J2000 axes): the same convention as `hipparcos.bin`, so the viewer's
  existing precession and frame code applies unchanged.

## Tiling

- **HEALPix nested, order 3**: 768 tiles of about 53.7 square degrees (nside = 8). A tile's number
  is `ipix`; file `o3-NNNN` is the zero-padded `ipix`. Empty tiles have no file.
- A star belongs to the tile of its **final (2026.0) position as decoded from the quantized
  values**, computed with the standard nested `ang2pix`, so no tile holds a star that decodes
  outside it. The viewer needs a HEALPix library only to pick which tiles cover the view
  (`query_disc_inclusive_nest`, e.g. `@hscmap/healpix`, MIT, verified against astropy-healpix).
- **Why order 3 and not a pyramid.** Tiles are 14 KB to 335 KB gzipped (median 37 KB), so a wide view needs on the order
  of 100 files and a 10 degree view needs 3 to 6. Finer tiles would multiply requests for no gain
  at this depth; a deeper G<16 round can add a second, finer order and the manifest already
  carries `order` per tile.
- **Brightest first inside every tile.** Stars are sorted by G (then source ID). To show only stars
  brighter than a limit, take the first `k` entries of each column; the manifest gives `k` for
  whole magnitudes (`n_lt`, below), so the viewer can decide before it decodes anything.

## Tile file (`GAIT`, version 1)

Little-endian. A 32-byte header, then four columns of `count` entries (columns compress better
than records; the sorted magnitude column nearly vanishes, 0.01 byte/star):

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | magic `GAIT` |
| 4 | 2 | version u16 = 1 |
| 6 | 1 | order u8 (3) |
| 7 | 1 | reserved |
| 8 | 4 | ipix u32 |
| 12 | 4 | count u32 |
| 16 | 4 | epoch f32 (2026.0) |
| 20 | 12 | reserved |
| 32 | 3 x count | ra u24 |
| | 3 x count | dec u24 |
| | count | mag u8 |
| | count | colour u8 |

| Column | Decode |
|---|---|
| `ra` | `ra_deg = value / 2^24 * 360` (77 mas steps) |
| `dec` | `dec_deg = value / (2^24 - 1) * 180 - 90` (39 mas steps) |
| `mag` | `G = value / 11 - 1.0` (0.09 mag steps; range -1.0 to 22.2) |
| `colour` | `BP-RP = value / 25 - 1.0`; **0 means no colour** (range -0.96 to 9.2) |

Note the differences from `hipparcos.bin`: the magnitude is Gaia **G** (not Johnson V) with a
different scale so G up to 21 fits in a later round, and the colour is **BP-RP** (not B-V), which
runs about 1.3 to 1.5 times the B-V of the same star. The viewer needs its own BP-RP to colour
mapping (or a conversion); a relation is not part of this format and should be chosen and checked
in the viewer round. Gaia magnitudes are also not Hipparcos magnitudes: G is about 0.1 to 0.5
brighter than V depending on colour, which matters if the two layers share one limiting magnitude.

## Details file (`GAID`, version 1)

Loaded only for a selected star or a visited tile. Same stars in the **same order** as the tile.
A 32-byte header (`GAID`, version u16 = 1, reserved u16, count u32 at offset 8), then columns:

| Column | Size | Decode |
|---|---|---|
| `source_id` | u64 x count | Gaia DR3 source ID: look up in SIMBAD as `Gaia DR3 <id>` |
| `parallax` | i16 x count | `mas = value / 40`; -32768 = none |
| `parallax_error` | u8 x count | `mas = value / 200`; 255 = none or 1.27 mas or more |
| `flags` | u8 x count | bit 0 (1): no BP-RP colour |

12 bytes per star. Kept: the source ID (the only way to look a star up later; 8 bytes and
incompressible), and parallax with its error, so the info card can show a distance only when the
parallax is significant (parallax over error of about 5 or more) without a network request. Not
kept: proper motion (SIMBAD returns it with the lookup), photometry beyond G and BP-RP, anything
else in the 225-column archive row.

## Manifest (`manifest.json`)

JSON, `version`, `format_version`, `epoch`, `source` (catalogue, service, selection, retrieval
dates, the archive's own total), `handover` (the rule and its parameters), `tiling`, `encoding`
(every constant above, machine-readable), `totals`, `attribution`, and `tiles`: one entry per
tile:

```json
{ "order": 3, "ipix": 450, "count": 28307, "file": "tiles/o3-0450.bin.gz",
  "bytes": 226488, "gz_bytes": 175012, "sha256": "...",
  "details_file": "details/o3-0450.bin.gz", "details_bytes": 339716, "details_gz_bytes": 305521,
  "details_sha256": "...", "g_min": 4.19, "g_max": 13.0,
  "n_lt": [212, 640, 1850, 5100, 12600, 28307] }
```

`n_lt[i]` is the number of stars in the tile with decoded G < `encoding.mag_bins[i]`
(8, 9, 10, 11, 12, 13). `sha256` is of the stored (gzipped) file. A viewer should cache by the
versioned path, so a new build is a new `v2/` prefix rather than an overwrite.

## The glow atlas (`glow-o7.jpg`, `glow.json`)

An all-sky colour map for the unresolved light of the Milky Way, built from Gaia flux sums (not
from CDS's flux map). HEALPix **nested order 7** (196,608 pixels, about 0.46 degrees), ICRS.
Pixel `i` is at column `i % 512`, row `i // 512` of a 512 x 384 JPEG (quality 92, **4:4:4, no
chroma subsampling**: in this layout vertical neighbours are unrelated sky positions, so
subsampled chroma would bleed colour between them). The method (channel balance
and the asinh stretch) is in `scripts/star_data/glow.py` and `glow.json`. Draw it additively behind
the stars and fade it down as the field narrows and stars resolve. Its credit is the same as the
tiles'.

## Attribution (must be shown while the data is on screen)

- **Credit: ESA, Gaia DPAC** (the credit line ESA's archive terms specify for Gaia).
- Licence **CC BY-NC 3.0 IGO**, linked: https://creativecommons.org/licenses/by-nc/3.0/igo/ , with
  a note that the data were adapted (selected, moved to epoch 2026.0, packed).
- The site shows a non-commercial note next to it, as it does for Hipparcos.
- The full text is in `manifest.json` under `attribution`.
- **If the site ever becomes commercial this data must be replaced**: ESA asks for authorisation
  before any commercial use (data.licences@esa.int). Hipparcos has the same condition.

## Known limits

- G < 13 only. Fainter stars (G < 16, about 78 million) are a later data round; narrow fields can
  use live cone queries (see the research doc).
- Positions are moved with proper motion only; radial motion and parallax are ignored.
- A star's ID cell and position cell can differ (0.44% at level 12, about 1 in 400,000 at order 3);
  tiles are by position, so this never matters to the viewer.
- The Gaia bright end is incomplete, so the brightest stars come from the Hipparcos file.

## Sizes of the G < 13 build

| | Decoded | Stored (gzip) |
|---|---|---|
| Tiles (768 files) | 58.0 MB | 45.9 MB (6.3 bytes/star) |
| Details (768 files) | 87.0 MB | 56.3 MB (7.8 bytes/star) |
| Manifest | 313 KB | 102 KB |
| Glow atlas | | 74.7 KB (JPEG q92, 4:4:4) |

Tile files: min 14 KB, median 37 KB, p90 137 KB, max 335 KB gzipped; 469 under 50 KB, 23 over 200 KB.
Stars per tile: min 2,125, median 5,908, max 52,834. In total 1,539 files (768 + 768 + manifest + glow
JPEG + glow JSON), about 102.5 MB.
