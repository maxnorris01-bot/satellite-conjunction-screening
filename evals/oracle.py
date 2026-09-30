"""Independent closest-approach oracle for the synthetic eval scenarios.

The screener finds encounters with a 60 s sample grid, a KD-tree radius search, a straight-line
closest-approach estimate between samples and a bounded SGP4 refinement (see
`app.screening.conjunction_screen`). This oracle shares none of that: it propagates every object
with raw SGP4 on a dense 1 s grid, checks every pair at every sample, and refines each local minimum
of the sampled separation. It's brute force, so only usable on small synthetic catalogs (tens of
objects, hours of window). That's the point: it's slow enough to be obviously right.

Why 1 s is dense enough: the true minimum lies within 1 s of the sampled minimum, and two Earth
orbiters close at most ~16 km/s, so any encounter under `threshold` shows up as a sampled local
minimum under `threshold + 16 km`. Every such minimum is refined by a bounded scalar minimization
of the true SGP4 separation over +/-1 s.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
from scipy.optimize import minimize_scalar
from sgp4.api import SatrecArray

from app.data.models import CatalogObject
from app.propagation.sgp4_propagator import SECONDS_PER_DAY, _jday, build_satrec

GRID_S = 1.0
MAX_CLOSING_KM_S = 16.0


@dataclass(frozen=True)
class OracleEvent:
    norad_a: int
    norad_b: int
    tca_offset_s: float
    miss_km: float
    relative_speed_km_s: float


@dataclass
class OracleResult:
    # Crossing encounters under threshold (pairs that are not co-located), sorted by pair then TCA.
    events: list[OracleEvent]
    # Pairs whose every sub-threshold minimum is slower than the co-location speed.
    co_located_pairs: set[tuple[int, int]]
    # Objects the oracle excluded, with the reason: the same stale-epoch rule the spec defines,
    # applied here independently, plus any SGP4 error inside the window.
    excluded: dict[int, str]


def run_oracle(
    objects: list[CatalogObject],
    *,
    window_start: datetime,
    window_hours: float,
    threshold_km: float,
    co_located_max_relative_speed_km_s: float,
    max_epoch_age_days: float,
) -> OracleResult:
    excluded: dict[int, str] = {}
    kept = []
    for obj in objects:
        age_days = (window_start - obj.epoch).total_seconds() / SECONDS_PER_DAY
        if age_days > max_epoch_age_days:
            excluded[obj.norad_id] = "stale_epoch"
        else:
            kept.append(obj)
    kept.sort(key=lambda o: o.norad_id)
    satrecs = [build_satrec(o) for o in kept]

    window_s = window_hours * 3600.0
    offsets = np.arange(0.0, window_s + GRID_S / 2, GRID_S)
    jd0, fr0 = _jday(window_start)
    err, r, _ = SatrecArray(satrecs).sgp4(
        np.full(len(offsets), jd0), fr0 + offsets / SECONDS_PER_DAY
    )
    ok = ~err.any(axis=1)
    for bad in np.flatnonzero(~ok):
        excluded[kept[bad].norad_id] = "sgp4_error"
    idx = [int(i) for i in np.flatnonzero(ok)]

    def state(i: int, t: float) -> tuple[np.ndarray, np.ndarray]:
        e, rr, vv = satrecs[i].sgp4(jd0, fr0 + t / SECONDS_PER_DAY)
        if e:
            raise RuntimeError(f"SGP4 error {e} for {kept[i].norad_id}")
        return np.asarray(rr), np.asarray(vv)

    cutoff = threshold_km + MAX_CLOSING_KM_S * GRID_S
    by_pair: dict[tuple[int, int], list[OracleEvent]] = {}
    for n, i in enumerate(idx):
        for j in idx[n + 1 :]:
            d = np.linalg.norm(r[i] - r[j], axis=1)
            left = np.r_[np.inf, d[:-1]]
            right = np.r_[d[1:], np.inf]
            for k in np.flatnonzero((d <= left) & (d < right) & (d < cutoff)):
                lo, hi = max(0.0, offsets[k] - GRID_S), min(window_s, offsets[k] + GRID_S)

                def sep(t: float, i: int = i, j: int = j) -> float:
                    return float(np.linalg.norm(state(i, t)[0] - state(j, t)[0]))

                res = minimize_scalar(
                    sep, bounds=(lo, hi), method="bounded", options={"xatol": 1e-5}
                )
                tca = float(res.x)
                ra, va = state(i, tca)
                rb, vb = state(j, tca)
                miss = float(np.linalg.norm(ra - rb))
                if miss < threshold_km:
                    a, b = kept[i].norad_id, kept[j].norad_id
                    by_pair.setdefault((a, b), []).append(
                        OracleEvent(a, b, tca, miss, float(np.linalg.norm(va - vb)))
                    )

    events: list[OracleEvent] = []
    co_located: set[tuple[int, int]] = set()
    for pair, pair_events in sorted(by_pair.items()):
        if max(e.relative_speed_km_s for e in pair_events) < co_located_max_relative_speed_km_s:
            co_located.add(pair)
        else:
            events.extend(sorted(pair_events, key=lambda e: e.tca_offset_s))
    return OracleResult(events, co_located, excluded)
