"""Check a finished star-data folder, independently of the packer.

    uv run python -m scripts.star_data.verify \
        --out  ~/Desktop/Projects/star-data-2026-10/stars-v1 \
        --work ~/Desktop/Projects/star-data-2026-10/work \
        --hipparcos ~/Desktop/Projects/portfolio-site/public/data/stars/hipparcos.bin

It re-reads every file from disk and checks: checksums and sizes against the manifest; headers;
brightest-first order; every star lies in its tile; no source appears twice; per-magnitude-bin
counts (kept + dropped) against the archive's own totals; and a list of known stars, looked up in
SIMBAD at run time, against both the Hipparcos file and the tiles (a star should be in one of
them and not in both). Writes verify_report.json next to the manifest.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from scripts.star_data import encoding as enc
from scripts.star_data.crossmatch import load_hipparcos, propagate, unit_vectors
from scripts.star_data.healpix import ang2pix_nest

# (label, SIMBAD identifier). Hipparcos numbers where the star has one, so the lookup is exact.
KNOWN = [
    ("Sirius A", "HIP 32349"),
    ("Sirius B", "* alf CMa B"),
    ("Rigel", "HIP 24436"),
    ("Rigel B", "* bet Ori B"),
    ("Betelgeuse", "HIP 27989"),
    ("Vega", "HIP 91262"),
    ("Polaris", "HIP 11767"),
    ("Polaris B", "* alf UMi B"),
    ("Alnitak", "HIP 26727"),
    ("Mintaka", "HIP 25930"),
    ("Barnard's Star", "HIP 87937"),
    ("Kapteyn's Star", "HIP 24186"),
    ("Proxima Cen", "GJ 551"),
    ("Teegarden's Star", "SO J025300.5+165258"),
]
MATCH_ARCSEC = 6.0


def simbad(ident: str) -> dict[str, float] | None:
    q = (
        "SELECT b.main_id, b.ra, b.dec, b.pmra, b.pmdec FROM basic AS b JOIN ident AS i "
        f"ON i.oidref = b.oid WHERE i.id = '{ident}'"
    )
    url = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync?" + urllib.parse.urlencode(
        {"request": "doQuery", "lang": "adql", "format": "json", "query": q}
    )
    d = json.loads(urllib.request.urlopen(url, timeout=60).read())
    if not d.get("data"):
        return None
    main_id, ra, dec, pmra, pmdec = d["data"][0]
    return {"main_id": main_id, "ra": ra, "dec": dec, "pmra": pmra or 0.0, "pmdec": pmdec or 0.0}


def nearest(ra: float, dec: float, cat_ra: np.ndarray, cat_dec: np.ndarray) -> tuple[int, float]:
    v = unit_vectors(cat_ra, cat_dec)
    t = unit_vectors(np.array([ra]), np.array([dec]))[0]
    d = np.linalg.norm(v - t, axis=1)
    i = int(np.argmin(d))
    return i, float(np.degrees(2 * np.arcsin(min(1.0, d[i] / 2))) * 3600)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--out", required=True)
    p.add_argument("--work", required=True)
    p.add_argument("--hipparcos", required=True)
    a = p.parse_args(argv)
    out, work = Path(a.out).expanduser(), Path(a.work).expanduser()
    m = json.loads((out / "manifest.json").read_text())
    checks: dict[str, object] = {}
    problems: list[str] = []

    # --- files, checksums, headers, order, membership, duplicates
    all_ra: list[np.ndarray] = []
    all_dec: list[np.ndarray] = []
    all_mag: list[np.ndarray] = []
    seen: set[int] = set()
    dup = 0
    n_stars = 0
    sizes_gz = []
    for t in m["tiles"]:
        blob = (out / t["file"]).read_bytes()
        if hashlib.sha256(blob).hexdigest() != t["sha256"] or len(blob) != t["gz_bytes"]:
            problems.append(f"{t['file']}: checksum or size mismatch")
        raw = gzip.decompress(blob)
        tile = enc.read_tile(raw)
        if (tile.order, tile.ipix, tile.count, len(raw)) != (
            t["order"],
            t["ipix"],
            t["count"],
            t["bytes"],
        ):
            problems.append(f"{t['file']}: header disagrees with the manifest")
        dblob = (out / t["details_file"]).read_bytes()
        if hashlib.sha256(dblob).hexdigest() != t["details_sha256"]:
            problems.append(f"{t['details_file']}: checksum mismatch")
        det = enc.read_details(gzip.decompress(dblob))
        if det.count != tile.count:
            problems.append(f"{t['file']}: details count differs")
        ra, dec, mag = enc.decode_ra(tile.ra), enc.decode_dec(tile.dec), enc.decode_mag(tile.mag)
        if tile.count and (np.diff(mag) < -1e-9).any():
            problems.append(f"{t['file']}: not brightest first")
        if tile.count and not (ang2pix_nest(t["order"], ra, dec) == t["ipix"]).all():
            problems.append(f"{t['file']}: a star lies outside its tile")
        ids = det.source_id.tolist()
        s = set(ids)
        dup += (len(ids) - len(s)) + len(s & seen)
        seen |= s
        n_stars += tile.count
        sizes_gz.append(len(blob))
        all_ra.append(ra)
        all_dec.append(dec)
        all_mag.append(mag)
        for b, n in zip(m["encoding"]["mag_bins"], t["n_lt"], strict=True):
            if n != int((mag < b).sum()):
                problems.append(f"{t['file']}: n_lt[{b}] wrong")
    checks["stars"] = n_stars
    checks["manifest_total_matches"] = n_stars == m["totals"]["stars"]
    checks["duplicate_sources"] = dup
    if dup:
        problems.append(f"{dup} duplicated source ids")
    if n_stars != m["totals"]["stars"]:
        problems.append("star total differs from the manifest")

    # --- counts against the archive: kept + dropped per whole-magnitude bin
    arch = json.loads((work / "archive_counts.json").read_text())
    rep = json.loads((out / "build_report.json").read_text())
    per_bin = {}
    for gb, n in arch["by_floor_g"].items():
        kept = rep["kept_by_floor_g"].get(gb, 0)
        dropped = rep["dropped_by_floor_g"].get(gb, 0)
        per_bin[gb] = {
            "archive": n,
            "kept": kept,
            "dropped_hipparcos": dropped,
            "ok": kept + dropped == n,
        }
        if kept + dropped != n:
            problems.append(f"G bin {gb}: kept {kept} + dropped {dropped} != archive {n}")
    checks["per_magnitude_bin"] = per_bin
    checks["archive_total"] = arch["total"]
    checks["kept_plus_dropped_equals_archive"] = n_stars + m["handover"]["dropped"] == arch["total"]
    if n_stars + m["handover"]["dropped"] != arch["total"]:
        problems.append("kept + dropped != archive total")

    # --- known stars
    hip = load_hipparcos(Path(a.hipparcos).expanduser())
    g_ra, g_dec, g_mag = (np.concatenate(x) for x in (all_ra, all_dec, all_mag))
    known = []
    for label, ident in KNOWN:
        row: dict[str, object] = {"star": label, "ident": ident}
        s = simbad(ident)
        if s is None:
            row["note"] = "not found in SIMBAD"
            known.append(row)
            continue
        ra26, dec26 = propagate(
            np.array([s["ra"]]),
            np.array([s["dec"]]),
            np.array([s["pmra"]]),
            np.array([s["pmdec"]]),
            26.0,
        )
        hi, hsep = nearest(ra26[0], dec26[0], hip.ra, hip.dec)
        gi, gsep = nearest(ra26[0], dec26[0], g_ra, g_dec)
        in_hip = hsep <= MATCH_ARCSEC
        in_gaia = gsep <= MATCH_ARCSEC
        row.update(
            {
                "simbad": s["main_id"],
                "in_hipparcos": bool(in_hip),
                "hip_sep_arcsec": round(hsep, 2),
                "hip_V": round(float(hip.v[hi]), 2) if in_hip else None,
                "in_gaia_tiles": bool(in_gaia),
                "gaia_sep_arcsec": round(gsep, 2),
                "gaia_G": round(float(g_mag[gi]), 2) if in_gaia else None,
            }
        )
        known.append(row)
    checks["known_stars"] = known
    bad = [
        r["star"]
        for r in known
        if r.get("in_hipparcos")
        and r.get("in_gaia_tiles")
        and abs(float(r["hip_V"]) - float(r["gaia_G"])) <= 2.0
        and r["hip_sep_arcsec"] <= 2.0
        and r["gaia_sep_arcsec"] <= 2.0
    ]  # type: ignore[arg-type]
    if bad:
        problems.append(f"drawn twice (in both files): {bad}")

    # --- file sizes
    sz = np.array(sizes_gz)
    checks["tile_files"] = {
        "count": len(sizes_gz),
        "gz_bytes": {
            "min": int(sz.min()),
            "median": int(np.median(sz)),
            "p90": int(np.percentile(sz, 90)),
            "max": int(sz.max()),
            "total": int(sz.sum()),
        },
    }
    report = {"ok": not problems, "problems": problems, "checks": checks}
    (out / "verify_report.json").write_text(json.dumps(report, indent=1))
    print(
        json.dumps(
            {"ok": report["ok"], "problems": problems, "tile_files": checks["tile_files"]}, indent=1
        )
    )
    for r in known:
        print(" ", r)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
