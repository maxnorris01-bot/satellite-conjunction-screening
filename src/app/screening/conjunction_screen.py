"""`screen_conjunctions`: naive all-pairs screening (session 1).

ADR 0003's coarse filter + per-timestep KD-tree replaces the all-pairs distance matrix once scope
grows; the function signature and output types are meant to stay the same when it does.

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

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.spatial.distance import pdist

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
    iu, ju = np.triu_indices(n, k=1)
    half = step / 2.0

    hits: dict[tuple[int, int], list[_Hit]] = defaultdict(list)
    pairs_within_radius = 0
    for k in range(n_steps):
        pos = prop.positions[:, k, :]
        near = np.flatnonzero(pdist(pos) < search_radius)
        if near.size == 0:
            continue
        pairs_within_radius += int(near.size)
        i, j = iu[near], ju[near]
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
            tca, miss, speed = _refine(prop, a, b, linear_tca, step)
            if miss >= threshold:
                rejected_after_refinement += 1
                continue
            conjunctions.append(Conjunction(a, b, tca, miss, speed, best.miss, linear_tca))

    stats = {
        "objects": n,
        "timesteps": n_steps,
        "pairs_per_timestep": int(iu.size),
        "pair_checks": int(iu.size) * n_steps,
        "search_radius_km": round(search_radius, 3),
        "pairs_within_search_radius": pairs_within_radius,
        "candidate_pairs": len(hits),
        "conjunctions": len(conjunctions),
        "co_located_pairs": len(co_located),
        "rejected_after_refinement": rejected_after_refinement,
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
