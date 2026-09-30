"""Build the frozen synthetic scenarios the screening evals run on (deliberate regeneration only).

    uv run python -m evals.build_fixtures

Each scenario is a tiny catalog of circular LEO element sets engineered so that specific pairs pass
through specific points at specific times: a between-sample crossing at a known miss, a sub-1 km
pass that should rate `high`, a pair just outside the threshold, and so on. Each object is placed by
a small Newton solve on real SGP4 (mean anomaly, RAAN and mean motion adjusted until SGP4 puts it
within 1 m of its target point at its target time), so the geometry holds under the same dynamics
the screener uses.

The output goes to `evals/fixtures/<scenario>/` as CelesTrak cache files (`gp-<group>.json`,
`satcat-<group>.json`), which the eval runner serves to the real pipeline through its normal fetch
path, plus a `scenario.json` recording what each scenario was designed to show. The designed misses
are targets, not the expected answer: the expected answer is whatever the dense-sampling oracle
(`evals/oracle.py`) computes at eval time.

The fixtures are committed. Like eval cases, regenerate them only deliberately and in their own
commit, never to make a failing eval pass (see evals/README.md).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from sgp4 import omm
from sgp4.api import Satrec

from app.propagation.sgp4_propagator import _jday

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
WINDOW_START = datetime(2026, 10, 1, tzinfo=UTC)
FETCHED_AT = WINDOW_START - timedelta(hours=1)
# Elements a few hours old, like a fresh CelesTrak pull.
FRESH_EPOCH = WINDOW_START - timedelta(hours=6)
EARTH_RADIUS_KM = 6378.137
MU_KM3_S2 = 398600.4418
ALTITUDE_KM = 780.0  # the Iridium NEXT / Fengyun-1C shell the default demo scope screens

ACTIVE = ("PAY", "+")
DEBRIS = ("DEB", "")
NO_SATCAT = None


@dataclass
class Obj:
    norad_id: int
    name: str
    satcat: tuple[str, str] | None
    # Where (TEME km) and when (seconds after WINDOW_START) SGP4 must put this object.
    target_km: np.ndarray
    target_s: float
    inclination_deg: float
    descending: bool = False
    epoch: datetime = FRESH_EPOCH


@dataclass
class Scenario:
    name: str
    purpose: str
    objects: list[Obj]
    designed: list[dict[str, Any]] = field(default_factory=list)
    # Extra records copied from another object's solved elements (e.g. a co-located twin).
    clones: list[tuple[int, int, str, tuple[str, str] | None, float]] = field(default_factory=list)


def unit(lat_deg: float, lon_deg: float) -> np.ndarray:
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    return np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)])


def point(lat_deg: float, lon_deg: float) -> np.ndarray:
    return unit(lat_deg, lon_deg) * (EARTH_RADIUS_KM + ALTITUDE_KM)


def plane_through(p: np.ndarray, inc_deg: float, descending: bool) -> tuple[float, float]:
    """RAAN and argument of latitude (deg) of a circular orbit at `inc_deg` passing through `p`."""
    i = math.radians(inc_deg)
    px, py, pz = p / np.linalg.norm(p)
    rho, lam = math.hypot(px, py), math.atan2(py, px)
    s = -pz / (math.tan(i) * rho)
    if abs(s) > 1:
        raise ValueError(
            f"inclination {inc_deg} can't reach latitude {math.degrees(math.asin(pz))}"
        )
    raan = lam + (math.pi - math.asin(s) if descending else math.asin(s))
    node = np.array([math.cos(raan), math.sin(raan), 0.0])
    h = np.array([math.sin(raan) * math.sin(i), -math.cos(raan) * math.sin(i), math.cos(i)])
    u = math.atan2(float(np.dot(p, np.cross(h, node))), float(np.dot(p, node)))
    return math.degrees(raan) % 360, math.degrees(u) % 360


def omm_record(o: Obj, mean_anomaly: float, raan: float, mean_motion: float) -> dict[str, Any]:
    return {
        "OBJECT_NAME": o.name,
        "OBJECT_ID": f"2099-{o.norad_id % 1000:03d}A",
        "EPOCH": o.epoch.strftime("%Y-%m-%dT%H:%M:%S.%f"),
        "MEAN_MOTION": round(mean_motion, 10),
        "ECCENTRICITY": 0.0001,
        "INCLINATION": o.inclination_deg,
        "RA_OF_ASC_NODE": round(raan % 360, 10),
        "ARG_OF_PERICENTER": 0.0,
        "MEAN_ANOMALY": round(mean_anomaly % 360, 10),
        "EPHEMERIS_TYPE": 0,
        "CLASSIFICATION_TYPE": "U",
        "NORAD_CAT_ID": o.norad_id,
        "ELEMENT_SET_NO": 999,
        "REV_AT_EPOCH": 1000,
        "BSTAR": 0.0,
        "MEAN_MOTION_DOT": 0.0,
        "MEAN_MOTION_DDOT": 0.0,
    }


def state(rec: dict[str, Any], t: datetime) -> tuple[np.ndarray, np.ndarray]:
    sat = Satrec()
    omm.initialize(sat, {k: str(v) for k, v in rec.items()})
    jd, fr = _jday(t)
    err, r, v = sat.sgp4(jd, fr)
    if err:
        raise RuntimeError(f"SGP4 error {err}")
    return np.asarray(r), np.asarray(v)


def position(rec: dict[str, Any], t: datetime) -> np.ndarray:
    return state(rec, t)[0]


def raan_and_arglat(r: np.ndarray, v: np.ndarray) -> tuple[float, float]:
    h = np.cross(r, v)
    raan = math.atan2(h[0], -h[1])
    node = np.array([math.cos(raan), math.sin(raan), 0.0])
    u = math.atan2(float(np.dot(r, np.cross(h / np.linalg.norm(h), node))), float(np.dot(r, node)))
    return math.degrees(raan), math.degrees(u)


def solve(o: Obj) -> dict[str, Any]:
    """Place `o` at its target with SGP4, to within 1 m.

    A Keplerian first guess drifts by thousands of km over a long arc (SGP4's secular J2 rates move
    the mean anomaly and node), so first correct RAAN and argument of latitude from the propagated
    state until the object is in the right plane near the right spot, then Newton on (mean anomaly,
    RAAN, mean motion) to close the last few km, including the radial offset.
    """
    raan, u = plane_through(o.target_km, o.inclination_deg, o.descending)
    a = EARTH_RADIUS_KM + ALTITUDE_KM
    n_rad_s = math.sqrt(MU_KM3_S2 / a**3)
    t = WINDOW_START + timedelta(seconds=o.target_s)
    dt = (t - o.epoch).total_seconds()
    x = np.array(
        [math.degrees(math.radians(u) - n_rad_s * dt), raan, n_rad_s * 86400 / (2 * math.pi)]
    )
    for _ in range(20):
        r, v = state(omm_record(o, *x), t)
        if np.linalg.norm(r - o.target_km) < 10.0:
            break
        raan_act, u_act = raan_and_arglat(r, v)
        x[0] += (u - u_act + 180) % 360 - 180
        x[1] += (raan - raan_act + 180) % 360 - 180
    steps = np.array([1e-4, 1e-4, 1e-7])
    for _ in range(30):
        f = position(omm_record(o, *x), t) - o.target_km
        if np.linalg.norm(f) < 1e-3:
            return omm_record(o, *x)
        jac = np.column_stack(
            [
                (position(omm_record(o, *(x + np.eye(3)[c] * steps[c])), t) - o.target_km - f)
                / steps[c]
                for c in range(3)
            ]
        )
        x = x - np.linalg.solve(jac, f)
    raise RuntimeError(f"placement did not converge for {o.norad_id}: {np.linalg.norm(f):.4f} km")


def above(p: np.ndarray, km: float) -> np.ndarray:
    """`p` raised `km` radially. Two orbits crossing at a point both move horizontally there, so
    their relative velocity is horizontal too, and a radial offset is the one that sets the miss
    distance rather than just shifting the time of closest approach."""
    raised: np.ndarray = p * (1 + km / np.linalg.norm(p))
    return raised


def pair(
    base_id: int,
    names: tuple[str, str],
    types: tuple[tuple[str, str] | None, tuple[str, str] | None],
    p: np.ndarray,
    t_s: float,
    miss_km: float,
    incs: tuple[float, float],
    descending: tuple[bool, bool] = (False, True),
) -> list[Obj]:
    """Two objects over `p` at `t_s`, the second `miss_km` higher than the first."""
    b_target = above(p, miss_km)
    return [
        Obj(base_id, names[0], types[0], p, t_s, incs[0], descending[0]),
        Obj(base_id + 1, names[1], types[1], b_target, t_s, incs[1], descending[1]),
    ]


def scenarios() -> list[Scenario]:
    rng = np.random.default_rng(20261001)
    out: list[Scenario] = []

    # T = 2h17m37s: 37 s past a 60 s sample, so neither neighboring sample is anywhere near 5 km.
    out.append(
        Scenario(
            "between-samples-crossing",
            "Active payload vs debris, 2.0 km miss at a TCA 37 s past a sample. A sample-only "
            "distance check misses it; the screener must find it and rate it moderate "
            "(active payload, miss under 2.5 km).",
            pair(
                91001,
                ("SYN ACTIVE A", "SYN DEBRIS B"),
                (ACTIVE, DEBRIS),
                point(20, 30),
                8257.0,
                2.0,
                (86.4, 98.9),
            ),
            [{"pair": [91001, 91002], "t_s": 8257.0, "miss_km": 2.0}],
        )
    )
    out.append(
        Scenario(
            "high-tier-hypervelocity",
            "Active payload vs debris, 0.4 km miss at hypervelocity. The default demo scope has "
            "never produced a live `high`; this exercises that path end to end.",
            pair(
                91011,
                ("SYN ACTIVE A", "SYN DEBRIS B"),
                (ACTIVE, DEBRIS),
                point(-35, 140),
                13333.0,
                0.4,
                (86.4, 98.9),
            ),
            [{"pair": [91011, 91012], "t_s": 13333.0, "miss_km": 0.4}],
        )
    )
    out.append(
        Scenario(
            "debris-debris-subkm",
            "Debris vs debris, 0.6 km miss at hypervelocity: sub-1 km but no active payload, so "
            "moderate, not high.",
            pair(
                91021,
                ("SYN DEBRIS A", "SYN DEBRIS B"),
                (DEBRIS, DEBRIS),
                point(10, -80),
                5000.5,
                0.6,
                (82.0, 98.9),
            ),
            [{"pair": [91021, 91022], "t_s": 5000.5, "miss_km": 0.6}],
        )
    )
    out.append(
        Scenario(
            "missing-satcat-counts-as-active",
            "Debris vs an object with no SATCAT record, 0.5 km miss at hypervelocity. Unknown "
            "status counts as possibly active (ADR 0004), so this rates high where the "
            "debris-debris scenario rates moderate.",
            pair(
                91031,
                ("SYN DEBRIS A", "SYN UNKNOWN B"),
                (DEBRIS, NO_SATCAT),
                point(45, 60),
                15021.0,
                0.5,
                (86.4, 98.9),
            ),
            [{"pair": [91031, 91032], "t_s": 15021.0, "miss_km": 0.5}],
        )
    )
    out.append(
        Scenario(
            "threshold-edges",
            "Two debris pairs either side of the 5 km threshold: 4.7 km (flagged, low) and 5.3 km "
            "(not flagged). Same-altitude pairs meet again half an orbit (~50 min) later at a "
            "drifted miss that can fall under 5 km, so the designed passes are 5 minutes apart "
            "and this scenario's case uses a short window (00:40-01:16Z) that excludes the "
            "re-encounters.",
            pair(
                91041,
                ("SYN DEBRIS A", "SYN DEBRIS B"),
                (DEBRIS, DEBRIS),
                point(0, 0),
                3601.0,
                4.7,
                (86.4, 98.9),
            )
            + pair(
                91043,
                ("SYN DEBRIS C", "SYN DEBRIS D"),
                (DEBRIS, DEBRIS),
                point(-20, 100),
                3903.0,
                5.3,
                (86.4, 98.9),
            ),
            [
                {"pair": [91041, 91042], "t_s": 3601.0, "miss_km": 4.7},
                {"pair": [91043, 91044], "t_s": 3903.0, "miss_km": 5.3},
            ],
        )
    )
    out.append(
        Scenario(
            "slow-crossing",
            "Two active payloads crossing at a shallow angle (headings about 4 degrees apart at "
            "60N): a 0.5 km miss at about 0.5 km/s. Sub-1 km with an active payload, but below "
            "hypervelocity, so moderate. Still a crossing, not co-located.",
            pair(
                91051,
                ("SYN ACTIVE A", "SYN ACTIVE B"),
                (ACTIVE, ACTIVE),
                point(60, 20),
                7777.0,
                0.5,
                (86.4, 84.4),
                (False, False),
            ),
            [{"pair": [91051, 91052], "t_s": 7777.0, "miss_km": 0.5}],
        )
    )
    co = Scenario(
        "co-located-and-stale",
        "An active payload with a twin 0.3 km ahead in the same orbit (co-located: reported "
        "separately, never risk-rated), plus a debris object on a 1 km crossing with it whose "
        "elements are 20 days old (must be dropped as stale, so no conjunction).",
        [
            Obj(91061, "SYN ACTIVE A", ACTIVE, point(-50, -120), 12000.0, 86.4),
            Obj(
                91063,
                "SYN STALE DEBRIS",
                DEBRIS,
                above(point(-50, -120), 1.0),
                12000.0,
                98.9,
                True,
                WINDOW_START - timedelta(days=20),
            ),
        ],
        [
            {"pair": [91061, 91062], "co_located": True, "separation_km": 0.3},
            {"pair": [91061, 91063], "t_s": 12000.0, "miss_km": 1.0, "stale_days": 20},
        ],
        clones=[(91062, 91061, "SYN ACTIVE A TWIN", ACTIVE, 0.3)],
    )
    out.append(co)
    out.append(
        Scenario(
            "window-edges",
            "Debris crossings 25 s after the window opens and 25 s before it closes, each 1.5 km. "
            "Both must be found; neither may be extrapolated past the window.",
            pair(
                91071,
                ("SYN DEBRIS A", "SYN DEBRIS B"),
                (DEBRIS, DEBRIS),
                point(30, -150),
                25.0,
                1.5,
                (86.4, 98.9),
            )
            + pair(
                91073,
                ("SYN DEBRIS C", "SYN DEBRIS D"),
                (DEBRIS, DEBRIS),
                point(-5, 70),
                6 * 3600 - 25.0,
                1.5,
                (86.4, 98.9),
            ),
            [
                {"pair": [91071, 91072], "t_s": 25.0, "miss_km": 1.5},
                {"pair": [91073, 91074], "t_s": 6 * 3600 - 25.0, "miss_km": 1.5},
            ],
        )
    )

    # Crowd: 40 objects through 4 hubs, 10 per hub, each within ~3 km of its hub center at nearly
    # the same instant, from random planes. Dozens of pairs pass under 5 km at arbitrary sub-sample
    # times, plus their re-encounters half an orbit later. The oracle is the only source of truth.
    crowd: list[Obj] = []
    hub_times = [2417.3, 7019.8, 12780.1, 18763.6]
    types = [ACTIVE, DEBRIS, DEBRIS, ("R/B", ""), NO_SATCAT]
    for h, t_hub in enumerate(hub_times):
        center = point(float(rng.uniform(-40, 40)), float(rng.uniform(-180, 180)))
        lat = abs(math.degrees(math.asin(center[2] / np.linalg.norm(center))))
        for k in range(10):
            nid = 92000 + h * 10 + k
            v = rng.normal(size=3)
            target = center + v / np.linalg.norm(v) * rng.uniform(0, 3.0)
            crowd.append(
                Obj(
                    nid,
                    f"SYN CROWD {h}-{k}",
                    types[int(rng.integers(len(types)))],
                    target,
                    t_hub + float(rng.uniform(-0.2, 0.2)),
                    float(rng.uniform(max(lat + 2, 45.0), 110.0)),
                    bool(rng.integers(2)),
                )
            )
    out.append(
        Scenario(
            "crowd-oracle",
            "40 objects converging on 4 hubs from random planes. No hand-picked expectations: "
            "every sub-threshold encounter the dense oracle finds must be found by the screener, "
            "and nothing else.",
            crowd,
        )
    )
    return out


def build(s: Scenario) -> None:
    group = f"eval-{s.name}"
    gp = [solve(o) for o in s.objects]
    by_id = {r["NORAD_CAT_ID"]: r for r in gp}
    satcat_types = {o.norad_id: o.satcat for o in s.objects}
    for new_id, src_id, name, clone_type, ahead_km in s.clones:
        rec = dict(by_id[src_id])
        # A circular orbit's mean anomaly moves the object along-track by (angle x radius).
        rec["MEAN_ANOMALY"] = round(
            (rec["MEAN_ANOMALY"] + math.degrees(ahead_km / (EARTH_RADIUS_KM + ALTITUDE_KM))) % 360,
            10,
        )
        rec.update(OBJECT_NAME=name, NORAD_CAT_ID=new_id, OBJECT_ID=f"2099-{new_id % 1000:03d}A")
        gp.append(rec)
        satcat_types[new_id] = clone_type
    gp.sort(key=lambda r: r["NORAD_CAT_ID"])
    satcat = [
        {
            "OBJECT_NAME": r["OBJECT_NAME"],
            "OBJECT_ID": r["OBJECT_ID"],
            "NORAD_CAT_ID": r["NORAD_CAT_ID"],
            "OBJECT_TYPE": satcat_types[r["NORAD_CAT_ID"]][0],  # type: ignore[index]
            "OPS_STATUS_CODE": satcat_types[r["NORAD_CAT_ID"]][1],  # type: ignore[index]
        }
        for r in gp
        if satcat_types[r["NORAD_CAT_ID"]] is not None
    ]
    out = FIXTURES_DIR / s.name
    out.mkdir(parents=True, exist_ok=True)
    stamp = FETCHED_AT.isoformat()
    (out / f"gp-{group}.json").write_text(
        json.dumps({"fetched_at": stamp, "payload": gp}, indent=1) + "\n"
    )
    (out / f"satcat-{group}.json").write_text(
        json.dumps({"fetched_at": stamp, "payload": satcat}, indent=1) + "\n"
    )
    meta = {
        "scenario": s.name,
        "group": group,
        "window_start_utc": WINDOW_START.isoformat().replace("+00:00", "Z"),
        "purpose": s.purpose,
        "designed": s.designed,
    }
    (out / "scenario.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"{s.name}: {len(gp)} objects -> {out}")


def main() -> int:
    for s in scenarios():
        build(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
