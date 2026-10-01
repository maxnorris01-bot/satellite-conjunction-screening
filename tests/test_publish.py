"""`app.publish`: what gets uploaded, in what order, and that a failed run uploads nothing."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app import publish as pub
from app.config import Config


class FakeStore:
    def __init__(self) -> None:
        self.puts: list[tuple[str, bytes, str]] = []

    def put(self, key: str, body: bytes, *, content_type: str) -> None:
        self.puts.append((key, body, content_type))


def _fake_run_screening(settings: Any, *, config: Config) -> Any:
    """Stand-in pipeline: writes two cache files and a report where the real one would."""
    cache = Path(settings.source.cache_dir)
    cache.mkdir(parents=True)
    for group in settings.groups:
        (cache / f"gp-{group}.json").write_text(json.dumps({"payload": [group]}))
        (cache / f"satcat-{group}.json").write_text(json.dumps({"payload": []}))
    report = {
        "run_id": "20261001T0000Z-abc123",
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

    return SimpleNamespace(report=report, report_path=path, timings_s={"total": 1.0})


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
        "reports/current.json",
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
