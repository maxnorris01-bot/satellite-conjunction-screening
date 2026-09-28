"""`screen_conjunctions`: per-timestep KD-tree neighbor search (ADR 0003's fine filter).

At each sample, a `cKDTree` over all positions returns the pairs within the search radius directly,
instead of computing the full n x n distance matrix and filtering it (session 1's naive version).
The results are identical; only the cost changes: roughly O(n log n + neighbors) per timestep
instead of O(n^2), with no O(n^2) pair-index arrays in memory. ADR 0003's coarse orbital-regime
filter is not implemented yet.

Why not just check `distance < threshold` at each sample: LEO closing speeds reach ~15 km/s, so at
a 60 s step two objects move ~900 km relative to each other between samples, and a 5 km pass
almost always falls between samples. Instead, for each sample k:

1. Keep pairs within `threshold + max_relative_speed * step / 2` - the farthest apart two objects
   can be at a sample and still come within `threshold` in the half-step either side of it.
2. For those, assume straight-line relative motion over that half-step and compute the linear time
   and distance of closest approach (relative acceleration between two nearby objects is tiny, so
   this is accurate over +/-30 s).
3. Linear misses under `threshold` become candidate events; each is then refined by re-propagating
   just that pair with SGP4 and minimizing the true separation around the linear estimate.

Pairs that stay slow relative to each other (docked vehicles, station modules) are separated out as
co-located rather than reported as crossing encounters.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.spatial import cKDTree

from app.propagation.sgp4_propagator import PropagationResult
from app.settings import ScreeningSettings


@dataclass(frozen=True)
class Conjunction:
    """One close approach between two objects (indices into `PropagationResult.objects`)."""

    index_a: int
    index_b: int
    tca_offset_s: float
    miss_distance_km: float
    relative_speed_km_s: float
    # The straight-line estimate before SGP4 refinement, kept so refinement error is inspectable.
    linear_miss_km: float
    linear_tca_offset_s: float


@dataclass(frozen=True)
class CoLocatedPair:
    index_a: int
    index_b: int
    min_separation_km: float
    max_relative_speed_km_s: float
    samples_within_threshold: int


@dataclass
class ScreeningResult:
    conjunctions: list[Conjunction]
    co_located: list[CoLocatedPair]
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class _Hit:
    k: int
    t_offset: float
    miss: float
    speed: float


def screen_conjunctions(prop: PropagationResult, settings: ScreeningSettings) -> ScreeningResult:
    n, n_steps, _ = prop.positions.shape
    threshold = settings.threshold_km
    step = prop.step_s
    search_radius = threshold + settings.max_relative_speed_km_s * step / 2.0
    half = step / 2.0

    hits: dict[tuple[int, int], list[_Hit]] = defaultdict(list)
    pairs_within_radius = 0
    max_pairs_in_step = 0
    # Phase timers (instrumentation only): tree build + radius query; then the per-timestep
    # closest-approach math on the tree's survivors; then per-pair event splitting + refinement.
    search_s = survivor_s = 0.0
    for k in range(n_steps):
        t0 = time.perf_counter()
        pos = prop.positions[:, k, :]
        # (m, 2) array of index pairs with i < j - the same orientation the all-pairs version used,
        # so dr/dv below carry the same signs. query_pairs uses `<= r` where the old filter used
        # `< r`. The only pair that could differ sits exactly on the radius, and it can close by at
        # most `max_relative_speed * step / 2` - to exactly `threshold`, which `miss < threshold`
        # below rejects - so it can never produce a hit either way.
        near = cKDTree(pos).query_pairs(search_radius, output_type="ndarray")
        t1 = time.perf_counter()
        search_s += t1 - t0
        if near.shape[0] == 0:
            continue
        pairs_within_radius += int(near.shape[0])
        max_pairs_in_step = max(max_pairs_in_step, int(near.shape[0]))
        i, j = near[:, 0], near[:, 1]
        dr = pos[i] - pos[j]
        dv = prop.velocities[i, k, :] - prop.velocities[j, k, :]
        vv = np.einsum("ij,ij->i", dv, dv)
        t = -np.einsum("ij,ij->i", dr, dv) / np.maximum(vv, 1e-18)
        # Each sample owns the half-step either side of it, clipped to the window's edges, so
        # consecutive samples tile the window without gaps or double coverage.
        lo = -half if k > 0 else 0.0
        hi = half if k < n_steps - 1 else 0.0
        t = np.clip(t, lo, hi)
        miss = np.linalg.norm(dr + dv * t[:, None], axis=1)
        for idx in np.flatnonzero(miss < threshold):
            hits[(int(i[idx]), int(j[idx]))].append(
                _Hit(k, float(t[idx]), float(miss[idx]), float(np.sqrt(vv[idx])))
            )
        survivor_s += time.perf_counter() - t1

    t_refine = time.perf_counter()
    refined_events = 0
    conjunctions: list[Conjunction] = []
    co_located: list[CoLocatedPair] = []
    rejected_after_refinement = 0
    for (a, b), pair_hits in sorted(hits.items()):
        max_speed = max(h.speed for h in pair_hits)
        if max_speed < settings.co_located_max_relative_speed_km_s:
            co_located.append(
                CoLocatedPair(a, b, min(h.miss for h in pair_hits), max_speed, len(pair_hits))
            )
            continue
        for event in _split_events(pair_hits):
            best = min(event, key=lambda h: h.miss)
            linear_tca = float(prop.offsets_s[best.k]) + best.t_offset
            refined_events += 1
            tca, miss, speed = _refine(prop, a, b, linear_tca, step)
            if miss >= threshold:
                rejected_after_refinement += 1
                continue
            conjunctions.append(Conjunction(a, b, tca, miss, speed, best.miss, linear_tca))
    refine_s = time.perf_counter() - t_refine

    stats = {
        "objects": n,
        "timesteps": n_steps,
        "neighbor_search": "cKDTree.query_pairs",
        # The naive problem size, kept for comparison: pairs an all-pairs check would examine.
        "all_pairs_per_timestep": n * (n - 1) // 2,
        "search_radius_km": round(search_radius, 3),
        "pairs_within_search_radius": pairs_within_radius,
        "mean_pairs_within_radius_per_timestep": round(pairs_within_radius / max(n_steps, 1), 1),
        "max_pairs_within_radius_in_a_timestep": max_pairs_in_step,
        "candidate_pairs": len(hits),
        "refined_events": refined_events,
        "conjunctions": len(conjunctions),
        "co_located_pairs": len(co_located),
        "rejected_after_refinement": rejected_after_refinement,
        "phase_timings_s": {
            "neighbor_search": round(search_s, 4),
            "survivor_closest_approach": round(survivor_s, 4),
            "event_refinement": round(refine_s, 4),
        },
    }
    return ScreeningResult(conjunctions, co_located, stats)


def _split_events(pair_hits: list[_Hit]) -> list[list[_Hit]]:
    """Group a pair's hits into separate encounters: consecutive samples are one encounter."""
    pair_hits = sorted(pair_hits, key=lambda h: h.k)
    events: list[list[_Hit]] = [[pair_hits[0]]]
    for h in pair_hits[1:]:
        if h.k - events[-1][-1].k <= 1:
            events[-1].append(h)
        else:
            events.append([h])
    return events


def _refine(
    prop: PropagationResult, a: int, b: int, linear_tca: float, step: float
) -> tuple[float, float, float]:
    """Minimize true SGP4 separation within one step either side of the linear estimate."""
    window_end = float(prop.offsets_s[-1])
    lo, hi = max(0.0, linear_tca - step), min(window_end, linear_tca + step)

    def separation(t: float) -> float:
        ra, _ = prop.state_at(a, t)
        rb, _ = prop.state_at(b, t)
        return float(np.linalg.norm(ra - rb))

    if hi <= lo:
        tca = lo
    else:
        res = minimize_scalar(
            separation, bounds=(lo, hi), method="bounded", options={"xatol": 1e-3}
        )
        tca = float(res.x)
    ra, va = prop.state_at(a, tca)
    rb, vb = prop.state_at(b, tca)
    return tca, float(np.linalg.norm(ra - rb)), float(np.linalg.norm(va - vb))
