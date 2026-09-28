"""Session 2 Step B: one-off scaling measurement at `active` + Fengyun-1C scope.

    uv run python scripts/scaling_spike.py

The first run fetches CelesTrak's `active` and `fengyun-1c-debris` groups (GP + SATCAT) exactly
once into `cache/scaling-spike/` and pins the window start in a manifest. Every later run is served
from that frozen copy with network access blocked, so repeated timing runs never re-pull the large
`active` feed and all measure identical inputs. The snapshot is gitignored and never committed.
Re-freezing (deleting `cache/scaling-spike/`) is a deliberate, separate step that produces a new
measurement: see scripts/README.md, which also records the snapshot behind ADR 0007's numbers.

This never touches `config/screening.yaml`'s demo scope: groups, cache dir and report dir are
overridden here only. Each invocation is one pipeline run in a fresh process, so
`ru_maxrss` is a clean per-run peak; run it several times for repeat timings.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

import app.data.celestrak_client as celestrak_client
from app.config import Config
from app.conjunction_pipeline import run_screening
from app.settings import load_settings

GROUPS = ["active", "fengyun-1c-debris"]
FREEZE_DIR = Path("cache/scaling-spike")
MANIFEST = FREEZE_DIR / "manifest.json"
OUT_DIR = Path("runs/scaling-spike")


def swapouts() -> int | None:
    """macOS cumulative swap-out page count (to detect timings distorted by swapping)."""
    if sys.platform != "darwin":
        return None
    out = subprocess.run(["vm_stat"], capture_output=True, text=True, check=False).stdout
    m = re.search(r"Swapouts:\s+(\d+)", out)
    return int(m.group(1)) if m else None


def block_network() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise RuntimeError(f"frozen snapshot must not hit the network: {request.url}")

    real_client = httpx.Client
    celestrak_client.httpx.Client = lambda **kw: real_client(
        transport=httpx.MockTransport(refuse), **kw
    )


def raw_group_counts() -> dict[str, dict[str, int]]:
    """Independent count of what CelesTrak listed, straight from the frozen raw responses."""
    counts: dict[str, dict[str, int]] = {}
    for group in GROUPS:
        gp = json.loads((FREEZE_DIR / f"gp-{group}.json").read_text())["payload"]
        sc = json.loads((FREEZE_DIR / f"satcat-{group}.json").read_text())["payload"]
        counts[group] = {
            "gp_records": len(gp),
            "gp_unique_norad_ids": len({r.get("NORAD_CAT_ID") for r in gp}),
            "satcat_records": len(sc),
            "satcat_on_orbit": sum(1 for r in sc if not r.get("DECAY_DATE")),
        }
    return counts


def main() -> int:
    frozen = MANIFEST.exists()
    if frozen:
        manifest = json.loads(MANIFEST.read_text())
        block_network()
        ttl_hours = 1e9
    else:
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        manifest = {"frozen_at_utc": now.isoformat(), "window_start_utc": now.isoformat()}
        ttl_hours = load_settings().source.cache_ttl_hours

    base = load_settings().with_overrides(groups=GROUPS)
    settings = replace(
        base,
        source=replace(base.source, cache_dir=str(FREEZE_DIR), cache_ttl_hours=ttl_hours),
        report_dir=str(OUT_DIR / "reports"),
    )
    swap_before = swapouts()
    out = run_screening(
        settings,
        config=Config(tracing_disabled=False),
        window_start=datetime.fromisoformat(manifest["window_start_utc"]),
    )
    swap_after = swapouts()
    if not frozen:
        MANIFEST.write_text(json.dumps(manifest, indent=1) + "\n")

    r = out.report
    scr = r["summary"]["screening"]
    fetch = r["scope"]["fetch"]
    dropped = r["scope"]["dropped"]
    result: dict[str, Any] = {
        "run_id": r["run_id"],
        "frozen_snapshot": manifest,
        "served_from_frozen_snapshot": frozen,
        "groups": GROUPS,
        "window": r["window"],
        "objects_fetched_merged": r["scope"]["objects_fetched"],
        "objects_screened": r["scope"]["objects_screened"],
        "timings_s": {
            "propagate_orbits": out.timings_s["propagate_orbits"],
            **scr["phase_timings_s"],
            "screen_conjunctions_total": out.timings_s["screen_conjunctions"],
            "pipeline_total": out.timings_s["total"],
        },
        "peak_rss_mb": out.peak_rss_mb,
        "swapouts_during_run": (
            None if swap_before is None or swap_after is None else swap_after - swap_before
        ),
        "screening": scr,
        "summary": {
            "conjunctions": r["summary"]["conjunctions_flagged"],
            "by_risk_level": r["summary"]["by_risk_level"],
            "co_located_pairs": r["summary"]["co_located_pairs"],
        },
        "sanity": {
            "raw_listing": raw_group_counts(),
            "fetch_per_group": fetch["groups"],
            "parse_failures": fetch["parse_failures"],
            "missing_satcat": fetch["missing_satcat"],
            "dropped_by_reason": dict(Counter(d["reason"] for d in dropped)),
            "sgp4_error_codes": dict(
                Counter(f"{d['error_code']}: {d['error']}" for d in dropped if "error_code" in d)
            ),
            "sgp4_dropped_examples": [d for d in dropped if d["reason"] == "sgp4_error"][:10],
            "conjunction_object_types": dict(
                Counter(
                    "-".join(
                        sorted(
                            (
                                c["object_a"]["object_type"] or "?",
                                c["object_b"]["object_type"] or "?",
                            )
                        )
                    )
                    for c in r["conjunctions"]
                )
            ),
            "conjunctions_with_active_payload": sum(
                1
                for c in r["conjunctions"]
                if c["object_a"]["active_payload"] or c["object_b"]["active_payload"]
            ),
            "closest_miss_km": min(
                (c["miss_distance_km"] for c in r["conjunctions"]), default=None
            ),
            "high_risk_examples": [
                {k: c[k] for k in ("tca_utc", "miss_distance_km", "relative_speed_km_s")}
                | {"a": c["object_a"]["name"], "b": c["object_b"]["name"]}
                for c in r["conjunctions"]
                if c["risk_level"] == "high"
            ][:10],
        },
        "report_path": str(out.report_path),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{r['run_id']}-spike.json"
    path.write_text(json.dumps(result, indent=1, default=str) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "run_id",
                    "served_from_frozen_snapshot",
                    "objects_fetched_merged",
                    "objects_screened",
                    "timings_s",
                    "peak_rss_mb",
                    "swapouts_during_run",
                    "summary",
                )
            },
            indent=1,
        )
    )
    print(f"full result: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
