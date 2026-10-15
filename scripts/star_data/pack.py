"""Pack the extracted Gaia cells into the viewer's tile files, details files and manifest.

    uv run python -m scripts.star_data.pack \
        --work ~/Desktop/Projects/star-data-2026-10/work \
        --hipparcos ~/Desktop/Projects/portfolio-site/public/data/stars/hipparcos.bin \
        --out  ~/Desktop/Projects/star-data-2026-10/stars-v1

Steps: load all cells, check them against the archive's own totals, move every position to epoch
2026.0 (as hipparcos.bin is), drop the Gaia sources that are Hipparcos stars (crossmatch.py), assign
each star to its order-3 HEALPix tile by its 2026.0 position, sort each tile brightest first,
and write gzip-compressed tile and details files plus manifest.json. Deterministic: the same input
gives byte-identical output (gzip mtime 0, stable sort).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scripts.star_data import encoding as enc
from scripts.star_data.crossmatch import (
    GUARD_BASE,
    GUARD_COLOUR_TERM,
    GUARD_MAX,
    GUARD_NO_COLOUR,
    RADIUS_ARCSEC,
    hipparcos_duplicates,
    load_hipparcos,
    propagate,
)
from scripts.star_data.healpix import ang2pix_nest, n_cells, source_id_cell

ORDER = 3
GAIA_EPOCH = 2016.0
EPOCH = 2026.0  # the same epoch hipparcos.bin is propagated to
MAG_BINS = [8, 9, 10, 11, 12, 13]  # the manifest's per-tile cumulative counts: stars with G < bin
ATTRIBUTION = {
    "credit": "Credit: ESA, Gaia DPAC",
    "text": (
        "Star positions, magnitudes and colours from Gaia DR3 (Gaia Collaboration, 2022), Credit: "
        "ESA, Gaia DPAC, distributed under CC BY-NC 3.0 IGO "
        "(https://creativecommons.org/licenses/by-nc/3.0/igo/). Adapted by selecting stars "
        "brighter than G = 13, moving positions to epoch 2026.0 with Gaia proper motions, removing "
        "stars that are in the Hipparcos file, and quantizing positions, magnitudes and colours."
    ),
    "licence": "CC BY-NC 3.0 IGO",
    "non_commercial": True,
    "if_commercial": "ESA asks for authorisation before any commercial use "
    "(data.licences@esa.int).",
}


def gz(data: bytes) -> bytes:
    return gzip.compress(data, 9, mtime=0)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_cells(work: Path) -> tuple[dict[str, np.ndarray], list[dict[str, object]]]:
    metas: list[dict[str, object]] = []
    parts: dict[str, list[np.ndarray]] = {}
    files = sorted((work / "cells").glob("c3_*.npz"))
    if len(files) != n_cells(ORDER):
        raise SystemExit(f"expected {n_cells(ORDER)} cells, found {len(files)}: run extract first")
    for f in files:
        metas.append(json.loads(f.with_suffix(".json").read_text()))
        with np.load(f) as z:
            for k in z.files:
                parts.setdefault(k, []).append(z[k])
    return {k: np.concatenate(v) for k, v in parts.items()}, metas


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", required=True)
    p.add_argument("--hipparcos", required=True, help="the site's hipparcos.bin (read only)")
    p.add_argument("--out", required=True)
    p.add_argument("--version", default="v1")
    a = p.parse_args(argv)
    work, out = Path(a.work).expanduser(), Path(a.out).expanduser()
    (out / "tiles").mkdir(parents=True, exist_ok=True)
    (out / "details").mkdir(parents=True, exist_ok=True)

    d, metas = load_cells(work)
    n_in = len(d["source_id"])
    print(f"loaded {n_in:,} rows from {len(metas)} cells", flush=True)

    # --- completeness and duplicates against the archive's own totals
    counts = json.loads((work / "archive_counts.json").read_text())
    per_cell = np.array([int(m["rows"]) for m in metas])  # type: ignore[call-overload]
    archive_cells = np.array([counts["cells"].get(str(i), 0) for i in range(n_cells(ORDER))])
    if not np.array_equal(per_cell, archive_cells):
        bad = np.flatnonzero(per_cell != archive_cells)
        raise SystemExit(f"cell counts differ from the archive in {len(bad)} cells, e.g. {bad[:5]}")
    if len(np.unique(d["source_id"])) != n_in:
        raise SystemExit("duplicate source_id across cells")
    by_bin = np.bincount(np.floor(d["g"]).astype(int))
    for gb, n in counts["by_floor_g"].items():
        if int(by_bin[int(gb)]) != int(n):
            raise SystemExit(f"magnitude bin {gb}: {by_bin[int(gb)]} != archive {n}")
    print("counts match the archive per cell and per magnitude bin", flush=True)

    # --- epoch 2026.0
    ra, dec = propagate(d["ra"], d["dec"], d["pmra"], d["pmdec"], EPOCH - GAIA_EPOCH)

    # --- Hipparcos handover
    hip = load_hipparcos(Path(a.hipparcos).expanduser())
    drop, hip_of, sep = hipparcos_duplicates(
        ra, dec, d["g"].astype(np.float64), hip, d["bp_rp"].astype(np.float64)
    )
    n_drop = int(drop.sum())
    print(
        f"hipparcos: {len(hip.v):,} stars; {n_drop:,} Gaia sources dropped as duplicates",
        flush=True,
    )
    keep = ~drop
    ra, dec = ra[keep], dec[keep]
    g, bp_rp = d["g"][keep], d["bp_rp"][keep]
    sid, plx, eplx = d["source_id"][keep], d["parallax"][keep], d["parallax_error"][keep]

    # --- tiles: by the position the viewer will actually decode (a star within 0.08 arcsec of a
    # tile edge can quantize across it), so every tile contains exactly the stars it draws
    ra_q, dec_q = enc.encode_ra(ra), enc.encode_dec(dec)
    tile = ang2pix_nest(ORDER, enc.decode_ra(ra_q), enc.decode_dec(dec_q))
    moved = int((tile != source_id_cell(sid, ORDER)).sum())
    print(
        f"{moved:,} stars sit in a different tile than their source_id cell (position vs ID)",
        flush=True,
    )
    order = np.lexsort((sid, g.astype(np.float64), tile))  # tile, then G, then source_id
    ra, dec, g, bp_rp, sid, plx, eplx, tile, ra_q, dec_q = (
        x[order] for x in (ra, dec, g, bp_rp, sid, plx, eplx, tile, ra_q, dec_q)
    )
    starts = np.searchsorted(tile, np.arange(n_cells(ORDER) + 1))

    mag_q, col_q = enc.encode_mag(g.astype(np.float64)), enc.encode_colour(bp_rp.astype(np.float64))
    plx_q, eplx_q = (
        enc.encode_parallax(plx.astype(np.float64)),
        enc.encode_parallax_error(eplx.astype(np.float64)),
    )
    flags = np.where(np.isnan(bp_rp), enc.FLAG_NO_COLOUR, 0).astype(np.uint8)
    dmag = enc.decode_mag(mag_q)

    tiles_meta = []
    total_gz = total_raw = det_gz = det_raw = 0
    for ipix in range(n_cells(ORDER)):
        s, e = int(starts[ipix]), int(starts[ipix + 1])
        if e == s:
            continue
        t = enc.Tile(ORDER, ipix, EPOCH, ra_q[s:e], dec_q[s:e], mag_q[s:e], col_q[s:e])
        raw = enc.write_tile(t)
        blob = gz(raw)
        name = f"tiles/o{ORDER}-{ipix:04d}.bin.gz"
        (out / name).write_bytes(blob)
        det_raw_b = enc.write_details(enc.Details(sid[s:e], plx_q[s:e], eplx_q[s:e], flags[s:e]))
        det_blob = gz(det_raw_b)
        dname = f"details/o{ORDER}-{ipix:04d}.bin.gz"
        (out / dname).write_bytes(det_blob)
        m = dmag[s:e]
        tiles_meta.append(
            {
                "order": ORDER,
                "ipix": ipix,
                "count": e - s,
                "file": name,
                "bytes": len(raw),
                "gz_bytes": len(blob),
                "sha256": sha(blob),
                "details_file": dname,
                "details_bytes": len(det_raw_b),
                "details_gz_bytes": len(det_blob),
                "details_sha256": sha(det_blob),
                "g_min": round(float(m[0]), 2),
                "g_max": round(float(m[-1]), 2),
                "n_lt": [int((m < b).sum()) for b in MAG_BINS],
            }
        )
        total_gz += len(blob)
        total_raw += len(raw)
        det_gz += len(det_blob)
        det_raw += len(det_raw_b)
    n_out = int(keep.sum())

    # --- build report: quantization error and handover statistics
    ra_err = (
        np.abs(((enc.decode_ra(ra_q) - ra + 180.0) % 360.0) - 180.0)
        * np.cos(np.radians(dec))
        * 3600.0
    )
    dec_err = np.abs(enc.decode_dec(dec_q) - dec) * 3600.0
    report = {
        "rows_in": n_in,
        "dropped_as_hipparcos": n_drop,
        "stars_out": n_out,
        "hipparcos_stars": int(len(hip.v)),
        "hipparcos_matched": int((hip_of[drop] >= 0).sum()) if n_drop else 0,
        "match_separation_arcsec": {
            "median": float(np.nanmedian(sep[drop])),
            "p99": float(np.nanpercentile(sep[drop], 99)),
            "max": float(np.nanmax(sep[drop])),
        },
        "quantization_error_arcsec": {
            "ra_max": float(ra_err.max()),
            "dec_max": float(dec_err.max()),
            "mag_max": float(np.abs(dmag - g).max()),
        },
        "tile_differs_from_id_cell": moved,
        "kept_by_floor_g": {
            str(int(k)): int(v)
            for k, v in zip(*np.unique(np.floor(g).astype(int), return_counts=True), strict=True)
        },
        "dropped_by_floor_g": {
            str(int(k)): int(v)
            for k, v in zip(
                *np.unique(np.floor(d["g"][drop]).astype(int), return_counts=True), strict=True
            )
        },
        "no_colour": int((flags & enc.FLAG_NO_COLOUR).astype(bool).sum()),
        "no_parallax": int((plx_q == enc.PLX_NONE).sum()),
        "tiles": len(tiles_meta),
        "bytes": {
            "tiles_raw": total_raw,
            "tiles_gz": total_gz,
            "details_raw": det_raw,
            "details_gz": det_gz,
        },
    }
    manifest = {
        "name": "gaia-dr3-g13",
        "version": a.version,
        "format_version": enc.VERSION,
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "epoch": EPOCH,
        "source": {
            "catalogue": "Gaia DR3 gaia_source",
            "service": "ESA Gaia archive TAP, https://gea.esac.esa.int/tap-server/tap",
            "selection": "phot_g_mean_mag < 13.0",
            "gaia_epoch": GAIA_EPOCH,
            "retrieved_utc": [str(m["retrieved_utc"]) for m in (metas[0], metas[-1])],
            "archive_total": counts["total"],
            "archive_counts_retrieved_utc": counts["retrieved_utc"],
        },
        "handover": {
            "rule": "drop a Gaia source when a Hipparcos star lies within radius_arcsec at "
            "epoch 2026.0 and |G - V| <= guard(BP-RP); one best match per Hipparcos star",
            "radius_arcsec": RADIUS_ARCSEC,
            "guard": "min(max, base + colour_term * max(0, BP-RP)^2); no_colour value if no BP-RP",
            "guard_base": GUARD_BASE,
            "guard_colour_term": GUARD_COLOUR_TERM,
            "guard_max": GUARD_MAX,
            "guard_no_colour": GUARD_NO_COLOUR,
            "hipparcos_file": "public/data/stars/hipparcos.bin (HIPS v1)",
            "hipparcos_stars": int(len(hip.v)),
            "dropped": n_drop,
        },
        "tiling": {
            "scheme": "HEALPix nested",
            "order": ORDER,
            "tile_count": len(tiles_meta),
            "cells": n_cells(ORDER),
        },
        "encoding": {
            "tile": "GAIT v1: 32 B header, then columns ra u24, dec u24, mag u8, colour u8; "
            "brightest first",
            "details": "GAID v1: 32 B header, then columns source_id u64, parallax i16, "
            "parallax_error u8, flags u8",
            "ra": {"steps": enc.RA_STEPS, "unit": "deg / 360"},
            "dec": {"steps": enc.DEC_STEPS, "offset_deg": -90.0, "span_deg": 180.0},
            "mag": {"offset": enc.MAG_OFFSET, "scale": enc.MAG_SCALE, "band": "G"},
            "colour": {
                "offset": enc.COL_OFFSET,
                "scale": enc.COL_SCALE,
                "unknown": enc.COL_UNKNOWN,
                "band": "BP-RP",
            },
            "parallax": {"scale": enc.PLX_SCALE, "none": enc.PLX_NONE, "unit": "mas"},
            "parallax_error": {"scale": enc.EPLX_SCALE, "none": enc.EPLX_NONE, "unit": "mas"},
            "flags": {"1": "no BP-RP colour"},
            "mag_bins": MAG_BINS,
            "stored_as": "gzip (level 9); serve with Content-Encoding: gzip",
        },
        "totals": {
            "stars": n_out,
            "tiles": len(tiles_meta),
            "tiles_bytes": total_raw,
            "tiles_gz_bytes": total_gz,
            "details_bytes": det_raw,
            "details_gz_bytes": det_gz,
        },
        "attribution": ATTRIBUTION,
        "tiles": tiles_meta,
    }
    body = json.dumps(manifest, separators=(",", ":")).encode()
    (out / "manifest.json").write_bytes(body)
    (out / "build_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    print(f"manifest.json: {len(body):,} bytes (gzip {len(gz(body)):,})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
