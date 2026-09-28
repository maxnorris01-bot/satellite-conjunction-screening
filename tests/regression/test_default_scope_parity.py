"""Parity regression: the full pipeline on a frozen real-data snapshot vs. a known-good baseline.

Runs `run_screening` end to end (fetch from the snapshot, never the network -> propagate -> screen
-> assess -> report) on the exact CelesTrak responses and window behind run
`20260928T0101Z-c6e1f2`, and compares against that run's output (produced by the session-1 naive
all-pairs screen). Any screening change meant to be a pure speedup (the KD-tree, a coarse
filter, chunked propagation) must keep this passing unchanged. See README.md in this directory.

    uv run pytest tests/regression -v
"""

from __future__ import annotations

import gzip
import json
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config import Config
from app.conjunction_pipeline import run_screening
from app.settings import load_settings

HERE = Path(__file__).resolve().parent
SNAPSHOT_DIR = HERE / "default_scope_snapshot"
EXPECTED_PATH = HERE / "expected_default_scope.json"
REPO_ROOT = HERE.parents[1]

# Bit-identical on the machine the baseline was made on. The tolerances only absorb cross-platform
# float noise (CI runs Linux) and the report's 4-decimal rounding flipping a last digit; any real
# screening change moves these values by far more.
TCA_TOLERANCE_S = 0.01
KM_TOLERANCE = 2e-4


def canonicalize(report: dict[str, Any]) -> dict[str, Any]:
    """The comparable subset of a report. Also used to (deliberately) regenerate the baseline."""

    def rec(c: dict[str, Any]) -> dict[str, Any]:
        return {
            "norad_a": c["object_a"]["norad_id"],
            "norad_b": c["object_b"]["norad_id"],
            "tca_utc": c["tca_utc"],
            "miss_distance_km": c["miss_distance_km"],
            "relative_speed_km_s": c["relative_speed_km_s"],
            "risk_level": c["risk_level"],
            "linear_estimate_miss_km": c["screening"]["linear_estimate_miss_km"],
        }

    params = report["parameters"]
    return {
        "window_start_utc": report["window"]["start_utc"],
        "window_hours": params["propagation"]["window_hours"],
        "step_seconds": report["window"]["step_seconds"],
        "groups": list(params["groups"]),
        "threshold_km": params["screening"]["threshold_km"],
        "objects_screened": report["scope"]["objects_screened"],
        "by_risk_level": report["summary"]["by_risk_level"],
        "pairs_within_search_radius": report["summary"]["screening"]["pairs_within_search_radius"],
        "conjunctions": sorted(
            (rec(c) for c in report["conjunctions"]),
            key=lambda x: (x["norad_a"], x["norad_b"], x["tca_utc"]),
        ),
        "co_located_pairs": sorted(
            (
                {
                    "norad_a": p["object_a"]["norad_id"],
                    "norad_b": p["object_b"]["norad_id"],
                    "min_separation_km": p["min_separation_km"],
                    "samples_within_threshold": p["samples_within_threshold"],
                }
                for p in report["co_located_pairs"]
            ),
            key=lambda x: (x["norad_a"], x["norad_b"]),
        ),
    }


def _by_pair(records: list[dict[str, Any]]) -> dict[tuple[int, int], list[dict[str, Any]]]:
    out: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for r in records:
        out.setdefault((r["norad_a"], r["norad_b"]), []).append(r)
    return out


def _tca(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


@pytest.fixture
def expected() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(EXPECTED_PATH.read_text())
    return data


def test_default_scope_matches_known_good_baseline(
    expected: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    for gz in SNAPSHOT_DIR.glob("*.json.gz"):
        (cache_dir / gz.name.removesuffix(".gz")).write_bytes(gzip.decompress(gz.read_bytes()))

    # fetch_tle_data builds a client up front even when every response is cached, so allow the
    # client but fail any request it actually makes.
    def refuse(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"regression test must not hit the network: {request.url}")

    real_client = httpx.Client
    monkeypatch.setattr(
        "app.data.celestrak_client.httpx.Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(refuse), **kwargs),
    )

    # Scope/window/threshold are pinned from the baseline; everything else (risk bands, stale-epoch
    # cutoff, max relative speed) comes from config, so changing those deliberately fails this test.
    base = load_settings(REPO_ROOT / "config" / "screening.yaml").with_overrides(
        groups=expected["groups"],
        window_hours=expected["window_hours"],
        step_seconds=expected["step_seconds"],
        threshold_km=expected["threshold_km"],
    )
    settings = replace(
        base,
        source=replace(base.source, cache_dir=str(cache_dir), cache_ttl_hours=1e9),
        report_dir=str(tmp_path / "reports"),
    )
    out = run_screening(
        settings,
        config=Config(tracing_disabled=True),
        window_start=_tca(expected["window_start_utc"]),
    )
    actual = canonicalize(out.report)

    assert actual["objects_screened"] == expected["objects_screened"]
    assert actual["pairs_within_search_radius"] == expected["pairs_within_search_radius"]
    assert actual["by_risk_level"] == expected["by_risk_level"]
    assert len(actual["conjunctions"]) == len(expected["conjunctions"])

    exp_pairs, act_pairs = _by_pair(expected["conjunctions"]), _by_pair(actual["conjunctions"])
    assert act_pairs.keys() == exp_pairs.keys()
    for pair, exp_events in exp_pairs.items():
        act_events = act_pairs[pair]
        assert len(act_events) == len(exp_events), pair
        for e, a in zip(exp_events, act_events, strict=True):
            assert a["risk_level"] == e["risk_level"], pair
            dt = abs((_tca(a["tca_utc"]) - _tca(e["tca_utc"])).total_seconds())
            assert dt < TCA_TOLERANCE_S, (pair, dt)
            for key in ("miss_distance_km", "relative_speed_km_s", "linear_estimate_miss_km"):
                assert abs(a[key] - e[key]) < KM_TOLERANCE, (pair, key, a[key], e[key])

    assert [(p["norad_a"], p["norad_b"]) for p in actual["co_located_pairs"]] == [
        (p["norad_a"], p["norad_b"]) for p in expected["co_located_pairs"]
    ]


if __name__ == "__main__":
    # Deliberate baseline regeneration only - see README.md. Usage:
    #   uv run python tests/regression/test_default_scope_parity.py <report.json>
    report = json.loads(Path(sys.argv[1]).read_text())
    EXPECTED_PATH.write_text(json.dumps(canonicalize(report), indent=1) + "\n")
    print(f"wrote {EXPECTED_PATH}")
