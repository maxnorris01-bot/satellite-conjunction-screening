"""Binary encodings for the star tiles and their details files (format version 1).

The spec, with the reasoning, is docs/star-data-format.md. In short, per star:
- tile file (the part every view needs): RA, Dec (24-bit each), G magnitude, BP-RP colour (8 bits
  each), stored as four columns, brightest star first;
- details file (loaded only for a selected star): Gaia source ID, parallax and its error.
Everything is little-endian.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

TILE_MAGIC = b"GAIT"
DETAILS_MAGIC = b"GAID"
VERSION = 1
HEADER_BYTES = 32

# G magnitude byte: round((G - MAG_OFFSET) * MAG_SCALE). Range -1.0 to 22.18, steps of 0.091 mag.
MAG_OFFSET = -1.0
MAG_SCALE = 11.0
# BP-RP byte: round((bp_rp - COL_OFFSET) * COL_SCALE); 0 means "no colour". Range -0.96 to 9.2.
COL_OFFSET = -1.0
COL_SCALE = 25.0
COL_UNKNOWN = 0
# Parallax int16 in 1/40 mas (range +-819 mas, Proxima is 768); -32768 = none.
PLX_SCALE = 40.0
PLX_NONE = -32768
# Parallax error uint8 in 0.005 mas steps (0 to 1.27 mas); 255 = none or larger.
EPLX_SCALE = 200.0
EPLX_NONE = 255

FLAG_NO_COLOUR = 1  # BP-RP missing (the colour byte is 0)

RA_STEPS = 2**24
DEC_STEPS = 2**24 - 1


def encode_ra(ra_deg: NDArray[np.float64]) -> NDArray[np.uint32]:
    q = np.rint(np.mod(ra_deg, 360.0) / 360.0 * RA_STEPS).astype(np.int64) % RA_STEPS
    return q.astype(np.uint32)


def decode_ra(q: NDArray[np.uint32]) -> NDArray[np.float64]:
    return q.astype(np.float64) / RA_STEPS * 360.0


def encode_dec(dec_deg: NDArray[np.float64]) -> NDArray[np.uint32]:
    q = np.rint((np.clip(dec_deg, -90.0, 90.0) + 90.0) / 180.0 * DEC_STEPS)
    return q.astype(np.uint32)


def decode_dec(q: NDArray[np.uint32]) -> NDArray[np.float64]:
    return q.astype(np.float64) / DEC_STEPS * 180.0 - 90.0


def encode_mag(g: NDArray[np.float64]) -> NDArray[np.uint8]:
    return np.clip(np.rint((g - MAG_OFFSET) * MAG_SCALE), 0, 255).astype(np.uint8)


def decode_mag(b: NDArray[np.uint8]) -> NDArray[np.float64]:
    return b.astype(np.float64) / MAG_SCALE + MAG_OFFSET


def encode_colour(bp_rp: NDArray[np.float64]) -> NDArray[np.uint8]:
    """BP-RP to a byte; NaN becomes COL_UNKNOWN, and real values never use that code."""
    q = np.clip(np.rint((bp_rp - COL_OFFSET) * COL_SCALE), 1, 255)
    return np.where(np.isnan(bp_rp), COL_UNKNOWN, q).astype(np.uint8)


def decode_colour(b: NDArray[np.uint8]) -> NDArray[np.float64]:
    out = b.astype(np.float64) / COL_SCALE + COL_OFFSET
    return np.where(b == COL_UNKNOWN, np.nan, out)


def encode_parallax(plx_mas: NDArray[np.float64]) -> NDArray[np.int16]:
    q = np.clip(np.rint(plx_mas * PLX_SCALE), -32767, 32767)
    return np.where(np.isnan(plx_mas), PLX_NONE, q).astype(np.int16)


def encode_parallax_error(eplx_mas: NDArray[np.float64]) -> NDArray[np.uint8]:
    q = np.clip(np.rint(eplx_mas * EPLX_SCALE), 0, 254)
    return np.where(np.isnan(eplx_mas), EPLX_NONE, q).astype(np.uint8)


def _u24(q: NDArray[np.uint32]) -> bytes:
    a = q.astype(np.uint32)
    return np.stack([a & 255, (a >> 8) & 255, (a >> 16) & 255], axis=1).astype(np.uint8).tobytes()


def _read_u24(buf: bytes, offset: int, n: int) -> NDArray[np.uint32]:
    a = np.frombuffer(buf, dtype=np.uint8, count=3 * n, offset=offset).reshape(n, 3)
    return (
        a[:, 0].astype(np.uint32)
        | (a[:, 1].astype(np.uint32) << 8)
        | (a[:, 2].astype(np.uint32) << 16)
    )


@dataclass(frozen=True)
class Tile:
    order: int
    ipix: int
    epoch: float
    ra: NDArray[np.uint32]
    dec: NDArray[np.uint32]
    mag: NDArray[np.uint8]
    colour: NDArray[np.uint8]

    @property
    def count(self) -> int:
        return len(self.mag)


def write_tile(t: Tile) -> bytes:
    """Header (32 B), then columns of `count` entries: ra u24, dec u24, mag u8, colour u8."""
    n = t.count
    if not (len(t.ra) == len(t.dec) == len(t.colour) == n):
        raise ValueError("tile columns differ in length")
    header = struct.pack("<4sHBBIIf", TILE_MAGIC, VERSION, t.order, 0, t.ipix, n, t.epoch)
    header += b"\x00" * (HEADER_BYTES - len(header))
    return header + _u24(t.ra) + _u24(t.dec) + t.mag.tobytes() + t.colour.tobytes()


def read_tile(buf: bytes) -> Tile:
    magic, version, order, _res, ipix, n, epoch = struct.unpack_from("<4sHBBIIf", buf, 0)
    if magic != TILE_MAGIC or version != VERSION:
        raise ValueError("not a version 1 star tile")
    if len(buf) != HEADER_BYTES + 8 * n:
        raise ValueError("star tile has the wrong length")
    ra_at = HEADER_BYTES
    dec_at = ra_at + 3 * n
    mag_at = dec_at + 3 * n
    col_at = mag_at + n
    return Tile(
        order=order,
        ipix=ipix,
        epoch=epoch,
        ra=_read_u24(buf, ra_at, n),
        dec=_read_u24(buf, dec_at, n),
        mag=np.frombuffer(buf, dtype=np.uint8, count=n, offset=mag_at).copy(),
        colour=np.frombuffer(buf, dtype=np.uint8, count=n, offset=col_at).copy(),
    )


@dataclass(frozen=True)
class Details:
    source_id: NDArray[np.int64]
    parallax: NDArray[np.int16]
    parallax_error: NDArray[np.uint8]
    flags: NDArray[np.uint8]

    @property
    def count(self) -> int:
        return len(self.source_id)


def write_details(d: Details) -> bytes:
    """Header (32 B), then columns of `count` entries: source_id u64, plx i16, eplx u8, flags u8."""
    n = d.count
    header = struct.pack("<4sHHI", DETAILS_MAGIC, VERSION, 0, n)
    header += b"\x00" * (HEADER_BYTES - len(header))
    return (
        header
        + d.source_id.astype("<u8").tobytes()
        + d.parallax.astype("<i2").tobytes()
        + d.parallax_error.tobytes()
        + d.flags.tobytes()
    )


def read_details(buf: bytes) -> Details:
    magic, version, _res, n = struct.unpack_from("<4sHHI", buf, 0)
    if magic != DETAILS_MAGIC or version != VERSION:
        raise ValueError("not a version 1 star details file")
    if len(buf) != HEADER_BYTES + 12 * n:
        raise ValueError("star details file has the wrong length")
    at = HEADER_BYTES
    sid = np.frombuffer(buf, dtype="<u8", count=n, offset=at).astype(np.int64)
    at += 8 * n
    plx = np.frombuffer(buf, dtype="<i2", count=n, offset=at).astype(np.int16)
    at += 2 * n
    eplx = np.frombuffer(buf, dtype=np.uint8, count=n, offset=at).copy()
    at += n
    flags = np.frombuffer(buf, dtype=np.uint8, count=n, offset=at).copy()
    return Details(sid, plx, eplx, flags)
