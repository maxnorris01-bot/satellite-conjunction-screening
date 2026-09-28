"""Structured JSON report: the MVP's user-facing output.

`REPORT_SCHEMA_VERSION` should be bumped on any breaking change to the report's shape - records or
summary/diagnostic fields - since the later `generate_summary` upgrade will read it as a contract.
v2: `summary.screening` replaced `pair_checks`/`pairs_per_timestep` with
`all_pairs_per_timestep`/`neighbor_search` (KD-tree fine filter); conjunction records unchanged.
v3: `summary.screening` added `phase_timings_s`, `mean_pairs_within_radius_per_timestep`,
`max_pairs_within_radius_in_a_timestep` and `refined_events` (additive; Step B instrumentation).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.data.models import CatalogObject
from app.propagation.sgp4_propagator import PropagationResult
from app.risk.risk_model import RISK_ORDER, RiskAssessment
from app.screening.conjunction_screen import CoLocatedPair, Conjunction

REPORT_SCHEMA_VERSION = 3
LIMITATIONS = (
    "Risk levels are a documented heuristic over miss distance, closing speed and object status "
    "(ADR 0004), not a probability of collision: public GP/TLE data carries no covariance. Typical "
    "SGP4/TLE position error for fresh LEO elements is on the order of 1 km and grows with element "
    "age, so miss distances here are screening estimates, not operational-grade predictions."
)


@dataclass(frozen=True)
class AssessedConjunction:
    conjunction: Conjunction
    risk: RiskAssessment


def _iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


def _object_record(obj: CatalogObject, at: datetime) -> dict[str, Any]:
    return {
        "norad_id": obj.norad_id,
        "name": obj.name,
        "international_designator": obj.object_id,
        "object_type": obj.object_type,
        "ops_status": obj.ops_status,
        "active_payload": obj.is_active,
        "source": obj.source,
        "source_groups": list(obj.groups),
        "element_epoch_utc": _iso(obj.epoch),
        "element_age_at_tca_days": round((at - obj.epoch).total_seconds() / 86400.0, 3),
    }


def build_report(
    *,
    run_id: str,
    generated_at: datetime,
    settings: dict[str, Any],
    prop: PropagationResult,
    assessed: list[AssessedConjunction],
    co_located: list[CoLocatedPair],
    fetch_stats: dict[str, Any],
    screen_stats: dict[str, Any],
    timings_s: dict[str, float],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for item in assessed:
        c = item.conjunction
        tca = prop.time_at(c.tca_offset_s)
        records.append(
            {
                "risk_level": item.risk.level,
                "risk_reason": item.risk.reason,
                "tca_utc": _iso(tca),
                "miss_distance_km": round(c.miss_distance_km, 4),
                "relative_speed_km_s": round(c.relative_speed_km_s, 4),
                "object_a": _object_record(prop.objects[c.index_a], tca),
                "object_b": _object_record(prop.objects[c.index_b], tca),
                "screening": {
                    "linear_estimate_miss_km": round(c.linear_miss_km, 4),
                    "linear_estimate_tca_utc": _iso(prop.time_at(c.linear_tca_offset_s)),
                },
            }
        )
    records.sort(key=lambda r: (RISK_ORDER[r["risk_level"]], r["miss_distance_km"]))

    co_records = [
        {
            "object_a": {
                "norad_id": prop.objects[p.index_a].norad_id,
                "name": prop.objects[p.index_a].name,
            },
            "object_b": {
                "norad_id": prop.objects[p.index_b].norad_id,
                "name": prop.objects[p.index_b].name,
            },
            "min_separation_km": round(p.min_separation_km, 4),
            "max_relative_speed_km_s": round(p.max_relative_speed_km_s, 5),
            "samples_within_threshold": p.samples_within_threshold,
        }
        for p in co_located
    ]

    by_risk = {level: 0 for level in RISK_ORDER}
    for r in records:
        by_risk[r["risk_level"]] += 1
    window_end = prop.time_at(float(prop.offsets_s[-1]))
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at_utc": _iso(generated_at),
        "window": {
            "start_utc": _iso(prop.window_start),
            "end_utc": _iso(window_end),
            "step_seconds": prop.step_s,
            "frame": "TEME",
        },
        "parameters": settings,
        "scope": {
            "groups": list(settings["groups"]),
            "objects_fetched": fetch_stats.get("objects"),
            "objects_screened": len(prop.objects),
            "dropped": prop.dropped,
            "fetch": fetch_stats,
        },
        "summary": {
            "conjunctions_flagged": len(records),
            "by_risk_level": by_risk,
            "co_located_pairs": len(co_records),
            "screening": screen_stats,
            "timings_s": timings_s,
        },
        "limitations": LIMITATIONS,
        "conjunctions": records,
        "co_located_pairs": co_records,
    }


def write_report(report: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{report['run_id']}.json"
    path.write_text(json.dumps(report, indent=2, default=str) + "\n")
    return path
