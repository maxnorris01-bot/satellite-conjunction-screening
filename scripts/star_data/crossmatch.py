"""The Hipparcos handover: which Gaia stars the Hipparcos file already covers.

The viewer draws `hipparcos.bin` (118,217 stars, epoch 2026.0) and these Gaia tiles together, so a
star present in both would be drawn twice, and Gaia itself is missing most of the brightest stars
(Sirius A, Vega, Betelgeuse, Alnitak ... are absent or only their companions appear). The rule:

    A Gaia source is DROPPED from the tiles when a Hipparcos star lies within RADIUS_ARCSEC of it
    (both at epoch 2026.0) and their magnitudes agree: |G - V| <= guard(BP-RP). For each Hipparcos
    star only the single best match (smallest |G - V|, then nearest) is dropped.

The guard depends on colour because V - G does: measured on 116,664 near-certain counterparts,
its median runs from 0.03 (blue stars) to 2.24 (BP-RP above 4) and its 99th percentile from 0.11
to 4.1. A fixed 2.0 left Proxima Centauri (V = 11.0, G = 9.0, BP-RP = 3.8) drawn twice. The guard is
`1.0 + 0.5 * max(0, BP-RP)**2`, at most 6.0 (3.0 when a source has no colour); that covers the
largest V - G seen in the near-certain pairs (5.23) and stays far below the 6 to 10 magnitude gap of
a companion beside a bright star (Sirius B, G = 8.5, is 9 arcsec from Sirius A, V = -1.4; Rigel B
and Polaris B are similar), so those stay in the tiles. Taking only the best match keeps the second
component of a close pair that Hipparcos blended into one star.

No magnitude cut is applied: every Hipparcos star stays in the Hipparcos layer, and every Gaia
source not matched to one is in the tiles, so nothing is drawn twice and nothing is lost.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

RADIUS_ARCSEC = 3.0  # 163 of 117,763 real counterparts were 2-3 arcsec apart (Hipparcos binaries)
GUARD_BASE = 1.0
GUARD_COLOUR_TERM = 0.5  # mag per (BP-RP)**2
GUARD_MAX = 6.0
GUARD_NO_COLOUR = 3.0


def mag_guard(bp_rp: NDArray[np.float64]) -> NDArray[np.float64]:
    """The largest |G - V| still counted as the same star, from the Gaia source's BP-RP."""
    red = np.maximum(0.0, np.nan_to_num(bp_rp, nan=0.0))
    g = np.minimum(GUARD_MAX, GUARD_BASE + GUARD_COLOUR_TERM * red**2)
    return np.where(np.isnan(bp_rp), GUARD_NO_COLOUR, g)


@dataclass(frozen=True)
class Hipparcos:
    ra: NDArray[np.float64]
    dec: NDArray[np.float64]
    v: NDArray[np.float64]
    epoch: float


def load_hipparcos(path: Path) -> Hipparcos:
    """Read the site's hipparcos.bin ("HIPS" version 1: ra u24, dec u24, mag u8, bv u8 columns)."""
    buf = path.read_bytes()
    magic, version = struct.unpack_from("<4sH", buf, 0)
    if magic != b"HIPS" or version != 1:
        raise ValueError("not a version 1 hipparcos.bin")
    (n,) = struct.unpack_from("<I", buf, 8)
    (epoch,) = struct.unpack_from("<f", buf, 12)
    at = 32

    def u24(offset: int) -> NDArray[np.float64]:
        a = (
            np.frombuffer(buf, dtype=np.uint8, count=3 * n, offset=offset)
            .reshape(n, 3)
            .astype(np.uint32)
        )
        return (a[:, 0] | (a[:, 1] << 8) | (a[:, 2] << 16)).astype(np.float64)

    ra = u24(at) / 2**24 * 360.0
    dec = u24(at + 3 * n) / (2**24 - 1) * 180.0 - 90.0
    mag = np.frombuffer(buf, dtype=np.uint8, count=n, offset=at + 6 * n).astype(np.float64)
    return Hipparcos(ra, dec, mag / 16.0 - 2.0, float(epoch))


def unit_vectors(ra_deg: NDArray[np.float64], dec_deg: NDArray[np.float64]) -> NDArray[np.float64]:
    ra = np.radians(ra_deg)
    dec = np.radians(dec_deg)
    c = np.cos(dec)
    return np.stack([c * np.cos(ra), c * np.sin(ra), np.sin(dec)], axis=1)


def propagate(
    ra_deg: NDArray[np.float64],
    dec_deg: NDArray[np.float64],
    pmra_mas_yr: NDArray[np.float32 | np.float64],
    pmdec_mas_yr: NDArray[np.float32 | np.float64],
    years: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """First-order proper-motion propagation (pmra includes cos(dec), as in Gaia and Hipparcos).

    Missing proper motions (NaN) leave the position unchanged. The second-order error is a few
    milliarcseconds even for Barnard's Star over ten years.
    """
    pmra = np.nan_to_num(pmra_mas_yr.astype(np.float64), nan=0.0)
    pmdec = np.nan_to_num(pmdec_mas_yr.astype(np.float64), nan=0.0)
    dec = np.clip(dec_deg + pmdec * years / 3.6e6, -90.0, 90.0)
    cosd = np.maximum(1e-6, np.cos(np.radians(dec)))
    ra = np.mod(ra_deg + pmra * years / 3.6e6 / cosd, 360.0)
    return ra, dec


def hipparcos_duplicates(
    g_ra: NDArray[np.float64],
    g_dec: NDArray[np.float64],
    g_mag: NDArray[np.float64],
    hip: Hipparcos,
    g_bp_rp: NDArray[np.float64] | None = None,
    radius_arcsec: float = RADIUS_ARCSEC,
) -> tuple[NDArray[np.bool_], NDArray[np.int64], NDArray[np.float64]]:
    """Which Gaia stars are the Hipparcos stars. Returns (drop mask, hip index per Gaia star or -1,
    separation in arcsec per Gaia star or NaN)."""
    n = len(g_ra)
    guard = mag_guard(g_bp_rp if g_bp_rp is not None else np.full(n, np.nan))
    drop = np.zeros(n, dtype=bool)
    hip_of = np.full(n, -1, dtype=np.int64)
    sep = np.full(n, np.nan)
    tree = cKDTree(unit_vectors(g_ra, g_dec))
    chord = 2.0 * np.sin(np.radians(radius_arcsec / 3600.0) / 2.0)
    hvec = unit_vectors(hip.ra, hip.dec)
    candidates = tree.query_ball_point(hvec, r=chord)
    for h, cand in enumerate(candidates):
        if not cand:
            continue
        idx = np.asarray(cand)
        dmag = np.abs(g_mag[idx] - hip.v[h])
        ok = dmag <= guard[idx]
        if not ok.any():
            continue
        idx, dmag = idx[ok], dmag[ok]
        d = np.linalg.norm(unit_vectors(g_ra[idx], g_dec[idx]) - hvec[h], axis=1)
        best = int(np.lexsort((d, dmag))[0])
        j = int(idx[best])
        if drop[j]:
            continue  # already claimed by another Hipparcos star
        drop[j] = True
        hip_of[j] = h
        sep[j] = float(np.degrees(2.0 * np.arcsin(min(1.0, d[best] / 2.0))) * 3600.0)
    return drop, hip_of, sep
