"""Scheduled-run entry point: screen the default scope, then publish the result (ADR 0009).

    python -m app.publish                  # upload to the S3-compatible bucket in BUCKET_NAME
    make publish-local                     # dry run: --local-dir runs/publish --cache-dir cache/...

Runs the same pipeline as `make screen`, then publishes. On Fly the CelesTrak cache lives in a temp
dir, so every scheduled run fetches fresh. A local dry run passes `--cache-dir` so repeated runs
reuse the normal 2-hour cache instead of re-fetching inside CelesTrak's fair-use window.

Publishing overwrites the previous run's objects:

- `snapshots/current/<gp|satcat>-<group>.json.gz`: the exact CelesTrak responses behind this
  report, gzipped in the same format as `tests/regression/default_scope_snapshot/`, so any
  published report can be reproduced or frozen into a test.
- `snapshots/current/manifest.json`: the run id and file list for the snapshot above.
- `objects/current.json`: every screened object as a flat, propagation-ready record with TLE lines
  (ADR 0010, `app.reporting.objects_builder`). Stored gzipped and served with
  `Content-Encoding: gzip` and `Content-Type: application/json`, so a browser `fetch` decompresses
  it transparently. Several MB at full-catalog scope.
- `objects/<date>.json.gz` and `reports/<date>.json.gz`: dated copies for the globe's time slider
  (ADR 0011), gzipped and served with `Content-Encoding: gzip`. `<date>` is the UTC date of the
  run's window start; a second run on the same date overwrites it.
- `reports/current.json`: the report itself, uploaded last.

After everything above is published, the retention step deletes dated keys more than
`RETENTION_DAYS` days before this run's date and rewrites `history/index.json`, the list of dates
that have both a dated objects and a dated report key. A retention failure doesn't undo the
publish: the run still logs `"published"`, with a `retention_error` field, and exits non-zero.

Nothing is uploaded unless the pipeline finished, so a failed fetch or crash leaves the previous
report in place; the process exits non-zero so the failure shows in the Machine's logs. Each put
replaces one object atomically, but the set isn't transactional: if an upload fails partway, the
snapshot can be newer than the report. Consumers can check that the manifest's `run_id` matches the
report's.

`current.json` keys always hold the latest run; history is only the dated keys (ADR 0011).
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import re
import sys
import tempfile
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from app.config import Config, load_env
from app.conjunction_pipeline import peak_rss_mb, run_screening
from app.reporting.objects_builder import build_objects
from app.settings import DEFAULT_SETTINGS_PATH, load_settings

REPORT_KEY = "reports/current.json"
OBJECTS_KEY = "objects/current.json"
SNAPSHOT_PREFIX = "snapshots/current/"
INDEX_KEY = "history/index.json"
# Dated snapshots are kept for this many days before the current run's date (ADR 0011), so at most
# RETENTION_DAYS + 1 dated keys per prefix exist at once.
RETENTION_DAYS = 7
DATED_PREFIXES = ("objects/", "reports/")
DATED_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json\.gz$")
# Level 6: 5.42 MB for the 78 MB full-catalog report in 0.27 s, vs 5.07 MB in 0.97 s at level 9.
REPORT_GZIP_LEVEL = 6
# Short enough that a consumer sees the next daily run promptly, long enough to absorb bursts.
CACHE_CONTROL = "public, max-age=300"


class ObjectStore(Protocol):
    def put(
        self, key: str, body: bytes, *, content_type: str, content_encoding: str | None = None
    ) -> None: ...

    def list_keys(self, prefix: str) -> list[str]: ...

    def delete(self, key: str) -> None: ...


class S3Store:
    """Any S3-compatible bucket. On Fly, `fly storage create` sets every variable this reads."""

    def __init__(self, bucket: str) -> None:
        import boto3

        # Endpoint and credentials come from AWS_ENDPOINT_URL_S3 / AWS_ACCESS_KEY_ID /
        # AWS_SECRET_ACCESS_KEY, which boto3 reads from the environment on its own.
        self.bucket = bucket
        self.client = boto3.client("s3")

    def put(
        self, key: str, body: bytes, *, content_type: str, content_encoding: str | None = None
    ) -> None:
        if content_encoding:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                ContentEncoding=content_encoding,
                CacheControl=CACHE_CONTROL,
            )
        else:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                CacheControl=CACHE_CONTROL,
            )

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        for page in self.client.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=prefix
        ):
            keys += [obj["Key"] for obj in page.get("Contents", []) if "Key" in obj]
        return keys

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


class LocalStore:
    """Writes objects under a directory, for dry runs (`make publish-local`)."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def put(
        self, key: str, body: bytes, *, content_type: str, content_encoding: str | None = None
    ) -> None:
        # Bytes are written exactly as uploaded: objects/current.json stays gzipped on disk.
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    def list_keys(self, prefix: str) -> list[str]:
        base = self.root / prefix
        if not base.is_dir():
            return []
        return sorted(
            f"{prefix}{p.relative_to(base).as_posix()}" for p in base.rglob("*") if p.is_file()
        )

    def delete(self, key: str) -> None:
        (self.root / key).unlink(missing_ok=True)


def dated_key(prefix: str, day: date) -> str:
    return f"{prefix}{day.isoformat()}.json.gz"


def apply_retention(store: ObjectStore, *, run_date: date, run_id: str) -> dict[str, Any]:
    """Delete dated keys older than the window, then rewrite the history index (ADR 0011).

    Only keys named exactly `<prefix><YYYY-MM-DD>.json.gz` are ever deleted.
    """
    cutoff = run_date - timedelta(days=RETENTION_DAYS)
    deleted: list[str] = []
    kept: dict[str, set[date]] = {}
    for prefix in DATED_PREFIXES:
        kept[prefix] = set()
        for key in store.list_keys(prefix):
            m = DATED_NAME.match(key[len(prefix) :])
            if not m:
                continue
            day = date.fromisoformat(m.group(1))
            if day < cutoff:
                store.delete(key)
                deleted.append(key)
            else:
                kept[prefix].add(day)
    days = sorted(set.intersection(*kept.values()), reverse=True)
    index = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "latest_run_id": run_id,
        "retention_days": RETENTION_DAYS,
        "dates": [
            {
                "date": d.isoformat(),
                "objects_key": dated_key("objects/", d),
                "report_key": dated_key("reports/", d),
            }
            for d in days
        ],
    }
    store.put(INDEX_KEY, json.dumps(index, indent=1).encode(), content_type="application/json")
    return {"retained_dates": len(days), "deleted": deleted}


def publish(
    store: ObjectStore,
    *,
    config: Config,
    settings_path: Path,
    cache_dir: Path | None = None,
) -> dict[str, object]:
    """Run the pipeline and publish snapshot + report. Returns a summary for the run log."""
    with tempfile.TemporaryDirectory() as tmp:
        base = load_settings(settings_path)
        settings = replace(
            base,
            source=replace(base.source, cache_dir=str(cache_dir or Path(tmp) / "cache")),
            report_dir=str(Path(tmp) / "reports"),
        )
        out = run_screening(settings, config=config)
        run_id = out.report["run_id"]

        snapshot_files = []
        cache = Path(settings.source.cache_dir)
        for path in [
            cache / f"{kind}-{g}.json" for g in settings.groups for kind in ("gp", "satcat")
        ]:
            name = f"{path.name}.gz"
            # mtime=0 keeps the gzip bytes a pure function of the content.
            store.put(
                SNAPSHOT_PREFIX + name,
                gzip.compress(path.read_bytes(), mtime=0),
                content_type="application/gzip",
            )
            snapshot_files.append(name)
        manifest = {"run_id": run_id, "groups": list(settings.groups), "files": snapshot_files}
        store.put(
            SNAPSHOT_PREFIX + "manifest.json",
            json.dumps(manifest, indent=1).encode(),
            content_type="application/json",
        )
        objects_doc = build_objects(
            run_id=run_id, generated_at_utc=out.report["generated_at_utc"], objects=out.objects
        )
        objects_gz = gzip.compress(json.dumps(objects_doc).encode(), mtime=0)
        store.put(OBJECTS_KEY, objects_gz, content_type="application/json", content_encoding="gzip")
        report_bytes = out.report_path.read_bytes()
        run_date = date.fromisoformat(out.report["window"]["start_utc"][:10])
        report_gz = gzip.compress(report_bytes, compresslevel=REPORT_GZIP_LEVEL, mtime=0)
        for key, body in (
            (dated_key("objects/", run_date), objects_gz),
            (dated_key("reports/", run_date), report_gz),
        ):
            store.put(key, body, content_type="application/json", content_encoding="gzip")
        store.put(REPORT_KEY, report_bytes, content_type="application/json")

    retention: dict[str, Any]
    try:
        retention = apply_retention(store, run_date=run_date, run_id=run_id)
    except Exception as exc:  # the run is already published; surface this without undoing it
        retention = {"retention_error": repr(exc)}

    summary = out.report["summary"]
    return {
        "event": "published",
        "run_id": run_id,
        "objects_screened": out.report["scope"]["objects_screened"],
        "conjunctions": summary["conjunctions_flagged"],
        "by_risk_level": summary["by_risk_level"],
        "co_located_pairs": summary["co_located_pairs"],
        "snapshot_files": len(snapshot_files),
        "objects_published": objects_doc["object_count"],
        "objects_gz_mb": round(len(objects_gz) / 1e6, 2),
        "report_mb": round(len(report_bytes) / 1e6, 2),
        "report_gz_mb": round(len(report_gz) / 1e6, 2),
        "dated_snapshot": run_date.isoformat(),
        **retention,
        "timings_s": out.timings_s,
        # Whole-process high-water mark, including publishing: what the Machine must fit.
        "peak_rss_mb": peak_rss_mb(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Screen the default scope and publish the report.")
    parser.add_argument("--config", type=Path, default=DEFAULT_SETTINGS_PATH)
    parser.add_argument("--local-dir", type=Path, help="write objects here instead of the bucket")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="reuse this CelesTrak cache (local dry runs) instead of a temp dir",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    load_env()

    store: ObjectStore
    if args.local_dir:
        store = LocalStore(args.local_dir)
    else:
        bucket = os.environ.get("BUCKET_NAME")
        if not bucket:
            print(json.dumps({"event": "failed", "error": "BUCKET_NAME not set"}), file=sys.stderr)
            return 2
        store = S3Store(bucket)
    try:
        result = publish(
            store, config=Config.from_env(), settings_path=args.config, cache_dir=args.cache_dir
        )
    except Exception as exc:  # logged as one line for `fly logs`; previous report stays in place
        print(json.dumps({"event": "failed", "error": repr(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 1 if "retention_error" in result else 0


if __name__ == "__main__":
    raise SystemExit(main())
