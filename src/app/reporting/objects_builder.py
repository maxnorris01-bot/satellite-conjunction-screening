"""`objects/current.json`: every screened object as a flat, propagation-ready record (ADR 0010).

The report carries full object detail only for objects in a flagged conjunction or co-located pair.
The planned globe, filtering, sky-view, satellite-POV and near-miss-replay features all need the
*whole* screened catalog, propagated client-side (e.g. `satellite.js`) from TLE lines. This builds
that list from the same objects and run as the report, so a consumer can join on `run_id`.

TLE lines are exported from each object's OMM elements with `sgp4.exporter.export_tle`. Catalog
numbers above 99999 come out in Alpha-5 form (100057 -> "A0057"), which is the TLE standard for
them; `norad_id` always carries the full integer.

`international_designator` is the object's COSPAR ID from CelesTrak's `OBJECT_ID` (e.g.
"1998-067A"), the same value the report's object records carry. Its first four characters are the
launch year. It's null when the source value is blank. Added 2026-10-06 without a schema bump, so
objects files written before then (including retained dated snapshots, ADR 0011) don't have the key
at all: readers must treat a missing key the same as null.

`OBJECTS_SCHEMA_VERSION` follows the report's rule: bump only when an existing field is renamed,
removed or changes meaning; additive fields don't bump it.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sgp4 import exporter

from app.data.models import CatalogObject
from app.data.satcat_owners import owner_record
from app.propagation.sgp4_propagator import build_satrec

OBJECTS_SCHEMA_VERSION = 1


def object_entry(obj: CatalogObject) -> dict[str, Any]:
    line1, line2 = exporter.export_tle(build_satrec(obj))
    return {
        "norad_id": obj.norad_id,
        "name": obj.name,
        "international_designator": obj.object_id.strip() or None,
        "tle_line1": line1,
        "tle_line2": line2,
        "element_epoch_utc": obj.epoch.isoformat().replace("+00:00", "Z"),
        "satcat_owner": owner_record(obj.satcat_owner),
        "object_type": obj.object_type,
        "active_payload": obj.is_active,
        "source_groups": list(obj.groups),
    }


def build_objects(
    *, run_id: str, generated_at_utc: str, objects: Iterable[CatalogObject]
) -> dict[str, Any]:
    entries = [object_entry(o) for o in objects]
    return {
        "schema_version": OBJECTS_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at_utc": generated_at_utc,
        "object_count": len(entries),
        "objects": entries,
    }
