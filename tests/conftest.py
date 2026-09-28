from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.data.celestrak_client import parse_gp_records

# Real CelesTrak GP record (ISS, fetched 2026-09-27), used as a known-good element set.
ISS_GP: dict[str, Any] = {
    "OBJECT_NAME": "ISS (ZARYA)",
    "OBJECT_ID": "1998-067A",
    "EPOCH": "2026-09-27T04:10:50.460096",
    "MEAN_MOTION": 15.48664528,
    "ECCENTRICITY": 0.0007168,
    "INCLINATION": 51.6315,
    "RA_OF_ASC_NODE": 155.3455,
    "ARG_OF_PERICENTER": 193.056,
    "MEAN_ANOMALY": 167.0244,
    "EPHEMERIS_TYPE": 0,
    "CLASSIFICATION_TYPE": "U",
    "NORAD_CAT_ID": 25544,
    "ELEMENT_SET_NO": 999,
    "REV_AT_EPOCH": 58756,
    "BSTAR": 0.00018291455,
    "MEAN_MOTION_DOT": 9.528e-05,
    "MEAN_MOTION_DDOT": 0,
}
ISS_EPOCH = datetime(2026, 9, 27, 4, 10, 50, 460096, tzinfo=UTC)


def gp_record(**overrides: Any) -> dict[str, Any]:
    return {**ISS_GP, **overrides}


def objects_from(records: list[dict[str, Any]], group: str = "test") -> list[Any]:
    objs, failures = parse_gp_records(records, group=group, fetched_at=ISS_EPOCH)
    assert not failures
    return objs
