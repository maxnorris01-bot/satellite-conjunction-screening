from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app.data.celestrak_client import (
    CelesTrakError,
    fetch_tle_data,
    merge_objects,
    parse_epoch,
    parse_gp_records,
)
from app.data.tle_cache import ResponseCache
from app.settings import SourceSettings
from conftest import ISS_EPOCH, gp_record


def test_parse_epoch_with_and_without_fraction() -> None:
    assert parse_epoch("2026-09-27T04:10:50.460096") == ISS_EPOCH
    assert parse_epoch("2026-09-27T04:10:50") == ISS_EPOCH.replace(microsecond=0)


def test_parse_keeps_six_digit_catalog_numbers_and_reports_bad_records() -> None:
    records = [
        gp_record(),
        gp_record(NORAD_CAT_ID=100057, OBJECT_NAME="SOYUZ-MS 29"),
        gp_record(NORAD_CAT_ID=5, MEAN_MOTION=None),
        gp_record(NORAD_CAT_ID=6, EPOCH="not a date"),
    ]
    objs, failures = parse_gp_records(records, group="stations", fetched_at=ISS_EPOCH)
    assert [o.norad_id for o in objs] == [25544, 100057]
    assert len(failures) == 2
    assert all(f["group"] == "stations" for f in failures)


def test_merge_dedupes_across_groups_keeping_newest_epoch() -> None:
    older, _ = parse_gp_records([gp_record()], group="a", fetched_at=ISS_EPOCH)
    newer, _ = parse_gp_records(
        [gp_record(EPOCH="2026-09-28T00:00:00.000000")], group="b", fetched_at=ISS_EPOCH
    )
    merged = merge_objects(older + newer)
    assert len(merged) == 1
    assert merged[0].groups == ("a", "b")
    assert merged[0].epoch.day == 28


def test_cache_reuses_within_ttl_and_refetches_after(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path, timedelta(hours=2))
    calls: list[int] = []

    def fetch() -> list[int]:
        calls.append(1)
        return [len(calls)]

    t0 = datetime(2026, 9, 27, tzinfo=UTC)
    assert cache.get_or_fetch("k", fetch, now=t0).from_cache is False
    hit = cache.get_or_fetch("k", fetch, now=t0 + timedelta(minutes=119))
    assert hit.from_cache is True and hit.payload == [1]
    miss = cache.get_or_fetch("k", fetch, now=t0 + timedelta(minutes=121))
    assert miss.from_cache is False and miss.payload == [2]


def _fake_celestrak(requests: list[str]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        group = request.url.params["GROUP"]
        if group == "nope":
            return httpx.Response(200, text="Invalid query: GROUP=nope")
        if request.url.path.endswith("gp.php"):
            return httpx.Response(
                200,
                json=[gp_record(), gp_record(NORAD_CAT_ID=88888), gp_record(NORAD_CAT_ID=99999)],
            )
        # 88888 has no SATCAT record at all; 99999 has one with a blank OWNER.
        return httpx.Response(
            200,
            json=[
                {
                    "NORAD_CAT_ID": 25544,
                    "OBJECT_TYPE": "PAY",
                    "OPS_STATUS_CODE": "+",
                    "OWNER": "ISS",
                },
                {"NORAD_CAT_ID": 99999, "OBJECT_TYPE": "DEB", "OPS_STATUS_CODE": "", "OWNER": ""},
            ],
        )

    return httpx.MockTransport(handler)


def test_fetch_joins_satcat_metadata_and_caches(tmp_path: Path) -> None:
    requests: list[str] = []
    settings = SourceSettings(cache_dir=str(tmp_path))
    client = httpx.Client(transport=_fake_celestrak(requests))
    now = datetime(2026, 9, 27, 6, tzinfo=UTC)

    tle_set, stats = fetch_tle_data(["stations"], settings, client=client, now=now)
    assert len(requests) == 2  # one GP + one SATCAT request
    assert [(o.norad_id, o.object_type, o.is_active, o.satcat_owner) for o in tle_set.objects] == [
        (25544, "PAY", True, "ISS"),
        (88888, None, None, None),
        (99999, "DEB", False, None),
    ]
    assert stats["objects"] == 3 and stats["missing_satcat"] == 1

    fetch_tle_data(["stations"], settings, client=client, now=now + timedelta(hours=1))
    assert len(requests) == 2  # served from cache
    cached = json.loads((tmp_path / "gp-stations.json").read_text())
    assert cached["fetched_at"] == now.isoformat()


def test_fetch_rejects_non_json_group_response(tmp_path: Path) -> None:
    client = httpx.Client(transport=_fake_celestrak([]))
    with pytest.raises(CelesTrakError, match="non-JSON"):
        fetch_tle_data(["nope"], SourceSettings(cache_dir=str(tmp_path)), client=client)
