# star_data: Gaia star tiles for the space view

Builds the data half of the streamed star layer: Gaia DR3 stars brighter than G = 13 (about 7.4
million, minus those already in `hipparcos.bin`) as compact HEALPix tiles, plus a small Milky Way
glow map. Output goes **outside the repo** (default `~/Desktop/Projects/star-data-2026-10/`), is
never committed, and is uploaded to the bucket by hand under a versioned prefix.

The file format is documented in [`docs/star-data-format.md`](../../docs/star-data-format.md); that
is the contract the `portfolio-site` viewer reads. Background and measurements:
[`docs/research/2026-10-streamed-star-catalogue.md`](../../docs/research/2026-10-streamed-star-catalogue.md).

## Run it (from the repo root)

```bash
W=~/Desktop/Projects/star-data-2026-10
HIP=~/Desktop/Projects/portfolio-site/public/data/stars/hipparcos.bin   # read only

# 1. The archive's own totals, to check against (about a minute)
uv run python -m scripts.star_data.extract counts --out $W/work

# 2. Extract G < 13, one level-3 HEALPix cell per request (about 1 to 1.5 hours, resumable)
uv run python -m scripts.star_data.extract run --out $W/work          # --workers 2 by default

# 3. Pack: epoch 2026.0, Hipparcos handover, tiles, details, manifest (a few minutes)
uv run python -m scripts.star_data.pack --work $W/work --hipparcos $HIP --out $W/stars-v1

# 4. The glow map: per-cell aggregates on the archive, then the image (about 15 minutes)
uv run python -m scripts.star_data.glow query --out $W/work
uv run --with pillow python -m scripts.star_data.glow build --work $W/work --out $W/stars-v1

# 5. Check everything, independently of the packer
uv run python -m scripts.star_data.verify --out $W/stars-v1 --work $W/work --hipparcos $HIP
```

Every step writes only under `$W`. `extract run` and `glow query` keep a file per finished cell, so
re-running the same command after an interruption (or an archive downtime) picks up where it
stopped. The archive was down for a window on 2026-10-14; the scripts treat its HTML downtime page
as "try later", never as data.

## Modules

| File | What it does |
|---|---|
| `healpix.py` | nested HEALPix `ang2pix` in numpy, and the `source_id` to cell shift |
| `encoding.py` | the tile and details binary formats and the quantization constants |
| `crossmatch.py` | the Hipparcos handover rule and proper-motion propagation |
| `extract.py` | archive extraction (`run`) and the archive's own totals (`counts`) |
| `pack.py` | the packer: tiles, details, manifest, build report |
| `glow.py` | the all-sky glow atlas (`query`, `build`) |
| `verify.py` | the independent checks, including known stars looked up in SIMBAD |
| `upload.py` | the bucket upload, dry run by default (see below) |

Tests: `uv run pytest tests/test_star_data.py` (HEALPix reference values from astropy-healpix, real
Gaia rows, encodings, the handover rule on known cases, an end-to-end pack on a synthetic work
folder, and the upload plan).

## Upload (not done by these scripts unless you run it)

`upload.py` is standalone (boto3 only) and reads the bucket from the same environment variables the
daily run uses, which exist only inside the Fly app. So it runs in a throwaway Machine built from the
app's image, with the data copied in over `fly ssh sftp`; see the session doc
[`docs/sessions/2026-10-14-gaia-star-data.md`](../../docs/sessions/2026-10-14-gaia-star-data.md)
for the exact commands, headers, verification and rollback. It only ever touches the prefix it is
given (default `stars/v1/`), never `objects/`, `reports/`, `history/` or `snapshots/`.

## Etiquette

The archive's servers are shared. The extraction uses 2 workers, a pause before each request and
exponential backoff with `Retry-After`, and asks for a cell at a time rather than the whole
catalogue. Don't raise `--workers` casually, and don't copy CDS's catalogue HiPS tiles (CDS marks
them "unclonable"); this data is built from the archive.
