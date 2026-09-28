"""Command-line entry point.

uv run python -m app.cli                                  # scope/window/threshold from config
uv run python -m app.cli --groups stations --window-hours 48 --threshold-km 10
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.config import Config, load_env
from app.conjunction_pipeline import run_screening
from app.settings import DEFAULT_SETTINGS_PATH, load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Screen CelesTrak groups for close approaches.")
    parser.add_argument("--config", type=Path, default=DEFAULT_SETTINGS_PATH)
    parser.add_argument("--groups", nargs="+", help="CelesTrak group names (overrides config)")
    parser.add_argument("--window-hours", type=float)
    parser.add_argument("--step-seconds", type=float)
    parser.add_argument("--threshold-km", type=float)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    load_env()
    settings = load_settings(args.config).with_overrides(
        groups=args.groups,
        window_hours=args.window_hours,
        step_seconds=args.step_seconds,
        threshold_km=args.threshold_km,
    )
    out = run_screening(settings, config=Config.from_env())
    summary = out.report["summary"]
    print(f"report: {out.report_path}")
    print(
        f"objects screened: {out.report['scope']['objects_screened']} "
        f"(fetched {out.report['scope']['objects_fetched']}, "
        f"dropped {len(out.report['scope']['dropped'])})"
    )
    print(f"conjunctions flagged: {summary['conjunctions_flagged']} {summary['by_risk_level']}")
    print(f"co-located pairs (not rated): {summary['co_located_pairs']}")
    print("timings (s): " + ", ".join(f"{k}={v}" for k, v in out.timings_s.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
