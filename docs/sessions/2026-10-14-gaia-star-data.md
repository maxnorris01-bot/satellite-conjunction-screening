# 2026-10-14 - Gaia star data (the data half of the streamed star layer)

Branch `feat/gaia-star-data`. Nothing is uploaded and nothing is merged. The data sits outside the
repo in `~/Desktop/Projects/star-data-2026-10/`. The viewer is a later round in `portfolio-site`.

## What changed and why

- **Format** (`docs/star-data-format.md`): Gaia DR3 stars brighter than G = 13, in 768 HEALPix
  order-3 tiles, brightest first, column layout, plus a lazily loaded details file per tile
  (source ID, parallax), a manifest with counts, sizes and checksums, and a glow atlas.
- **Scripts** (`scripts/star_data/`, README there): extract, pack, glow, verify, upload. They write
  only under the output folder given with `--out`/`--work`. Tests: `tests/test_star_data.py`.
- **Route**: the ESA Gaia archive TAP service (the VizieR route was only used to cross-check
  counts while ESA had a downtime window). Only archive data is used; no CDS HiPS tiles.
- **Extraction by source ID range, tiling by final position.** A Gaia `source_id >> 35` is the
  position's cell at the time the ID was assigned, which differs from the final position's cell for
  0.44% of stars at level 12 (1 in 392,000 at order 3). Fetching by ID range gets every star exactly
  once; tiling by final position puts it where the viewer looks. This corrects a claim in the
  research doc ("110/110"), which is amended.
- **Hipparcos handover** by position cross-match, not a magnitude cut (Gaia lacks Sirius A, Vega,
  Betelgeuse, Alnitak, Rigel A and Polaris A). Rule: both at epoch 2026.0; drop a Gaia source within
  3 arcsec of a Hipparcos star when |G - V| <= `min(6, 1 + 0.5 * max(0, BP-RP)^2)`; one best match
  per Hipparcos star. Verification found a fixed 2.0 guard left Proxima Centauri drawn twice (V - G
  is 2 mag or more for very red stars), hence the colour-aware guard. Tiles are assigned from the
  decoded (quantized) position because verification found 8 tiles with a star decoding just outside.
- **Glow atlas**: the unresolved light is the summed RP/G/BP flux of sources fainter than G = 13 per
  order-7 pixel (the brighter stars are drawn as points), white-balanced by channel medians, asinh
  stretched, 512 x 384 JPEG, 40.5 KB. A first version using all sources was speckled by single
  bright stars and was replaced.

## Problems found on the way (all fixed)

- The ESA sync TAP service silently truncates at 50,000 rows: four dense cells were short. Now
  `MAXREC=3,000,000` and every cell's row count is checked against the archive's own count.
- ESA downtime returned an HTML page that parsed as an empty result; now treated as "try later".
- A whole-sky async aggregate hit the 60 s job limit; the glow query is per level-2 cell, split on
  refusal. A CASE inside an aggregate is rejected (HTTP 400); a plain WHERE is used.

## Numbers

| | |
|---|---|
| Archive rows G < 13 (the archive's own count) | 7,369,627 |
| Extracted (768 cells, each equal to the archive's count) | 7,369,627 |
| Dropped as Hipparcos duplicates | 117,710 of 118,217 Hipparcos stars have a counterpart |
| Stars in tiles | 7,251,917 |
| Non-empty tiles | 768 of 768 |
| Stars per tile | min 2,125, median 5,908, max 52,834 |
| Tile files gzipped | min 14 KB, median 37 KB, p90 137 KB, max 335 KB; total 45.9 MB (6.3 B/star) |
| Details files gzipped | total 56.3 MB (7.8 B/star) |
| Manifest | 313 KB (102 KB gzipped); glow atlas 40.5 KB |
| Whole folder | 101 MB, 1,538 files |
| Extraction run time | 72.8 min (2 workers, polite pauses) |
| No colour / no parallax | 17,269 / 56,185 stars |

Why 6.3 bytes/star: ra and dec 3 bytes each, G and colour 1 byte each is 8 raw; the sorted G column
and spatially sorted positions compress to 6.3. Source ID is 8 incompressible bytes, so it lives in
the lazy details file (the tile download stays small: a 10 degree field is 3 to 6 files, about
0.1 to 0.5 MB).

Verification (`verify.py`, `verify_report.json`): `ok: true`, no problems. Checks: every file's
SHA-256 against the manifest, headers, brightest-first order, each star inside its tile, no
duplicate source IDs, kept + dropped = archive per magnitude bin (8 to 13), and 15 known stars
looked up in SIMBAD (Sirius A in Hipparcos only, Sirius B / Rigel B / Polaris B / Teegarden's Star
in the tiles, Proxima, Barnard's, Kapteyn's, Vega, Betelgeuse in Hipparcos only).

Glow check: the Mollweide preview (`work/glow_preview_mollweide.png`) shows the bulge, the Great
Rift dust lanes and both Magellanic Clouds. Not a pixel comparison with the research's reference
images; judged by eye.

Sample tiles (from the manifest): tile 437 (sparsest) 2,125 stars, 14 KB, G 4.6 to 13.0;
tile 637 (median) 5,908 stars, 37 KB, G 6.3 to 13.0; tile 592 (densest, bulge) 52,834 stars,
335 KB, G 6.0 to 13.0, 116 stars brighter than 8 and 587 brighter than 9.

Test/lint: `make lint` clean; `uv run pytest tests/test_star_data.py` 26 passed. No prompts or agent
logic changed, so `make eval-fast` is not applicable.

## Upload plan (NOT run)

Prefix `stars/v1/`. It does not touch `objects/`, `reports/`, `history/` or `snapshots/`;
`upload.py` only ever writes under the prefix it is given. The bucket credentials exist only as Fly app secrets,
so it runs in a throwaway Machine from the app's image (credentials never printed).

```
cd ~/Desktop/Projects/satellite-conjunction-screening
# 0. dry run, locally: lists every key and header, sends nothing
uv run python scripts/star_data/upload.py plan --src ~/Desktop/Projects/star-data-2026-10/stars-v1

# 1. a throwaway Machine from the app image (secrets arrive as env vars)
IMAGE=registry.fly.io/satellite-conjunction-screening:$(git rev-parse --short HEAD)   # after: make fly-build
fly machine run $IMAGE sleep 7200 --name star-upload --region sjc -a satellite-conjunction-screening
fly machine list -a satellite-conjunction-screening        # note the star-upload machine id

# 2. copy the data and the script in (about 101 MB)
fly ssh sftp shell --machine <ID> -a satellite-conjunction-screening
#    sftp> put -R /Users/maxnorris/Desktop/Projects/star-data-2026-10/stars-v1 /tmp/stars-v1
#    sftp> put scripts/star_data/upload.py /tmp/upload.py

# 3. upload (manifest is sent last)
fly ssh console --machine <ID> -a satellite-conjunction-screening \
  -C "python /tmp/upload.py put --src /tmp/stars-v1 --prefix stars/v1/ --go"

# 4. verify the public URLs (also works from your Mac, no credentials needed)
uv run python scripts/star_data/upload.py verify --src ~/Desktop/Projects/star-data-2026-10/stars-v1

# 5. remove the throwaway Machine
fly machine destroy <ID> --force -a satellite-conjunction-screening
```

- **Headers** (set per object): `*.bin.gz` `Content-Type: application/octet-stream`,
  `Content-Encoding: gzip`; JSON `application/json`; JPEG `image/jpeg`; all
  `Cache-Control: public, max-age=31536000, immutable` (the path is versioned, so a new build is
  `stars/v2/`, never an overwrite). `put` refuses to overwrite an existing key without `--overwrite`.
- **CORS**: production origins are already allowed on the bucket. Vercel preview origins are
  rejected until the separate CORS proposal (`fix/bucket-cors-previews`) is applied, so the viewer
  round's previews cannot load this data until then.
- **Cost**: about 0.1 GB at $0.02/GB-month (inside the 5 GB free tier); GETs $0.0005 per 1,000
  after 100,000 free; no egress fees.
- **Rollback**: `python /tmp/upload.py delete --prefix stars/v1/ --go` in the same Machine (or
  `aws s3 rm --recursive` on that prefix). Nothing else references the prefix until the viewer ships.

## Open questions / flag for review

- The 507 Hipparcos stars with no Gaia counterpart stay Hipparcos-only; 454 of them had none within
  3 arcsec at all. They are fine (drawn once) but are a list worth a look if a double star ever
  looks wrong.
- G (Gaia) and V (Hipparcos) differ by up to a magnitude for red stars, so one shared limiting
  magnitude across the two layers needs a choice in the viewer round.
- CC BY-NC 3.0 IGO: attribution text is in `manifest.json`; the viewer must show it. Commercial use
  of the site would need ESA's authorisation.
- Glow checked by eye only.

## Next command

`git diff main --stat`, then, when happy, the upload plan above (step 0 first).
