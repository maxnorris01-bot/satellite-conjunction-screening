"""Normalized catalog records, independent of which source supplied them."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# CelesTrak SATCAT operational status codes that mean "this payload is (at least partly) working",
# so it may be maneuverable and is worth protecting. Anything else ("-" nonoperational, "D" decayed,
# "?" unknown, "" for non-payloads) is not counted as active.
# https://celestrak.org/satcat/status.php
ACTIVE_STATUS_CODES = frozenset({"+", "P", "B", "S", "X"})


@dataclass(frozen=True)
class CatalogObject:
    """One tracked object's mean elements plus the metadata `assess_risk` needs.

    `elements` holds the raw CCSDS OMM fields exactly as CelesTrak's GP JSON returns them - the same
    mean-element content as a two-line element set, but without the 5-digit catalog-number limit
    that TLE lines have (catalog numbers above 99999 are already live in the stations group).
    """

    norad_id: int
    name: str
    object_id: str
    epoch: datetime
    elements: dict[str, Any]
    source: str
    groups: tuple[str, ...]
    fetched_at: datetime
    # From SATCAT: "PAY", "R/B", "DEB", "UNK", or None if SATCAT had no record.
    object_type: str | None = None
    ops_status: str | None = None
    # SATCAT's OWNER code ("US", "PRC", ...): the registering state or organization, not the
    # operator. None if SATCAT had no record or left it blank. See app.data.satcat_owners.
    satcat_owner: str | None = None

    @property
    def is_active(self) -> bool | None:
        """True/False from SATCAT, or None if unknown (no SATCAT record)."""
        if self.object_type is None:
            return None
        return self.object_type == "PAY" and self.ops_status in ACTIVE_STATUS_CODES


@dataclass
class TleSet:
    """The normalized result of `fetch_tle_data`: objects in a stable, catalog-number order."""

    objects: list[CatalogObject]
    source: str
    groups: tuple[str, ...]
    fetched_at: datetime
    parse_failures: list[dict[str, Any]] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.objects)
