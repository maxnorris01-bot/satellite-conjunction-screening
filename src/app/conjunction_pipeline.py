"""End-to-end screening run: fetch -> propagate -> screen -> assess -> report. Zero LLM calls.

Every step runs inside an `app.tracing.span`, so each run appends one JSON line per step (duration,
counts, `run_id`) to `runs/trace.jsonl` - the raw material for any later performance investigation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import Config
from app.data.celestrak_client import fetch_tle_data
from app.propagation.sgp4_propagator import propagate_orbits
from app.reporting.report_builder import AssessedConjunction, build_report, write_report
from app.risk.risk_model import assess_risk
from app.screening.conjunction_screen import screen_conjunctions
from app.settings import Settings
from app.tracing import span


@dataclass(frozen=True)
class RunOutput:
    report: dict[str, Any]
    report_path: Path
    # Includes write_report and total, which the report file itself can't contain.
    timings_s: dict[str, float]


def run_screening(
    settings: Settings,
    *,
    config: Config | None = None,
    window_start: datetime | None = None,
) -> RunOutput:
    cfg = config or Config.from_env()
    now = datetime.now(UTC)
    # Start the window on a whole minute so repeated runs line up and reports read cleanly.
    start = window_start or now.replace(second=0, microsecond=0)
    run_id = f"{start:%Y%m%dT%H%MZ}-{uuid.uuid4().hex[:6]}"
    timings: dict[str, float] = {}

    with span("pipeline.run_screening", config=cfg, run_id=run_id) as run_rec:
        with span("fetch_tle_data", config=cfg, run_id=run_id, groups=settings.groups) as rec:
            tle_set, fetch_stats = fetch_tle_data(settings.groups, settings.source)
            rec.update(fetch_stats)
        timings["fetch_tle_data"] = rec["duration_s"]

        with span("propagate_orbits", config=cfg, run_id=run_id) as rec:
            prop, prop_stats = propagate_orbits(
                tle_set,
                window_start=start,
                window_hours=settings.propagation.window_hours,
                step_s=settings.propagation.step_seconds,
                max_epoch_age_days=settings.source.max_epoch_age_days,
            )
            rec.update(prop_stats)
        timings["propagate_orbits"] = rec["duration_s"]

        with span("screen_conjunctions", config=cfg, run_id=run_id) as rec:
            screened = screen_conjunctions(prop, settings.screening)
            rec.update(screened.stats)
        timings["screen_conjunctions"] = rec["duration_s"]

        with span("assess_risk", config=cfg, run_id=run_id) as rec:
            assessed = [
                AssessedConjunction(
                    c,
                    assess_risk(
                        c.miss_distance_km,
                        c.relative_speed_km_s,
                        prop.objects[c.index_a],
                        prop.objects[c.index_b],
                        settings.risk,
                    ),
                )
                for c in screened.conjunctions
            ]
            rec["assessed"] = len(assessed)
            rec["by_risk_level"] = {
                lvl: sum(1 for a in assessed if a.risk.level == lvl)
                for lvl in ("high", "moderate", "low")
            }
        timings["assess_risk"] = rec["duration_s"]

        with span("write_report", config=cfg, run_id=run_id) as rec:
            report = build_report(
                run_id=run_id,
                generated_at=now,
                settings=settings.to_dict(),
                prop=prop,
                assessed=assessed,
                co_located=screened.co_located,
                fetch_stats=fetch_stats,
                screen_stats=screened.stats,
                timings_s=dict(timings),
            )
            path = write_report(report, Path(settings.report_dir))
            rec["path"] = str(path)
            rec["conjunctions"] = len(report["conjunctions"])
        timings["write_report"] = rec["duration_s"]
        run_rec["report_path"] = str(path)
        run_rec["conjunctions"] = len(report["conjunctions"])
    timings["total"] = run_rec["duration_s"]
    return RunOutput(report, path, timings)
