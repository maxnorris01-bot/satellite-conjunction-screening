"""Nested HEALPix pixel index from sky position, in numpy (no HEALPix library needed).

The standard algorithm (Gorski et al. 2005; the same arithmetic as `healpix_base`'s
`ang2pix_nest`). It's checked against astropy-healpix reference values and against real Gaia
sources in tests/test_star_data.py.

Gaia's `source_id // 2**35` is the level-12 nested HEALPix index of the position the source had
when its ID was assigned. That is NOT always the cell of the final DR3 position: measured on 392,349
stars brighter than G = 13, the two differ for 0.44% of sources at level 12, 0.006% at level 6 and
1 star in 392,349 at level 3. So a `source_id` range is a complete, non-overlapping way to ask the
archive for stars (every star is in exactly one range), but tiles must be assigned from the final
position with `ang2pix_nest`, which pack.py does.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

GAIA_HEALPIX_ORDER = 12
GAIA_SOURCE_ID_SHIFT = 35  # source_id >> 35 is the level-12 nested index


def _spread_bits(v: NDArray[np.uint64]) -> NDArray[np.uint64]:
    """Spread the low 32 bits of v so that bit i moves to bit 2i."""
    v = v.astype(np.uint64)
    v = (v | (v << np.uint64(16))) & np.uint64(0x0000FFFF0000FFFF)
    v = (v | (v << np.uint64(8))) & np.uint64(0x00FF00FF00FF00FF)
    v = (v | (v << np.uint64(4))) & np.uint64(0x0F0F0F0F0F0F0F0F)
    v = (v | (v << np.uint64(2))) & np.uint64(0x3333333333333333)
    v = (v | (v << np.uint64(1))) & np.uint64(0x5555555555555555)
    return v


def ang2pix_nest(
    order: int, ra_deg: NDArray[np.float64] | float, dec_deg: NDArray[np.float64] | float
) -> NDArray[np.int64]:
    """Nested HEALPix index at `order` (nside = 2**order) of positions given in degrees."""
    nside = 1 << order
    ra = np.atleast_1d(np.asarray(ra_deg, dtype=np.float64))
    dec = np.atleast_1d(np.asarray(dec_deg, dtype=np.float64))
    z = np.sin(np.radians(dec))
    za = np.abs(z)
    tt = np.mod(ra, 360.0) / 90.0  # [0, 4)

    # Equatorial belt
    temp1 = nside * (0.5 + tt)
    temp2 = nside * z * 0.75
    jp_e = np.floor(temp1 - temp2).astype(np.int64)  # ascending edge line
    jm_e = np.floor(temp1 + temp2).astype(np.int64)  # descending edge line
    ifp = jp_e // nside
    ifm = jm_e // nside
    face_e = np.where(ifp == ifm, ifp | 4, np.where(ifp < ifm, ifp, ifm + 8))
    ix_e = jm_e & (nside - 1)
    iy_e = nside - (jp_e & (nside - 1)) - 1

    # Polar caps
    ntt = np.minimum(np.floor(tt).astype(np.int64), 3)
    tp = tt - ntt
    tmp = nside * np.sqrt(3.0 * (1.0 - za))
    jp_p = np.minimum(np.floor(tp * tmp).astype(np.int64), nside - 1)
    jm_p = np.minimum(np.floor((1.0 - tp) * tmp).astype(np.int64), nside - 1)
    north = z >= 0
    face_p = np.where(north, ntt, ntt + 8)
    ix_p = np.where(north, nside - jm_p - 1, jp_p)
    iy_p = np.where(north, nside - jp_p - 1, jm_p)

    equatorial = za <= 2.0 / 3.0
    face = np.where(equatorial, face_e, face_p)
    ix = np.where(equatorial, ix_e, ix_p)
    iy = np.where(equatorial, iy_e, iy_p)
    spread_x = _spread_bits(ix.astype(np.uint64)).astype(np.int64)
    spread_y = _spread_bits(iy.astype(np.uint64)).astype(np.int64)
    return (face << (2 * order)) + spread_x + (spread_y << 1)


def source_id_cell(source_id: NDArray[np.int64] | int, order: int) -> NDArray[np.int64]:
    """Nested HEALPix index at `order` (<= 12) that a Gaia source's ID was assigned in."""
    shift = GAIA_SOURCE_ID_SHIFT + 2 * (GAIA_HEALPIX_ORDER - order)
    return np.asarray(source_id, dtype=np.int64) >> shift


def cell_source_id_range(cell: int, order: int) -> tuple[int, int]:
    """Half-open `source_id` range [lo, hi) of the sources whose ID is in one cell at `order`."""
    shift = GAIA_SOURCE_ID_SHIFT + 2 * (GAIA_HEALPIX_ORDER - order)
    return cell << shift, (cell + 1) << shift


def n_cells(order: int) -> int:
    return 12 * 4**order
