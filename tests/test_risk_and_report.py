from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from app.data.models import CatalogObject
from app.propagation.sgp4_propagator import PropagationResult
from app.reporting.report_builder import AssessedConjunction, build_report, write_report
from app.risk.risk_model import assess_risk
from app.screening.conjunction_screen import CoLocatedPair, Conjunction
from app.settings import RiskSettings, Settings
from conftest import gp_record, objects_from

RISK = RiskSettings(high_miss_km=1.0, moderate_miss_km_active=2.5, hypervelocity_km_s=1.0)


def _obj(object_type: str | None, status: str | None, norad_id: int) -> CatalogObject:
    (base,) = objects_from([gp_record(NORAD_CAT_ID=norad_id)])
    return replace(base, object_type=object_type, ops_status=status)


ACTIVE = _obj("PAY", "+", 1)
DEAD_PAYLOAD = _obj("PAY", "-", 2)
DEBRIS = _obj("DEB", "", 3)
UNKNOWN = _obj(None, None, 4)


@pytest.mark.parametrize(
    ("miss", "speed", "a", "b", "level"),
    [
        (0.5, 14.0, ACTIVE, DEBRIS, "high"),
        (0.5, 0.5, ACTIVE, DEBRIS, "moderate"),  # slow closing speed
        (0.5, 14.0, DEBRIS, DEAD_PAYLOAD, "moderate"),  # nothing active to protect
        (2.0, 14.0, ACTIVE, DEBRIS, "moderate"),
        (2.0, 14.0, DEBRIS, DEBRIS, "low"),
        (4.0, 14.0, ACTIVE, DEBRIS, "low"),
        (0.5, 14.0, UNKNOWN, DEBRIS, "high"),  # unknown status treated as possibly active
    ],
)
def test_risk_table(
    miss: float, speed: float, a: CatalogObject, b: CatalogObject, level: str
) -> None:
    assert assess_risk(miss, speed, a, b, RISK).level == level


def test_report_shape_sorting_and_serialization(tmp_path: Path) -> None:
    objects = [ACTIVE, DEBRIS, DEAD_PAYLOAD]
    offsets = np.arange(0.0, 120.1, 60.0)
    prop = PropagationResult(
        objects=objects,
        satrecs=[],
        window_start=datetime(2026, 9, 27, 6, tzinfo=UTC),
        offsets_s=offsets,
        positions=np.zeros((3, 3, 3)),
        velocities=np.zeros((3, 3, 3)),
    )
    low = Conjunction(1, 2, 30.0, 4.0, 14.0, 4.0, 30.0)
    high = Conjunction(0, 1, 90.5, 0.3, 14.0, 0.3, 90.4)
    assessed = [
        AssessedConjunction(c, assess_risk(c.miss_distance_km, 14.0, *pair, RISK))
        for c, pair in [(low, (DEBRIS, DEAD_PAYLOAD)), (high, (ACTIVE, DEBRIS))]
    ]
    settings = Settings()
    report = build_report(
        run_id="test-run",
        generated_at=prop.window_start,
        settings=settings.to_dict(),
        prop=prop,
        assessed=assessed,
        co_located=[CoLocatedPair(0, 2, 0.0, 0.0, 3)],
        fetch_stats={"objects": 3},
        screen_stats={},
        timings_s={"propagate_orbits": 1.0},
    )
    assert [c["risk_level"] for c in report["conjunctions"]] == ["high", "low"]
    top = report["conjunctions"][0]
    assert top["tca_utc"] == "2026-09-27T06:01:30.500000Z"
    assert top["object_a"]["active_payload"] is True
    assert top["object_b"]["object_type"] == "DEB"
    assert report["summary"]["by_risk_level"] == {"high": 1, "moderate": 0, "low": 1}
    assert report["co_located_pairs"][0]["samples_within_threshold"] == 3
    assert report["window"]["end_utc"] == "2026-09-27T06:02:00Z"

    path = write_report(report, tmp_path)
    assert json.loads(path.read_text())["run_id"] == "test-run"
