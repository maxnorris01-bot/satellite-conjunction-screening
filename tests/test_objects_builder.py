"""`objects/current.json` entries: fields, TLE export (incl. Alpha-5) and owner shape."""

from __future__ import annotations

from dataclasses import replace

import pytest
from sgp4.api import Satrec

from app.data.celestrak_client import parse_gp_records
from app.reporting.objects_builder import OBJECTS_SCHEMA_VERSION, build_objects, object_entry
from conftest import ISS_EPOCH, ISS_GP, gp_record, objects_from


def test_entry_fields_and_tle_round_trip() -> None:
    (iss,) = objects_from([gp_record()])
    iss = replace(iss, object_type="PAY", ops_status="+", satcat_owner="ISS", groups=("stations",))
    e = object_entry(iss)
    assert set(e) == {
        "norad_id",
        "name",
        "international_designator",
        "tle_line1",
        "tle_line2",
        "element_epoch_utc",
        "satcat_owner",
        "object_type",
        "active_payload",
        "source_groups",
    }
    assert e["norad_id"] == 25544 and e["name"] == "ISS (ZARYA)"
    assert e["international_designator"] == "1998-067A"
    assert e["element_epoch_utc"] == "2026-09-27T04:10:50.460096Z"
    assert e["satcat_owner"] == {"code": "ISS", "name": "International Space Station"}
    assert e["active_payload"] is True and e["source_groups"] == ["stations"]
    assert e["tle_line1"].startswith("1 25544U") and e["tle_line2"].startswith("2 25544 ")
    sat = Satrec.twoline2rv(e["tle_line1"], e["tle_line2"])
    assert sat.satnum == 25544
    assert abs(sat.inclo * 180 / 3.141592653589793 - ISS_GP["INCLINATION"]) < 1e-4


def test_catalog_numbers_above_99999_use_alpha5_and_keep_full_norad_id() -> None:
    (obj,) = objects_from([gp_record(NORAD_CAT_ID=100057)])
    e = object_entry(obj)
    assert e["norad_id"] == 100057
    assert e["tle_line1"].startswith("1 A0057U")
    assert Satrec.twoline2rv(e["tle_line1"], e["tle_line2"]).satnum == 100057


def test_no_satcat_record_gives_null_owner_and_unknown_activity() -> None:
    (obj,) = objects_from([gp_record()])
    e = object_entry(obj)
    assert e["satcat_owner"] is None and e["object_type"] is None and e["active_payload"] is None


def test_document_envelope() -> None:
    objs = objects_from([gp_record(), gp_record(NORAD_CAT_ID=88888)])
    doc = build_objects(run_id="r1", generated_at_utc="2026-10-01T00:00:00Z", objects=objs)
    assert doc["schema_version"] == OBJECTS_SCHEMA_VERSION == 1
    assert doc["run_id"] == "r1" and doc["object_count"] == 2
    assert [o["norad_id"] for o in doc["objects"]] == [25544, 88888]


@pytest.mark.parametrize("raw", ["", "   "])
def test_blank_designator_is_null_not_a_crash(raw: str) -> None:
    (obj,) = objects_from([gp_record()])
    assert object_entry(replace(obj, object_id=raw))["international_designator"] is None


def test_records_missing_object_id_never_reach_the_builder() -> None:
    # OBJECT_ID is a required GP field: a record without it (or with it empty) is reported as a
    # parse failure upstream, so the builder never sees an object with no designator attribute.
    for record in (
        {k: v for k, v in gp_record().items() if k != "OBJECT_ID"},
        gp_record(OBJECT_ID=""),
    ):
        objs, failures = parse_gp_records([record], group="g", fetched_at=ISS_EPOCH)
        assert objs == [] and len(failures) == 1
