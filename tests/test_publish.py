"""`app.publish`: what gets uploaded, in what order, and that a failed run uploads nothing."""

from __future__ import annotations

import gzip
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app import publish as pub
from app.config import Config
from conftest import gp_record, objects_from


class FakeStore:
    """In-memory bucket: records every put in order, and supports list/delete for retention."""

    def __init__(self, existing: list[str] | None = None) -> None:
        self.puts: list[tuple[str, bytes, str]] = []
        self.encodings: dict[str, str | None] = {}
        self.objects: dict[str, bytes] = {k: b"old" for k in existing or []}
        self.deleted: list[str] = []

    def put(
        self, key: str, body: bytes, *, content_type: str, content_encoding: str | None = None
    ) -> None:
        self.puts.append((key, body, content_type))
        self.encodings[key] = content_encoding
        self.objects[key] = body

    def list_keys(self, prefix: str) -> list[str]:
        return sorted(k for k in self.objects if k.startswith(prefix))

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)
        self.deleted.append(key)


def _fake_run_screening(settings: Any, *, config: Config) -> Any:
    """Stand-in pipeline: writes two cache files and a report where the real one would."""
    cache = Path(settings.source.cache_dir)
    cache.mkdir(parents=True)
    for group in settings.groups:
        (cache / f"gp-{group}.json").write_text(json.dumps({"payload": [group]}))
        (cache / f"satcat-{group}.json").write_text(json.dumps({"payload": []}))
    report = {
        "run_id": "20261001T0000Z-abc123",
        "generated_at_utc": "2026-10-01T00:00:05Z",
        "window": {"start_utc": "2026-10-01T00:00:00Z"},
        "scope": {"objects_screened": 2},
        "summary": {
            "conjunctions_flagged": 1,
            "by_risk_level": {"high": 0, "moderate": 1, "low": 0},
            "co_located_pairs": 0,
        },
    }
    path = Path(settings.report_dir) / "r.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(report))

    (obj,) = objects_from([gp_record()])
    return SimpleNamespace(
        report=report,
        report_path=path,
        timings_s={"total": 1.0},
        objects=[replace(obj, object_type="PAY", ops_status="+", satcat_owner="ISS")],
    )


@pytest.fixture
def settings_file(tmp_path: Path) -> Path:
    path = tmp_path / "screening.yaml"
    path.write_text("scope:\n  groups: [g1]\n")
    return path


def test_publishes_snapshot_then_manifest_then_report(
    monkeypatch: pytest.MonkeyPatch, settings_file: Path
) -> None:
    monkeypatch.setattr(pub, "run_screening", _fake_run_screening)
    store = FakeStore()
    summary = pub.publish(store, config=Config(tracing_disabled=True), settings_path=settings_file)

    keys = [k for k, _, _ in store.puts]
    assert keys == [
        "snapshots/current/gp-g1.json.gz",
        "snapshots/current/satcat-g1.json.gz",
        "snapshots/current/manifest.json",
        "objects/current.json",
        "objects/2026-10-01.json.gz",
        "reports/2026-10-01.json.gz",
        "reports/current.json",
        "history/index.json",
    ]
    by_key = {k: (body, ct) for k, body, ct in store.puts}
    gp_body, gp_type = by_key["snapshots/current/gp-g1.json.gz"]
    assert gp_type == "application/gzip"
    assert json.loads(gzip.decompress(gp_body)) == {"payload": ["g1"]}
    manifest = json.loads(by_key["snapshots/current/manifest.json"][0])
    assert manifest == {
        "run_id": "20261001T0000Z-abc123",
        "groups": ["g1"],
        "files": ["gp-g1.json.gz", "satcat-g1.json.gz"],
    }
    objects_body, objects_type = by_key["objects/current.json"]
    assert objects_type == "application/json"
    assert store.encodings["objects/current.json"] == "gzip"
    assert store.encodings["reports/current.json"] is None
    objects_doc = json.loads(gzip.decompress(objects_body))
    assert objects_doc["run_id"] == manifest["run_id"]
    assert objects_doc["generated_at_utc"] == "2026-10-01T00:00:05Z"
    assert objects_doc["object_count"] == 1
    assert objects_doc["objects"][0]["norad_id"] == 25544
    assert summary["objects_published"] == 1
    report_body, report_type = by_key["reports/current.json"]
    assert report_type == "application/json"
    assert json.loads(report_body)["run_id"] == manifest["run_id"]
    assert summary["run_id"] == manifest["run_id"]
    assert summary["by_risk_level"] == {"high": 0, "moderate": 1, "low": 0}


def test_failed_pipeline_uploads_nothing_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, settings_file: Path, tmp_path: Path
) -> None:
    def boom(settings: Any, *, config: Config) -> Any:
        raise RuntimeError("CelesTrak unreachable")

    monkeypatch.setattr(pub, "run_screening", boom)
    out_dir = tmp_path / "out"
    code = pub.main(["--config", str(settings_file), "--local-dir", str(out_dir)])
    assert code == 1
    assert not out_dir.exists()


def test_missing_bucket_name_fails_before_running(
    monkeypatch: pytest.MonkeyPatch, settings_file: Path
) -> None:
    monkeypatch.delenv("BUCKET_NAME", raising=False)
    monkeypatch.setattr(pub, "load_env", lambda: None)

    def never(settings: Any, *, config: Config) -> Any:
        raise AssertionError("pipeline must not run without a bucket")

    monkeypatch.setattr(pub, "run_screening", never)
    assert pub.main(["--config", str(settings_file)]) == 2


def test_local_store_writes_objects_under_root(tmp_path: Path) -> None:
    pub.LocalStore(tmp_path).put("reports/current.json", b"{}", content_type="application/json")
    assert (tmp_path / "reports" / "current.json").read_bytes() == b"{}"


def _publish(store: FakeStore, monkeypatch: pytest.MonkeyPatch, settings_file: Path) -> Any:
    monkeypatch.setattr(pub, "run_screening", _fake_run_screening)
    return pub.publish(store, config=Config(tracing_disabled=True), settings_path=settings_file)


def test_dated_snapshots_are_gzip_json_matching_current(
    monkeypatch: pytest.MonkeyPatch, settings_file: Path
) -> None:
    store = FakeStore()
    summary = _publish(store, monkeypatch, settings_file)
    assert summary["dated_snapshot"] == "2026-10-01"
    for prefix in ("objects", "reports"):
        key = f"{prefix}/2026-10-01.json.gz"
        assert store.encodings[key] == "gzip"
        assert dict((k, ct) for k, _, ct in store.puts)[key] == "application/json"
    assert store.objects["objects/2026-10-01.json.gz"] == store.objects["objects/current.json"]
    dated_report = json.loads(gzip.decompress(store.objects["reports/2026-10-01.json.gz"]))
    assert dated_report == json.loads(store.objects["reports/current.json"])


def test_retention_prunes_only_dated_keys_older_than_seven_days(
    monkeypatch: pytest.MonkeyPatch, settings_file: Path
) -> None:
    # The run's date is 2026-10-01, so the cutoff is 2026-09-24: that date is kept, 09-23 is not.
    existing = [
        "objects/2026-09-23.json.gz",
        "reports/2026-09-23.json.gz",
        "objects/2026-09-24.json.gz",
        "reports/2026-09-24.json.gz",
        "objects/2026-09-30.json.gz",  # no matching report: kept, but not in the index
        "reports/2026-09-01.json.gz",
        "objects/notes-2026-09-01.json.gz",  # not the exact dated pattern: never touched
        "objects/archive/2026-09-01.json.gz",
        "snapshots/current/manifest.json",
    ]
    store = FakeStore(existing)
    summary = _publish(store, monkeypatch, settings_file)

    assert sorted(store.deleted) == [
        "objects/2026-09-23.json.gz",
        "reports/2026-09-01.json.gz",
        "reports/2026-09-23.json.gz",
    ]
    for key in ("objects/notes-2026-09-01.json.gz", "objects/archive/2026-09-01.json.gz"):
        assert key in store.objects
    assert "objects/2026-09-30.json.gz" in store.objects
    assert summary["retained_dates"] == 2 and "retention_error" not in summary

    index = json.loads(store.objects["history/index.json"])
    assert index["retention_days"] == 7
    assert index["latest_run_id"] == "20261001T0000Z-abc123"
    assert index["dates"] == [
        {
            "date": "2026-10-01",
            "objects_key": "objects/2026-10-01.json.gz",
            "report_key": "reports/2026-10-01.json.gz",
        },
        {
            "date": "2026-09-24",
            "objects_key": "objects/2026-09-24.json.gz",
            "report_key": "reports/2026-09-24.json.gz",
        },
    ]


def test_retention_failure_keeps_publish_but_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, settings_file: Path, tmp_path: Path, capsys: Any
) -> None:
    monkeypatch.setattr(pub, "run_screening", _fake_run_screening)

    def broken_list(self: Any, prefix: str) -> list[str]:
        raise RuntimeError("list denied")

    monkeypatch.setattr(pub.LocalStore, "list_keys", broken_list)
    out_dir = tmp_path / "out"
    code = pub.main(["--config", str(settings_file), "--local-dir", str(out_dir)])
    assert code == 1
    assert (out_dir / "reports" / "current.json").exists()
    assert (out_dir / "reports" / "2026-10-01.json.gz").exists()
    logged = json.loads(capsys.readouterr().out)
    assert logged["event"] == "published"
    assert "list denied" in logged["retention_error"]


def test_local_store_lists_and_deletes(tmp_path: Path) -> None:
    store = pub.LocalStore(tmp_path)
    for key in ("objects/2026-10-01.json.gz", "objects/current.json", "reports/x.json"):
        store.put(key, b"x", content_type="application/json")
    assert store.list_keys("objects/") == ["objects/2026-10-01.json.gz", "objects/current.json"]
    assert store.list_keys("missing/") == []
    store.delete("objects/2026-10-01.json.gz")
    store.delete("objects/never-existed.json.gz")
    assert store.list_keys("objects/") == ["objects/current.json"]
