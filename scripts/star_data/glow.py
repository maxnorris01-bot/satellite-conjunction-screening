"""The Milky Way glow map: the unresolved light of the Gaia sky, as a small colour image.

    W=~/Desktop/Projects/star-data-2026-10
    uv run python -m scripts.star_data.glow query --out $W/work
    uv run --with pillow python -m scripts.star_data.glow build --work $W/work --out $W/stars-v1

`query` runs aggregate queries on the ESA Gaia archive: per HEALPix order-7 pixel, the number of
sources and the summed G, BP and RP fluxes of the sources FAINTER than the tiles' limit (G >= 13).
That is the glow: the unresolved remainder, smooth and complementary to the tiles. Summing every
source gave a speckled map (a pixel's flux is dominated by its few bright stars, which the tiles
already draw one by one) and would double-count them. The sky is asked for in level-2 cells (192
queries, each split into four if the archive refuses it) because a whole-sky job was aborted at the
archive's 60 s execution limit. Finished cells are kept in glow_cells_faint/ so a run resumes. It
is independent of the star tiles and of CDS's flux maps.

`build` turns those sums into an 8-bit RGB atlas (method below) plus glow.json describing it.

Method (documented so the result can be reproduced or restyled):
  1. Channels: R = summed RP flux, G = summed G flux, B = summed BP flux (the same assignment CDS
     uses, so a red star looks red).
  2. White balance: each channel is scaled so its all-sky median matches the G channel's, so a
     typical high-latitude field is neutral and the bulge comes out warm.
  3. Brightness: luminance L = mean of the balanced channels, stretched with
     asinh(L / L0) / asinh(Lmax / L0), L0 = the median pixel, Lmax = the 99.95th percentile pixel;
     the colour ratios are kept (each pixel is scaled by stretched_L / L, then clipped by its
     largest channel).
  4. Layout: HEALPix NESTED order 7 (196,608 pixels), pixel i at atlas column i % 512, row i // 512
     in a 512 x 384 image, so pixels that are close on the sky are close in the image.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import time
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from scripts.star_data.extract import TryLater, tap_csv
from scripts.star_data.healpix import ang2pix_nest

ORDER = 7
NPIX = 12 * 4**ORDER
ATLAS_W = 512
ATLAS_H = NPIX // ATLAS_W
FAINT_G = 13.0  # the tiles' limit: the glow is the light of everything fainter
CELL_ORDER = 2
CELL_SHIFT_ORDER = 12  # Gaia source ids carry a level-12 index above bit 35
QUERY = (
    "SELECT GAIA_HEALPIX_INDEX(7, source_id) AS hpx, COUNT(*) AS n, "
    "SUM(phot_g_mean_flux) AS fg, SUM(phot_bp_mean_flux) AS fbp, SUM(phot_rp_mean_flux) AS frp "
    "FROM gaiadr3.gaia_source WHERE phot_g_mean_mag >= {g} AND source_id >= {lo} "
    "AND source_id < {hi} GROUP BY hpx"
)


def _id_range(cell: int, order: int) -> tuple[int, int]:
    shift = 35 + 2 * (CELL_SHIFT_ORDER - order)
    return cell << shift, (cell + 1) << shift


def _aggregate(lo: int, hi: int) -> list[dict[str, str]]:
    q = QUERY.format(g=FAINT_G, lo=lo, hi=hi)
    return list(csv.DictReader(io.StringIO(tap_csv(q, timeout=180).decode())))


def aggregate_cell(cell: int, order: int, depth: int = 0) -> list[dict[str, str]]:
    """Aggregate one sky cell; if the archive refuses it, ask for its four children instead."""
    lo, hi = _id_range(cell, order)
    last: Exception | None = None
    for attempt in range(3):
        try:
            return _aggregate(lo, hi)
        except (TryLater, urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(10 * 2**attempt)
    if depth >= 3:
        raise RuntimeError(f"cell {cell} at order {order} failed: {last}")
    print(f"  cell {cell} (order {order}) refused ({last}); splitting", flush=True)
    rows: list[dict[str, str]] = []
    for c in range(4 * cell, 4 * cell + 4):
        rows += aggregate_cell(c, order + 1, depth + 1)
    return rows


def cmd_query(args: argparse.Namespace) -> int:
    out = Path(args.out).expanduser()
    (out / "glow_cells_faint").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    nf = np.zeros(NPIX, dtype=np.int64)
    flux = np.zeros((NPIX, 3), dtype=np.float64)  # R (rp), G, B (bp)
    n_cells = 12 * 4**CELL_ORDER
    pixels = 0
    for cell in range(n_cells):
        f = out / "glow_cells_faint" / f"g{CELL_ORDER}_{cell:03d}.json"
        if f.exists():
            rows = json.loads(f.read_text())
        else:
            rows = aggregate_cell(cell, CELL_ORDER)
            f.write_text(json.dumps(rows))
        for r in rows:
            i = int(r["hpx"])
            nf[i] += int(r["n"])
            flux[i] += [float(r["frp"] or 0), float(r["fg"] or 0), float(r["fbp"] or 0)]
        pixels += len(rows)
        print(
            f"[{cell + 1}/{n_cells}] {len(rows)} pixels, {int(nf.sum()):,} sources, "
            f"{(time.time() - t0) / 60:.1f} min",
            flush=True,
        )
    np.savez_compressed(out / "glow_flux_faint_order7.npz", n=nf, flux=flux)
    (out / "glow_query.json").write_text(
        json.dumps(
            {
                "query": QUERY.replace("{g}", f"{FAINT_G:g}")
                + " (run per level-2 cell, with the source_id range filled in)",
                "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "seconds": round(time.time() - t0, 1),
                "pixels_returned": pixels,
                "sources_faint": int(nf.sum()),
                "faint_g": FAINT_G,
            },
            indent=1,
        )
    )
    print(f"{pixels:,} pixels, {int(nf.sum()):,} sources fainter than G={FAINT_G:g}", flush=True)
    return 0


def stretch(
    flux: NDArray[np.float64], n: NDArray[np.int64]
) -> tuple[NDArray[np.uint8], dict[str, object]]:
    """Method steps 2 and 3. Returns the (NPIX, 3) uint8 image and the parameters used."""
    have = n > 0
    g_med = float(np.median(flux[have, 1]))
    scale = np.array([g_med / float(np.median(flux[have, c])) for c in range(3)])
    bal = flux * scale
    lum = bal.mean(axis=1)
    l0 = float(np.median(lum[have]))
    lmax = float(np.percentile(lum[have], 99.95))
    s = np.arcsinh(lum / l0) / np.arcsinh(lmax / l0)
    factor = np.where(lum > 0, s / np.maximum(lum, 1e-30), 0.0)
    rgb = bal * factor[:, None]
    peak = np.maximum(rgb.max(axis=1), 1.0)
    rgb = rgb / peak[:, None]
    img = np.clip(np.rint(rgb * 255.0), 0, 255).astype(np.uint8)
    return img, {"channel_scale_rgb": [float(x) for x in scale], "L0": l0, "Lmax_p99_95": lmax}


def galactic_to_equatorial(
    l_deg: NDArray[np.float64], b_deg: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Galactic (l, b) to ICRS (ra, dec), degrees (IAU 1958 pole, J2000 constants)."""
    a_ngp, d_ngp, l_ncp = np.radians(192.85948), np.radians(27.12825), np.radians(122.93192)
    lon, b = np.radians(l_deg), np.radians(b_deg)
    sd = np.sin(d_ngp) * np.sin(b) + np.cos(d_ngp) * np.cos(b) * np.cos(l_ncp - lon)
    dec = np.arcsin(np.clip(sd, -1, 1))
    y = np.cos(b) * np.sin(l_ncp - lon)
    x = np.cos(d_ngp) * np.sin(b) - np.sin(d_ngp) * np.cos(b) * np.cos(l_ncp - lon)
    ra = np.mod(a_ngp + np.arctan2(y, x), 2 * np.pi)
    return np.degrees(ra), np.degrees(dec)


def mollweide(img_nested: NDArray[np.uint8], width: int = 1600) -> NDArray[np.uint8]:
    """Galactic-centred Mollweide preview of an order-7 nested image (for checking by eye)."""
    h = width // 2
    xs = (np.arange(width) + 0.5) / width * 2 - 1
    ys = 1 - (np.arange(h) + 0.5) / h * 2
    xx, yy = np.meshgrid(xs * 2 * np.sqrt(2), ys * np.sqrt(2))
    th = np.arcsin(np.clip(yy / np.sqrt(2), -1, 1))
    inside = (xx / (2 * np.sqrt(2))) ** 2 + (yy / np.sqrt(2)) ** 2 <= 1
    lat = np.arcsin(np.clip((2 * th + np.sin(2 * th)) / np.pi, -1, 1))
    lon = np.pi * xx / (2 * np.sqrt(2) * np.cos(th) + 1e-12)
    l_deg = np.mod(np.degrees(-lon), 360.0)
    b_deg = np.degrees(lat)
    ra, dec = galactic_to_equatorial(l_deg[inside], b_deg[inside])
    idx = ang2pix_nest(ORDER, ra, dec)
    out = np.zeros((h, width, 3), dtype=np.uint8)
    out[inside] = img_nested[idx]
    return out


def cmd_build(args: argparse.Namespace) -> int:
    from PIL import Image  # pillow: `uv run --with pillow`

    work, out = Path(args.work).expanduser(), Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    z = np.load(work / "glow_flux_faint_order7.npz")
    q = json.loads((work / "glow_query.json").read_text())
    img, params = stretch(z["flux"], z["n"])
    atlas = img.reshape(ATLAS_H, ATLAS_W, 3)
    jpg = io.BytesIO()
    Image.fromarray(atlas).save(jpg, "JPEG", quality=args.quality, subsampling=0, optimize=True)
    png = io.BytesIO()
    Image.fromarray(atlas).save(png, "PNG", optimize=True)
    (out / "glow-o7.jpg").write_bytes(jpg.getvalue())
    meta = {
        "name": "gaia-dr3-glow",
        "version": "v1",
        "healpix": {"scheme": "nested", "order": ORDER, "pixels": NPIX, "frame": "ICRS"},
        "image": {
            "file": "glow-o7.jpg",
            "width": ATLAS_W,
            "height": ATLAS_H,
            "layout": f"pixel i at column i % {ATLAS_W}, row i // {ATLAS_W}",
            "format": f"JPEG 8-bit RGB, quality {args.quality}, 4:4:4 (no chroma subsampling)",
            "bytes": len(jpg.getvalue()),
            "sha256": hashlib.sha256(jpg.getvalue()).hexdigest(),
            "png_bytes_for_comparison": len(png.getvalue()),
        },
        "layer": f"flux of every Gaia source fainter than G = {q['faint_g']:g} (the unresolved "
        "remainder: the star tiles hold the brighter ones)",
        "method": "asinh stretch of balanced summed RP/G/BP flux; see scripts/star_data/glow.py",
        "stretch": params,
        "source": {
            "catalogue": f"Gaia DR3 gaia_source, sources with G >= {q['faint_g']:g}",
            "sources_in_layer": q["sources_faint"],
            "query": q["query"],
            "retrieved_utc": q["retrieved_utc"],
        },
        "attribution": {
            "credit": "Credit: ESA, Gaia DPAC",
            "licence": "CC BY-NC 3.0 IGO",
            "text": "Derived from Gaia DR3 (Credit: ESA, Gaia DPAC), CC BY-NC 3.0 IGO: fluxes "
            "of sources fainter than G = 13 summed per HEALPix order-7 pixel, colour-balanced "
            "and stretched.",
        },
    }
    (out / "glow.json").write_text(json.dumps(meta, indent=1))
    Image.fromarray(mollweide(img)).save(work / "glow_preview_mollweide.png")
    all_file = work / "glow_flux_order7_all_sources_only.npz"  # optional: the first, speckled pass
    if all_file.exists():
        a = np.load(all_file)
        Image.fromarray(mollweide(stretch(a["flux"], a["n"])[0])).save(
            work / "glow_preview_all_sources_mollweide.png"
        )
    print(f"glow-o7.jpg {len(jpg.getvalue()):,} B (PNG would be {len(png.getvalue()):,} B)")
    print("preview:", work / "glow_preview_mollweide.png")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("query")
    q.add_argument("--out", required=True)
    b = sub.add_parser("build")
    b.add_argument("--work", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--quality", type=int, default=92)
    args = p.parse_args(argv)
    return cmd_query(args) if args.cmd == "query" else cmd_build(args)


if __name__ == "__main__":
    sys.exit(main())
