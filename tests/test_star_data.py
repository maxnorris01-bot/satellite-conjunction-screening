"""Tiling maths, encodings, the Hipparcos handover and the packer (scripts/star_data).

The HEALPix reference values were computed with astropy-healpix (`HEALPix(nside, 'nested')
.lonlat_to_healpix`). The Gaia rows are real sources from the archive.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.star_data import encoding as enc  # noqa: E402
from scripts.star_data import pack  # noqa: E402
from scripts.star_data.crossmatch import (  # noqa: E402
    hipparcos_duplicates,
    load_hipparcos,
    propagate,
)
from scripts.star_data.healpix import (  # noqa: E402
    ang2pix_nest,
    cell_source_id_range,
    n_cells,
    source_id_cell,
)

POINTS = {
    "hdfn": (189.2058, 62.2161),
    "orion": (83.8221, -5.3911),
    "galcentre": (266.4168, -29.0078),
    "south": (10.0, -80.0),
    "south2": (300.0, -45.0),
}
# order -> expected nested index for hdfn, orion, galcentre, south, south2 (astropy-healpix)
REFERENCE = {
    3: [175, 334, 450, 514, 740],
    9: [720131, 1372138, 1845129, 2107474, 3034111],
    12: [46088403, 87816852, 118088263, 134878339, 194183167],
    13: [184353615, 351267410, 472353052, 539513356, 776732671],
    14: [737414460, 1405069640, 1889412210, 2158053426, 3106930685],
    15: [2949657840, 5620278561, 7557648841, 8632213705, 12427722742],
}
# Real Gaia DR3 sources: (source_id, ra, dec) at epoch 2016.0, northern and southern.
GAIA_ROWS = [
    (27022765995333376, 44.95510906128002, 9.649766316901077),
    (32996588763444736, 40.546662279120476, 14.601930856033647),
    (36025257966133120, 44.938727088209774, 19.314251514768138),
    (180145015887018112, 78.78687920742297, 30.108974962897502),
    (183904628398545280, 79.00729090459168, 35.825988029450535),
    (189150978195555328, 78.71485928950274, 41.761086357609706),
    (4053240970307667200, 264.34507648797927, -35.58816706797612),
    (4058442077024468096, 263.04476142284085, -30.146221043152025),
    (4062245390769436288, 264.4514360593435, -24.713647711857014),
    (4062247138768194560, 269.97248968051554, -29.97092083678047),
    (4064998700982944640, 272.5001411904042, -25.361893037856554),
    (4071252860557856512, 270.05061938031105, -19.524645031483246),
]


# ---------------------------------------------------------------- tiling maths
@pytest.mark.parametrize("order", sorted(REFERENCE))
def test_ang2pix_matches_astropy_reference(order: int) -> None:
    ra = np.array([p[0] for p in POINTS.values()])
    dec = np.array([p[1] for p in POINTS.values()])
    assert ang2pix_nest(order, ra, dec).tolist() == REFERENCE[order]


def test_source_id_cell_usually_but_not_always_matches_the_position_cell() -> None:
    """Gaia IDs are assigned from an initial position, so the ID cell can differ from the final
    position's cell. In 392,349 real stars: 0.44% differ at level 12, 1 star at level 3. The first
    row below is a real level-12 example (cell 786464 by position, 786466 by ID)."""
    sid = np.array([r[0] for r in GAIA_ROWS], dtype=np.int64)
    ra = np.array([r[1] for r in GAIA_ROWS])
    dec = np.array([r[2] for r in GAIA_ROWS])
    by_pos = ang2pix_nest(12, ra, dec)
    by_id = source_id_cell(sid, 12)
    assert by_pos[0] == 786464 and by_id[0] == 786466
    assert by_pos[1:].tolist() == by_id[1:].tolist()
    # at the tile level the ID cell and the position cell agree for all twelve
    assert ang2pix_nest(3, ra, dec).tolist() == source_id_cell(sid, 3).tolist()


def test_cell_source_id_range_is_exactly_the_cell() -> None:
    lo, hi = cell_source_id_range(450, 3)
    assert source_id_cell(lo, 3) == 450 and source_id_cell(hi - 1, 3) == 450
    assert source_id_cell(hi, 3) == 451 and source_id_cell(lo - 1, 3) == 449
    # The real Galactic-centre rows above sit in cell 450 by position and by ID.
    for sid, ra, dec in GAIA_ROWS[6:]:
        assert lo <= sid < hi or ang2pix_nest(3, ra, dec)[0] != 450


def test_poles_wraparound_and_range() -> None:
    rng = np.random.default_rng(1)
    for order in (0, 1, 3, 7, 12):
        ra = rng.uniform(0, 360, 5000)
        dec = np.degrees(np.arcsin(rng.uniform(-1, 1, 5000)))  # uniform on the sphere
        ipix = ang2pix_nest(order, ra, dec)
        assert ipix.min() >= 0 and ipix.max() < n_cells(order)
        # equal-area cells: no cell wildly over- or under-filled at order 1 (48 cells, ~104 each)
        if order == 1:
            counts = np.bincount(ipix, minlength=48)
            assert counts.min() > 50 and counts.max() < 170
    assert ang2pix_nest(3, 0.0, 10.0)[0] == ang2pix_nest(3, 360.0, 10.0)[0]
    assert 0 <= ang2pix_nest(3, 12.0, 90.0)[0] < 768 and 0 <= ang2pix_nest(3, 12.0, -90.0)[0] < 768


def test_a_star_is_tiled_by_position_even_when_its_id_cell_differs() -> None:
    sid, ra, dec = GAIA_ROWS[0]
    assert ang2pix_nest(12, ra, dec)[0] != source_id_cell(sid, 12)
    # both cells are inside the same order-3 tile here, so the tile is unambiguous
    assert ang2pix_nest(3, ra, dec)[0] == source_id_cell(sid, 3)


# ---------------------------------------------------------------- encodings
def test_position_quantization_error_is_under_a_pixel_at_narrow_fields() -> None:
    rng = np.random.default_rng(2)
    ra = rng.uniform(0, 360, 20000)
    dec = rng.uniform(-90, 90, 20000)
    dra = np.abs(((enc.decode_ra(enc.encode_ra(ra)) - ra + 180) % 360) - 180) * 3600
    ddec = np.abs(enc.decode_dec(enc.encode_dec(dec)) - dec) * 3600
    assert dra.max() <= 360 * 3600 / 2**24 / 2 + 1e-9  # half a step: 0.077 arcsec / 2
    assert ddec.max() <= 180 * 3600 / (2**24 - 1) / 2 + 1e-9
    assert enc.encode_ra(np.array([359.99999999]))[0] == 0  # wraps, never 2**24


def test_magnitude_and_colour_ranges_and_codes() -> None:
    g = np.array([1.5, 8.04, 12.99, 20.9])
    assert np.abs(enc.decode_mag(enc.encode_mag(g)) - g).max() <= 0.5 / enc.MAG_SCALE + 1e-9
    assert enc.encode_mag(np.array([-5.0, 99.0])).tolist() == [0, 255]
    bp = np.array([-0.5, 0.0, 0.82, 4.9, 8.46, np.nan])
    q = enc.encode_colour(bp)
    assert q[-1] == enc.COL_UNKNOWN and (q[:-1] >= 1).all()
    back = enc.decode_colour(q)
    assert np.isnan(back[-1]) and np.abs(back[:-1] - bp[:-1]).max() <= 0.5 / enc.COL_SCALE + 1e-9
    assert enc.COL_OFFSET + 255 / enc.COL_SCALE > 8.46  # the reddest star seen in testing fits


def test_parallax_encoding_covers_proxima_and_flags_missing() -> None:
    plx = np.array([768.07, 0.02, -1.5, np.nan])
    q = enc.encode_parallax(plx)
    assert q[3] == enc.PLX_NONE and abs(q[0] / enc.PLX_SCALE - 768.07) < 0.03
    e = enc.encode_parallax_error(np.array([0.02, 3.0, np.nan]))
    assert e.tolist() == [4, 254, 255]


def test_tile_round_trip_and_length_checks() -> None:
    t = enc.Tile(
        3,
        450,
        2026.0,
        np.array([0, 5, 2**24 - 1], dtype=np.uint32),
        np.array([1, 2**23, 2**24 - 1], dtype=np.uint32),
        np.array([10, 20, 255], dtype=np.uint8),
        np.array([0, 33, 255], dtype=np.uint8),
    )
    raw = enc.write_tile(t)
    assert len(raw) == 32 + 3 * 8 and raw[:4] == b"GAIT"
    back = enc.read_tile(raw)
    assert (back.order, back.ipix, back.count, back.epoch) == (3, 450, 3, 2026.0)
    for col in ("ra", "dec", "mag", "colour"):
        assert getattr(back, col).tolist() == getattr(t, col).tolist()
    with pytest.raises(ValueError):
        enc.read_tile(raw[:-1])
    with pytest.raises(ValueError):
        enc.read_tile(b"HIPS" + raw[4:])


def test_details_round_trip_with_large_source_ids() -> None:
    sid = np.array([6917528997577384320, 4053240970307667200, 27022765995333376], dtype=np.int64)
    d = enc.Details(
        sid,
        np.array([30720, -32768, 5], dtype=np.int16),
        np.array([4, 255, 0], dtype=np.uint8),
        np.array([0, 1, 0], dtype=np.uint8),
    )
    raw = enc.write_details(d)
    assert len(raw) == 32 + 3 * 12 and raw[:4] == b"GAID"
    back = enc.read_details(raw)
    assert back.source_id.tolist() == sid.tolist()
    assert back.parallax.tolist() == [30720, -32768, 5] and back.flags.tolist() == [0, 1, 0]


# ---------------------------------------------------------------- the Hipparcos handover
def _hip_file(path: Path, stars: list[tuple[float, float, float]]) -> Path:
    """Write a HIPS v1 file for (ra, dec, V) stars, brightest first, epoch 2026.0."""
    stars = sorted(stars, key=lambda s: s[2])
    n = len(stars)
    buf = bytearray(struct.pack("<4sHHIf", b"HIPS", 1, 0, n, 2026.0))
    buf += b"\x00" * (32 - len(buf))
    ra = np.array([s[0] for s in stars])
    dec = np.array([s[1] for s in stars])
    buf += enc._u24(enc.encode_ra(ra)) + enc._u24(enc.encode_dec(dec))
    buf += bytes(int(round((s[2] + 2) * 16)) for s in stars) + bytes(n)
    path.write_bytes(bytes(buf))
    return path


def test_load_hipparcos_round_trips(tmp_path: Path) -> None:
    h = load_hipparcos(_hip_file(tmp_path / "h.bin", [(10.0, 20.0, 5.0), (200.0, -30.0, 1.0)]))
    assert h.epoch == 2026.0 and h.v.tolist() == [1.0, 5.0]
    assert abs(h.ra[0] - 200.0) < 1e-4 and abs(h.dec[1] - 20.0) < 1e-4


def test_handover_drops_the_duplicate_and_keeps_companions(tmp_path: Path) -> None:
    # Hipparcos: one bright star "A" (V 0.0) and one faint-ish star (V 9.0)
    hip = load_hipparcos(_hip_file(tmp_path / "h.bin", [(100.0, 10.0, 0.0), (200.0, -20.0, 9.0)]))
    arcsec = 1 / 3600
    g_ra = np.array([100.0, 100.0 + 11 * arcsec, 200.0 + 0.5 * arcsec, 200.0 + 1.5 * arcsec, 50.0])
    g_dec = np.array([10.0, 10.0, -20.0, -20.0, 0.0])
    g_mag = np.array([0.1, 8.5, 9.1, 10.2, 12.0])
    drop, hip_of, sep = hipparcos_duplicates(g_ra, g_dec, g_mag, hip)
    # [0] is A itself: dropped. [1] is a companion 11" away (Sirius B-like): kept.
    # [2] is the V=9 star: dropped. [3] is a 10.2 star 1.5" from it: kept (the best match was [2]).
    assert drop.tolist() == [True, False, True, False, False]
    assert hip_of[0] == 0 and hip_of[2] == 1 and (hip_of[[1, 3, 4]] == -1).all()
    assert sep[0] < 0.5 and sep[2] < 1.0


def test_handover_magnitude_guard_keeps_a_faint_source_at_a_bright_position(tmp_path: Path) -> None:
    # A G=15 source within 1" of a V=2 star is a different object (a faint neighbour).
    hip = load_hipparcos(_hip_file(tmp_path / "h.bin", [(85.0, -2.0, 2.0)]))
    drop, _, _ = hipparcos_duplicates(
        np.array([85.0 + 0.3 / 3600]), np.array([-2.0]), np.array([15.0]), hip
    )
    assert not drop[0]


def test_proper_motion_brings_barnards_star_onto_its_hipparcos_position() -> None:
    # Barnard's Star: pm (-798.6, +10328.1) mas/yr. Gaia (2016.0) to 2026.0 is a 103" shift in Dec.
    ra, dec = propagate(
        np.array([269.4486]), np.array([4.7389]), np.array([-798.6]), np.array([10328.1]), 10.0
    )
    assert abs((dec[0] - 4.7389) * 3600 - 103.281) < 0.01
    assert abs((ra[0] - 269.4486) * 3600 * np.cos(np.radians(4.74)) - (-7.986)) < 0.01
    # no proper motion (NaN) leaves the position unchanged
    ra2, dec2 = propagate(
        np.array([10.0]), np.array([5.0]), np.array([np.nan]), np.array([np.nan]), 10.0
    )
    assert (ra2[0], dec2[0]) == (10.0, 5.0)


# ---------------------------------------------------------------- the packer, end to end
def _synthetic_work(root: Path) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(7)
    (root / "cells").mkdir(parents=True)
    cells: dict[str, list[np.ndarray]] = {}
    all_rows: list[tuple[float, float, float]] = []
    counts: dict[str, int] = {}
    by_bin: dict[int, int] = {}
    next_id = 1000
    for c in range(n_cells(3)):
        n = 3 + (c % 4)
        z = rng.uniform(-1, 1, n)
        ra = rng.uniform(0, 360, n)
        dec = np.degrees(np.arcsin(z))
        g = rng.uniform(5, 13, n).astype(np.float32)
        sid = np.arange(next_id, next_id + n, dtype=np.int64)
        next_id += n
        arrays = {
            "source_id": sid,
            "ra": ra,
            "dec": dec,
            "g": g,
            "bp_rp": np.where(rng.uniform(size=n) < 0.2, np.nan, rng.uniform(0, 3, n)).astype(
                np.float32
            ),
            "parallax": np.where(rng.uniform(size=n) < 0.1, np.nan, rng.uniform(0, 50, n)).astype(
                np.float32
            ),
            "parallax_error": rng.uniform(0.01, 0.3, n).astype(np.float32),
            "pmra": rng.uniform(-50, 50, n).astype(np.float32),
            "pmdec": rng.uniform(-50, 50, n).astype(np.float32),
        }
        np.savez_compressed(root / "cells" / f"c3_{c:04d}.npz", **arrays)
        (root / "cells" / f"c3_{c:04d}.json").write_text(
            json.dumps({"cell": c, "rows": n, "retrieved_utc": "2026-10-14T00:00:00+00:00"})
        )
        counts[str(c)] = n
        for gv in g:
            by_bin[int(np.floor(gv))] = by_bin.get(int(np.floor(gv)), 0) + 1
        for k, v in arrays.items():
            cells.setdefault(k, []).append(v)
        all_rows += [(float(a), float(b), float(m)) for a, b, m in zip(ra, dec, g, strict=True)]
    (root / "archive_counts.json").write_text(
        json.dumps(
            {
                "total": sum(counts.values()),
                "cells": counts,
                "by_floor_g": {str(k): v for k, v in sorted(by_bin.items())},
                "retrieved_utc": "2026-10-14T00:00:00+00:00",
            }
        )
    )
    return {k: np.concatenate(v) for k, v in cells.items()}


def test_pack_end_to_end_on_a_synthetic_work_folder(tmp_path: Path) -> None:
    work = tmp_path / "work"
    d = _synthetic_work(work)
    n = len(d["source_id"])
    # Hipparcos stars placed exactly on three Gaia stars (after propagating them to 2026.0).
    ra26, dec26 = propagate(d["ra"], d["dec"], d["pmra"], d["pmdec"], 10.0)
    pick = [0, 100, 500]
    hip_path = _hip_file(
        tmp_path / "hip.bin",
        [(float(ra26[i]), float(dec26[i]), float(d["g"][i]) + 0.2) for i in pick],
    )
    out = tmp_path / "out"
    assert pack.main(["--work", str(work), "--hipparcos", str(hip_path), "--out", str(out)]) == 0

    m = json.loads((out / "manifest.json").read_text())
    assert m["handover"]["dropped"] == 3 and m["totals"]["stars"] == n - 3
    assert sum(t["count"] for t in m["tiles"]) == n - 3
    assert m["epoch"] == 2026.0 and m["tiling"]["order"] == 3
    seen: set[int] = set()
    for t in m["tiles"]:
        blob = (out / t["file"]).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == t["sha256"] and len(blob) == t["gz_bytes"]
        tile = enc.read_tile(gzip.decompress(blob))
        assert tile.count == t["count"] and len(gzip.decompress(blob)) == t["bytes"]
        mags = enc.decode_mag(tile.mag)
        assert (np.diff(mags) >= 0).all()  # brightest first
        # every star lies inside its tile
        ra_s = enc.decode_ra(tile.ra)
        dec_s = enc.decode_dec(tile.dec)
        assert (ang2pix_nest(3, ra_s, dec_s) == tile.ipix).all()
        det = enc.read_details(gzip.decompress((out / t["details_file"]).read_bytes()))
        assert det.count == tile.count
        assert not (set(det.source_id.tolist()) & seen)  # no source appears in two tiles
        seen |= set(det.source_id.tolist())
        assert t["n_lt"] == [int((mags < b).sum()) for b in pack.MAG_BINS]
    assert len(seen) == n - 3
    assert not (seen & {int(d["source_id"][i]) for i in pick})  # the Hipparcos duplicates are gone
    # deterministic files: pack again, same bytes
    out2 = tmp_path / "out2"
    pack.main(["--work", str(work), "--hipparcos", str(hip_path), "--out", str(out2)])
    first = m["tiles"][0]["file"]
    assert (out / first).read_bytes() == (out2 / first).read_bytes()


def test_pack_refuses_a_work_folder_that_disagrees_with_the_archive(tmp_path: Path) -> None:
    work = tmp_path / "work"
    _synthetic_work(work)
    counts = json.loads((work / "archive_counts.json").read_text())
    counts["cells"]["10"] += 1
    (work / "archive_counts.json").write_text(json.dumps(counts))
    hip = _hip_file(tmp_path / "hip.bin", [(1.0, 1.0, 5.0)])
    with pytest.raises(SystemExit):
        pack.main(["--work", str(work), "--hipparcos", str(hip), "--out", str(tmp_path / "o")])


# ---------------------------------------------------------------- the upload plan
def test_upload_plan_sets_headers_and_sends_the_manifest_last(tmp_path: Path) -> None:
    from scripts.star_data import upload

    src = tmp_path / "stars-v1"
    for rel in (
        "tiles/o3-0001.bin.gz",
        "details/o3-0001.bin.gz",
        "manifest.json",
        "glow.json",
        "glow-o7.jpg",
    ):
        f = src / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
    (src / "build_report.json").write_bytes(b"{}")  # never uploaded
    (src / "verify_report.json").write_bytes(b"{}")
    items = upload.plan(src, "stars/v1/")
    keys = [k for _, k, _ in items]
    assert keys[-1] == "stars/v1/manifest.json"
    assert sorted(keys) == sorted(
        [
            "stars/v1/tiles/o3-0001.bin.gz",
            "stars/v1/details/o3-0001.bin.gz",
            "stars/v1/glow.json",
            "stars/v1/glow-o7.jpg",
            "stars/v1/manifest.json",
        ]
    )
    by_key = {k: h for _, k, h in items}
    tile = by_key["stars/v1/tiles/o3-0001.bin.gz"]
    assert tile["ContentEncoding"] == "gzip" and "immutable" in tile["CacheControl"]
    assert by_key["stars/v1/manifest.json"]["ContentType"] == "application/json"
    assert "ContentEncoding" not in by_key["stars/v1/glow-o7.jpg"]


# ---------------------------------------------------------------- extraction guards
def _csv_rows(ids: list[int]) -> bytes:
    head = "source_id,ra,dec,phot_g_mean_mag,bp_rp,parallax,parallax_error,pmra,pmdec\n"
    return (head + "".join(f"{i},10.0,20.0,12.5,0.8,1.0,0.1,0.0,0.0\n" for i in ids)).encode()


def test_extract_refuses_a_cell_that_disagrees_with_the_archive_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The archive's sync endpoint silently cut four dense cells at 50,000 rows; the CSV had no
    marker. A cell must match the archive's own count or it is not kept."""
    from scripts.star_data import extract

    (tmp_path / "cells").mkdir()
    (tmp_path / "raw").mkdir()
    lo, _ = cell_source_id_range(5, 3)
    ids = [lo + k for k in range(10)]
    monkeypatch.setattr(extract, "tap_with_retry", lambda q, label: (_csv_rows(ids), 1))
    (tmp_path / "archive_counts.json").write_text(json.dumps({"cells": {"5": 12}}))
    with pytest.raises(ValueError, match="archive counts 12"):
        extract.fetch_cell(tmp_path, 5, 13.0, 0.0)
    assert not (tmp_path / "cells" / "c3_0005.npz").exists()
    (tmp_path / "archive_counts.json").write_text(json.dumps({"cells": {"5": 10}}))
    meta = extract.fetch_cell(tmp_path, 5, 13.0, 0.0)
    assert meta["rows"] == 10 and (tmp_path / "cells" / "c3_0005.npz").exists()
    assert extract.fetch_cell(tmp_path, 5, 13.0, 0.0)["skipped"] is True


def test_extract_requests_a_record_limit_above_the_sync_default() -> None:
    from scripts.star_data import extract

    assert extract.MAXREC > 50_000


def test_handover_guard_is_colour_aware(tmp_path: Path) -> None:
    from scripts.star_data.crossmatch import mag_guard

    # Proxima-like: V=11.0, G=9.0, BP-RP=3.8 is the same star; a blue star 2 mag off is not.
    hip = load_hipparcos(_hip_file(tmp_path / "h.bin", [(10.0, 10.0, 11.0), (20.0, 10.0, 6.0)]))
    drop, _, _ = hipparcos_duplicates(
        np.array([10.0, 20.0]),
        np.array([10.0, 10.0]),
        np.array([9.0, 8.0]),
        hip,
        np.array([3.8, 0.3]),
    )
    assert drop.tolist() == [True, False]
    assert mag_guard(np.array([0.0, 4.0, 9.0, np.nan])).tolist() == [1.0, 6.0, 6.0, 3.0]


def test_tile_assignment_uses_the_decoded_position() -> None:
    # A star 0.02 arcsec inside a tile edge can quantize across it; the tile must follow the
    # decoded position so the viewer never sees a star outside its tile.
    from scripts.star_data import encoding as enc

    ra = np.linspace(44.9999, 45.0001, 4001)
    dec = np.full_like(ra, 9.0)
    q = enc.decode_ra(enc.encode_ra(ra))
    cells = ang2pix_nest(3, q, enc.decode_dec(enc.encode_dec(dec)))
    assert set(np.unique(ang2pix_nest(3, q, dec))) >= set(np.unique(cells))
