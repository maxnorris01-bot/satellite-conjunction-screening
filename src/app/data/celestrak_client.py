"""`fetch_tle_data` primary path: CelesTrak GP (elements) + SATCAT (object type/status) data.

No account or auth. Both endpoints are cached on disk for `cache_ttl_hours` (see `tle_cache`).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

import httpx

from app.data.models import CatalogObject, TleSet
from app.data.tle_cache import ResponseCache
from app.settings import SourceSettings

log = logging.getLogger(__name__)

SOURCE = "celestrak"
USER_AGENT = "satellite-conjunction-screening/0.1 (portfolio project; cached, <=1 req/2h/group)"
REQUIRED_FIELDS = (
    "OBJECT_NAME",
    "OBJECT_ID",
    "EPOCH",
    "NORAD_CAT_ID",
    "MEAN_MOTION",
    "ECCENTRICITY",
    "INCLINATION",
    "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER",
    "MEAN_ANOMALY",
    "BSTAR",
    "MEAN_MOTION_DOT",
    "MEAN_MOTION_DDOT",
)


class CelesTrakError(RuntimeError):
    """CelesTrak returned something other than a JSON list of records."""


def parse_epoch(value: str) -> datetime:
    """Parse an OMM EPOCH (`2026-09-27T04:10:50.460096`, UTC, fractional seconds optional)."""
    if "." not in value:
        value = value + ".000000"
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=UTC)


def _get_json(client: httpx.Client, url: str, params: dict[str, str]) -> list[dict[str, Any]]:
    resp = client.get(url, params=params)
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError as exc:
        # An unknown group name comes back as HTTP 200 with a plain-text message, not JSON.
        raise CelesTrakError(f"{resp.url}: non-JSON response: {resp.text[:200]!r}") from exc
    if not isinstance(data, list):
        raise CelesTrakError(f"{resp.url}: expected a JSON list, got {type(data).__name__}")
    return data


def parse_gp_records(
    records: Iterable[dict[str, Any]],
    *,
    group: str,
    fetched_at: datetime,
) -> tuple[list[CatalogObject], list[dict[str, Any]]]:
    """Normalize raw GP JSON records. Returns (objects, failures); never raises on a bad record."""
    objects: list[CatalogObject] = []
    failures: list[dict[str, Any]] = []
    for rec in records:
        try:
            missing = [f for f in REQUIRED_FIELDS if rec.get(f) in (None, "")]
            if missing:
                raise ValueError(f"missing fields {missing}")
            objects.append(
                CatalogObject(
                    norad_id=int(rec["NORAD_CAT_ID"]),
                    name=str(rec["OBJECT_NAME"]).strip(),
                    object_id=str(rec["OBJECT_ID"]),
                    epoch=parse_epoch(str(rec["EPOCH"])),
                    elements=dict(rec),
                    source=SOURCE,
                    groups=(group,),
                    fetched_at=fetched_at,
                )
            )
        except (ValueError, TypeError, KeyError) as exc:
            failures.append({"group": group, "record": rec, "error": repr(exc)})
    return objects, failures


def merge_objects(objects: Iterable[CatalogObject]) -> list[CatalogObject]:
    """Merge duplicates across groups by catalog number, keeping the newest epoch."""
    by_id: dict[int, CatalogObject] = {}
    for obj in objects:
        prev = by_id.get(obj.norad_id)
        if prev is None:
            by_id[obj.norad_id] = obj
            continue
        groups = tuple(dict.fromkeys(prev.groups + obj.groups))
        newest = obj if obj.epoch > prev.epoch else prev
        by_id[obj.norad_id] = replace(newest, groups=groups)
    return [by_id[k] for k in sorted(by_id)]


def fetch_tle_data(
    groups: Iterable[str],
    settings: SourceSettings,
    *,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> tuple[TleSet, dict[str, Any]]:
    """Fetch GP elements and SATCAT metadata for CelesTrak named groups.

    Returns the normalized `TleSet` and a stats dict (per-group counts, cache hits) for tracing.
    """
    groups = tuple(groups)
    cache = ResponseCache(Path(settings.cache_dir), timedelta(hours=settings.cache_ttl_hours))
    base = settings.celestrak_base_url.rstrip("/")
    owns_client = client is None
    http = client or httpx.Client(
        timeout=settings.http_timeout_s, headers={"User-Agent": USER_AGENT}
    )
    stats: dict[str, Any] = {"groups": {}, "cache_hits": 0, "http_requests": 0}
    all_objects: list[CatalogObject] = []
    failures: list[dict[str, Any]] = []
    satcat: dict[int, dict[str, Any]] = {}
    fetched_times: list[datetime] = []
    try:
        for group in groups:
            params = {"GROUP": group, "FORMAT": "JSON"}
            gp = cache.get_or_fetch(
                f"gp-{group}",
                partial(_get_json, http, f"{base}/NORAD/elements/gp.php", params),
                now=now,
            )
            sc = cache.get_or_fetch(
                f"satcat-{group}",
                partial(_get_json, http, f"{base}/satcat/records.php", params),
                now=now,
            )
            for resp in (gp, sc):
                stats["cache_hits" if resp.from_cache else "http_requests"] += 1
            fetched_times.append(gp.fetched_at)
            objs, fails = parse_gp_records(gp.payload, group=group, fetched_at=gp.fetched_at)
            all_objects.extend(objs)
            failures.extend(fails)
            for rec in sc.payload:
                if rec.get("NORAD_CAT_ID") is not None:
                    satcat[int(rec["NORAD_CAT_ID"])] = rec
            stats["groups"][group] = {
                "gp_records": len(gp.payload),
                "parsed": len(objs),
                "parse_failures": len(fails),
                "satcat_records": len(sc.payload),
                "gp_fetched_at": gp.fetched_at.isoformat(),
                "gp_from_cache": gp.from_cache,
            }
    finally:
        if owns_client:
            http.close()

    merged = []
    for obj in merge_objects(all_objects):
        meta = satcat.get(obj.norad_id)
        if meta is None:
            log.warning("no SATCAT record for %s (%s)", obj.norad_id, obj.name)
            merged.append(obj)
            continue
        merged.append(
            replace(
                obj,
                object_type=meta.get("OBJECT_TYPE") or None,
                ops_status=meta.get("OPS_STATUS_CODE") or "",
            )
        )
    stats["objects"] = len(merged)
    stats["parse_failures"] = len(failures)
    stats["missing_satcat"] = sum(1 for o in merged if o.object_type is None)
    tle_set = TleSet(
        objects=merged,
        source=SOURCE,
        groups=groups,
        fetched_at=min(fetched_times) if fetched_times else (now or datetime.now(UTC)),
        parse_failures=failures,
    )
    return tle_set, stats
