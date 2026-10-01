"""Screening eval runner: frozen inputs in, per-case pass/fail out.

    python -m evals.run --tier fast|standard|nightly

Exits non-zero if thresholds in evals/thresholds.yaml are missed, so CI can gate on it.

Each case in `cases/*.jsonl` runs the real pipeline (`run_screening`: fetch -> propagate -> screen
-> assess -> report) on a frozen input served from a temporary CelesTrak cache, with the network
blocked. Two kinds of input:

- **Synthetic scenarios** (`evals/fixtures/<name>/`, built by `evals/build_fixtures.py`): tiny
  engineered catalogs with a known geometry. With `"oracle": true`, the screener's output is also
  compared with an independent brute-force oracle (`evals/oracle.py`): every encounter under
  threshold that dense 1 s SGP4 sampling finds must be reported, at the same TCA and miss distance,
  and nothing else may be. That's the correctness check: the oracle shares none of the screener's
  search radius, KD-tree or straight-line logic.
- **The frozen real-data snapshot** (`tests/regression/default_scope_snapshot/`): named encounters
  and facts from the default demo scope. Too big for the oracle; these pin specific, human-checked
  behaviors, so a change that moves them shows *which* behavior moved. (The parity test in
  `tests/regression/` is the all-or-nothing version: any change at all fails it.)

This pipeline makes no LLM calls, so `APP_LLM_MODE` has no effect here and every case costs $0.
Cost is still reported, so a future LLM step (and its spend) would show up without a harness change.
Latency is the pipeline's own wall-clock for the case, not the oracle's.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest import mock

import httpx
import yaml

from app.config import Config, load_env
from app.conjunction_pipeline import run_screening
from app.data.celestrak_client import fetch_tle_data
from app.settings import load_settings
from evals.oracle import run_oracle

EVALS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALS_DIR.parent
TIER_SIZES: dict[str, int | None] = {"fast": 15, "standard": 50, "nightly": None}
# Oracle agreement tolerances. The screener's refinement converges to ~1e-3 s and the report rounds
# distances to 4 decimals, so real disagreement is orders of magnitude larger than these.
TCA_MATCH_S = 0.5
MISS_TOLERANCE_KM = 1e-3
# An oracle event this close to the threshold may legitimately land either side of it in the
# screener (rounding, refinement tolerance), so it's neither required nor forbidden.
THRESHOLD_BAND_KM = 1e-3


def load_cases(tier: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted((EVALS_DIR / "cases").glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                cases.append(json.loads(line))
    limit = TIER_SIZES[tier]
    return cases if limit is None else cases[:limit]


def _parse_utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


@contextmanager
def frozen_cache(fixture: Path) -> Iterator[Path]:
    """Copy a fixture's cache files (plain or gzipped) into a temp dir and block the network."""

    def refuse(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"evals must not hit the network: {request.url}")

    real_client = httpx.Client
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp) / "cache"
        cache.mkdir()
        for f in fixture.iterdir():
            if f.name.endswith(".json.gz"):
                (cache / f.name.removesuffix(".gz")).write_bytes(gzip.decompress(f.read_bytes()))
            elif f.name.startswith(("gp-", "satcat-")) and f.suffix == ".json":
                (cache / f.name).write_bytes(f.read_bytes())
        with mock.patch(
            "app.data.celestrak_client.httpx.Client",
            lambda **kw: real_client(transport=httpx.MockTransport(refuse), **kw),
        ):
            yield Path(tmp)


def _pair(rec: dict[str, Any]) -> tuple[int, int]:
    a, b = rec["object_a"]["norad_id"], rec["object_b"]["norad_id"]
    return (a, b) if a < b else (b, a)


def check_expectations(report: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if (
        "objects_screened" in expect
        and report["scope"]["objects_screened"] != expect["objects_screened"]
    ):
        fails.append(
            f"objects_screened {report['scope']['objects_screened']} "
            f"!= {expect['objects_screened']}"
        )
    if "by_risk_level" in expect and report["summary"]["by_risk_level"] != expect["by_risk_level"]:
        fails.append(
            f"by_risk_level {report['summary']['by_risk_level']} != {expect['by_risk_level']}"
        )

    by_pair: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for c in report["conjunctions"]:
        by_pair.setdefault(_pair(c), []).append(c)
    for e in expect.get("encounters", []):
        pair = (e["pair"][0], e["pair"][1])
        events = by_pair.get(pair, [])
        if not events:
            fails.append(f"expected encounter {pair} not reported")
            continue
        closest = min(events, key=lambda c: c["miss_distance_km"])
        if "risk_level" in e and closest["risk_level"] != e["risk_level"]:
            fails.append(
                f"{pair} closest pass rated {closest['risk_level']}, expected {e['risk_level']}"
            )
        if "miss_km" in e:
            lo, hi = e["miss_km"]
            if not lo <= closest["miss_distance_km"] <= hi:
                fails.append(
                    f"{pair} closest miss {closest['miss_distance_km']} km not in [{lo}, {hi}]"
                )
        if "events" in e and len(events) != e["events"]:
            fails.append(f"{pair} has {len(events)} events, expected {e['events']}")
        if "satcat_owners" in e:
            # Ordered like `pair` (lower NORAD id first), whichever side the report put it on.
            by_id = {
                closest[s]["norad_id"]: closest[s].get("satcat_owner")
                for s in ("object_a", "object_b")
            }
            owners = [(by_id[n] or {}).get("code") for n in pair]
            if owners != e["satcat_owners"]:
                fails.append(f"{pair} satcat_owner codes {owners}, expected {e['satcat_owners']}")
    for a, b in expect.get("absent_pairs", []):
        if (a, b) in by_pair:
            fails.append(f"pair {(a, b)} reported but should not be")

    if "co_located_pairs" in expect:
        got = sorted([list(_pair(p)) for p in report["co_located_pairs"]])
        if got != sorted(expect["co_located_pairs"]):
            fails.append(f"co_located_pairs {got} != {sorted(expect['co_located_pairs'])}")
    dropped = {(d["norad_id"], d["reason"]) for d in report["scope"]["dropped"]}
    for d in expect.get("dropped", []):
        if (d["norad_id"], d["reason"]) not in dropped:
            fails.append(f"expected {d['norad_id']} dropped as {d['reason']}")
    if "dropped_count" in expect and len(dropped) != expect["dropped_count"]:
        fails.append(f"dropped {len(dropped)} objects, expected {expect['dropped_count']}")
    return fails


def check_oracle(
    report: dict[str, Any], objects: list[Any], settings: Any, window_start: datetime
) -> tuple[list[str], dict[str, Any]]:
    """Compare the report's encounters with the dense oracle's. Returns (failures, stats)."""
    threshold = settings.screening.threshold_km
    oracle = run_oracle(
        objects,
        window_start=window_start,
        window_hours=settings.propagation.window_hours,
        threshold_km=threshold,
        co_located_max_relative_speed_km_s=settings.screening.co_located_max_relative_speed_km_s,
        max_epoch_age_days=settings.source.max_epoch_age_days,
    )
    fails: list[str] = []
    reported = [
        {
            "pair": _pair(c),
            "t": (_parse_utc(c["tca_utc"]) - window_start).total_seconds(),
            "miss": c["miss_distance_km"],
        }
        for c in report["conjunctions"]
    ]
    unmatched = list(range(len(reported)))
    matched = required = 0
    max_miss_err = max_tca_err = 0.0
    for ev in oracle.events:
        pair = (ev.norad_a, ev.norad_b)
        hit = next(
            (
                i
                for i in unmatched
                if reported[i]["pair"] == pair
                and abs(reported[i]["t"] - ev.tca_offset_s) < TCA_MATCH_S
            ),
            None,
        )
        borderline = ev.miss_km >= threshold - THRESHOLD_BAND_KM
        if hit is None:
            if not borderline:
                required += 1
                fails.append(
                    f"missed oracle encounter {pair} "
                    f"at +{ev.tca_offset_s:.2f} s, {ev.miss_km:.4f} km"
                )
            continue
        unmatched.remove(hit)
        if not borderline:
            required += 1
        matched += 1
        miss_err = abs(reported[hit]["miss"] - ev.miss_km)
        tca_err = abs(reported[hit]["t"] - ev.tca_offset_s)
        max_miss_err, max_tca_err = max(max_miss_err, miss_err), max(max_tca_err, tca_err)
        if miss_err > MISS_TOLERANCE_KM:
            fails.append(f"{pair} miss {reported[hit]['miss']} km vs oracle {ev.miss_km:.4f} km")
    for i in unmatched:
        r = reported[i]
        if r["miss"] < threshold - THRESHOLD_BAND_KM:
            fails.append(f"reported {r['pair']} at +{r['t']:.2f} s ({r['miss']} km) not in oracle")
    got_co = {_pair(p) for p in report["co_located_pairs"]}
    if got_co != oracle.co_located_pairs:
        fails.append(
            f"co-located pairs {sorted(got_co)} != oracle {sorted(oracle.co_located_pairs)}"
        )
    stats = {
        "oracle_events": len(oracle.events),
        "oracle_events_required": required,
        "oracle_events_matched": matched,
        "max_miss_error_km": round(max_miss_err, 6),
        "max_tca_error_s": round(max_tca_err, 4),
    }
    return fails, stats


def score_case(case: dict[str, Any], config: Config) -> dict[str, Any]:
    fixture = REPO_ROOT / case["fixture"]
    window_start = _parse_utc(case["window_start_utc"])
    result: dict[str, Any] = {"id": case["id"], "category": case.get("category", "default")}
    fails: list[str] = []
    latency = 0.0
    try:
        with frozen_cache(fixture) as tmp:
            base = load_settings(REPO_ROOT / "config" / "screening.yaml").with_overrides(
                groups=case["groups"],
                window_hours=case.get("window_hours"),
                step_seconds=case.get("step_seconds"),
                threshold_km=case.get("threshold_km"),
            )
            settings = replace(
                base,
                source=replace(base.source, cache_dir=str(tmp / "cache"), cache_ttl_hours=1e9),
                report_dir=str(tmp / "reports"),
            )
            start = time.perf_counter()
            out = run_screening(settings, config=config, window_start=window_start)
            latency = time.perf_counter() - start
            report = out.report
            fails += check_expectations(report, case.get("expect", {}))
            if case.get("oracle"):
                tle_set, _ = fetch_tle_data(settings.groups, settings.source)
                oracle_fails, stats = check_oracle(report, tle_set.objects, settings, window_start)
                fails += oracle_fails
                result["oracle"] = stats
                min_events = case.get("expect", {}).get("min_oracle_events")
                if min_events is not None and stats["oracle_events"] < min_events:
                    fails.append(
                        f"oracle found {stats['oracle_events']} events, "
                        f"scenario needs >= {min_events}"
                    )
        result["conjunctions"] = report["summary"]["conjunctions_flagged"]
        result["by_risk_level"] = report["summary"]["by_risk_level"]
    except Exception as exc:  # a crash is a failed case, not a crashed eval run
        fails.append(f"error: {exc!r}")
    result.update(
        passed=not fails,
        failures=fails,
        latency_s=round(latency, 4),
        # No LLM calls anywhere in the pipeline.
        cost_usd=0.0,
    )
    return result


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", choices=list(TIER_SIZES), default="fast")
    args = parser.parse_args()
    load_env()
    config = Config.from_env()
    print(
        "screening evals: frozen inputs, no network, no LLM calls "
        f"(APP_LLM_MODE={config.llm_mode} has no effect)",
        file=sys.stderr,
    )

    thresholds = yaml.safe_load((EVALS_DIR / "thresholds.yaml").read_text())
    cases = load_cases(args.tier)
    if not cases:
        print("No eval cases found.", file=sys.stderr)
        return 1

    # Sequential on purpose: each case is CPU-bound (propagation, KD-tree, oracle), and running
    # them one at a time keeps the per-case latency numbers meaningful.
    results = []
    for case in cases:
        r = score_case(case, config)
        status = "PASS" if r["passed"] else "FAIL"
        print(f"{status} {r['id']} ({r['latency_s']:.2f} s)", file=sys.stderr)
        for f in r["failures"]:
            print(f"    {f}", file=sys.stderr)
        results.append(r)

    pass_rate = sum(r["passed"] for r in results) / len(results)
    latency_p95 = p95([r["latency_s"] for r in results])
    total_cost = sum(r["cost_usd"] for r in results)
    mean_cost = total_cost / len(results)
    oracle_stats = [r["oracle"] for r in results if "oracle" in r]
    required = sum(s["oracle_events_required"] for s in oracle_stats)
    matched = sum(s["oracle_events_matched"] for s in oracle_stats)
    missed = sum(
        1 for r in results for f in r["failures"] if f.startswith("missed oracle encounter")
    )

    summary = {
        "tier": args.tier,
        "n_cases": len(results),
        "pass_rate": round(pass_rate, 4),
        "latency_p95_s": round(latency_p95, 4),
        "mean_cost_usd": round(mean_cost, 4),
        "total_cost_usd": round(total_cost, 4),
        "oracle_cases": len(oracle_stats),
        "oracle_events": sum(s["oracle_events"] for s in oracle_stats),
        "oracle_matched": matched,
        "oracle_recall": round((required - missed) / required, 4) if required else None,
        "max_miss_error_km": max((s["max_miss_error_km"] for s in oracle_stats), default=None),
        "max_tca_error_s": max((s["max_tca_error_s"] for s in oracle_stats), default=None),
    }

    failures = []
    if pass_rate < thresholds["min_pass_rate"]:
        failures.append(f"pass_rate {pass_rate:.2%} < {thresholds['min_pass_rate']:.2%}")
    if latency_p95 > thresholds["max_latency_p95_s"]:
        failures.append(f"latency_p95 {latency_p95:.2f}s > {thresholds['max_latency_p95_s']}s")
    if mean_cost > thresholds["max_mean_cost_usd"]:
        failures.append(f"mean_cost ${mean_cost:.3f} > ${thresholds['max_mean_cost_usd']}")
    max_total = thresholds.get("max_total_cost_usd")
    if max_total is not None and total_cost > max_total:
        failures.append(f"total_cost ${total_cost:.3f} > ${max_total} (this run's aggregate spend)")

    report_dir = EVALS_DIR / "reports"
    report_dir.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (report_dir / f"{args.tier}-{stamp}.json").write_text(
        json.dumps({"summary": summary, "failures": failures, "results": results}, indent=2)
    )

    print(json.dumps(summary, indent=2))
    for f in failures:
        print(f"FAIL: {f}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
