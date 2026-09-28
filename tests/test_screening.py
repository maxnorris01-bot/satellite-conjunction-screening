"""Screening against synthetic straight-line trajectories with a known closest approach.

Straight lines make the true TCA and miss distance exact, so these tests check the screening
geometry itself (between-sample detection, event splitting, co-location), independent of SGP4.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
from numpy.typing import NDArray

from app.propagation.sgp4_propagator import PropagationResult
from app.screening.conjunction_screen import screen_conjunctions
from app.settings import ScreeningSettings

Vec = NDArray[np.float64]


class LinearPropagation(PropagationResult):
    """Objects moving in straight lines: r(t) = r0 + v * t."""

    def __init__(self, r0: Vec, v: Vec, window_s: float, step_s: float) -> None:
        offsets = np.arange(0.0, window_s + step_s / 2, step_s)
        positions = r0[:, None, :] + v[:, None, :] * offsets[None, :, None]
        velocities = np.repeat(v[:, None, :], len(offsets), axis=1)
        super().__init__(
            objects=[],
            satrecs=[],
            window_start=datetime(2026, 9, 27, tzinfo=UTC),
            offsets_s=offsets,
            positions=positions,
            velocities=velocities,
        )
        self._r0, self._v = r0, v

    def state_at(self, index: int, offset_s: float) -> tuple[Vec, Vec]:
        return self._r0[index] + self._v[index] * offset_s, self._v[index]


def crossing_pair(tca: float, miss_km: float, speed: float = 7.5) -> tuple[Vec, Vec]:
    """A along +x, B along +y, both at (0, 0) at `tca` except B is offset `miss_km` in z."""
    va = np.array([speed, 0.0, 0.0])
    vb = np.array([0.0, speed, 0.0])
    r0 = np.array([-va * tca, -vb * tca + np.array([0.0, 0.0, miss_km])])
    return r0, np.array([va, vb])


SETTINGS = ScreeningSettings(threshold_km=5.0, max_relative_speed_km_s=16.0)


def test_encounter_between_samples_is_found_with_exact_tca_and_miss() -> None:
    # TCA 17 s after a sample: at the nearest samples the pair is ~180 km and ~450 km apart, so a
    # sample-only `distance < 5 km` check would miss it entirely.
    r0, v = crossing_pair(tca=3617.0, miss_km=2.0)
    prop = LinearPropagation(r0, v, window_s=7200, step_s=60)
    sampled = np.linalg.norm(prop.positions[0] - prop.positions[1], axis=1)
    assert sampled.min() > 100

    result = screen_conjunctions(prop, SETTINGS)
    assert len(result.conjunctions) == 1
    c = result.conjunctions[0]
    assert abs(c.tca_offset_s - 3617.0) < 0.01
    assert abs(c.miss_distance_km - 2.0) < 1e-3
    assert abs(c.relative_speed_km_s - 7.5 * np.sqrt(2)) < 1e-6
    assert not result.co_located


def test_pass_outside_threshold_is_not_flagged() -> None:
    r0, v = crossing_pair(tca=3617.0, miss_km=6.0)
    result = screen_conjunctions(LinearPropagation(r0, v, 7200, 60), SETTINGS)
    assert result.conjunctions == []
    assert result.stats["candidate_pairs"] == 0


def test_slow_pairs_are_co_located_not_conjunctions() -> None:
    # B starts 1 km ahead and closes at 1 m/s: within 1 km for the whole 10-minute window.
    r0 = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    v = np.array([[7.5, 0.0, 0.0], [7.499, 0.0, 0.0]])
    result = screen_conjunctions(LinearPropagation(r0, v, 600, 60), SETTINGS)
    assert result.conjunctions == []
    assert len(result.co_located) == 1
    assert result.co_located[0].samples_within_threshold == 11


def test_encounters_at_the_window_edges_are_not_extrapolated_past_it() -> None:
    # True TCA 10 s before the window starts: only the in-window part of the pass counts.
    r0, v = crossing_pair(tca=-10.0, miss_km=0.5)
    result = screen_conjunctions(LinearPropagation(r0, v, 600, 60), SETTINGS)
    assert result.conjunctions == []  # at t=0 they're already ~106 km apart


def test_many_objects_match_an_exact_closest_approach_oracle() -> None:
    """Guards the neighbor search: every pair that truly comes within threshold must be found.

    120 objects fly straight lines through six small "hubs" at nearly the same instant from random
    directions, so hundreds of pairs pass within 5 km at arbitrary sub-sample times (including 5 s
    from each window edge). For straight lines each pair's closest approach within the window is
    exact, so any pair the KD-tree failed to return would show up as a missing encounter.
    """
    rng = np.random.default_rng(7)
    n, window = 120, 3600.0
    d = rng.normal(size=(n, 3))
    v = d / np.linalg.norm(d, axis=1)[:, None] * rng.uniform(1, 7.5, (n, 1))
    hub = rng.integers(0, 6, n)
    hub_pos = rng.uniform(-3000, 3000, (6, 3))
    hub_t = np.array([5.0, 700.0, 1333.0, 2000.0, 2917.0, 3595.0])
    t_pass = hub_t[hub] + rng.uniform(-1, 1, n)
    r0 = hub_pos[hub] + rng.normal(scale=4, size=(n, 3)) - v * t_pass[:, None]

    expected: dict[tuple[int, int], tuple[float, float]] = {}
    for i in range(n):
        for j in range(i + 1, n):
            dr, dv = r0[i] - r0[j], v[i] - v[j]
            t = float(np.clip(-(dr @ dv) / (dv @ dv), 0.0, window))
            miss = float(np.linalg.norm(dr + dv * t))
            if miss < SETTINGS.threshold_km:
                expected[(i, j)] = (t, miss)

    result = screen_conjunctions(LinearPropagation(r0, v, window, 60), SETTINGS)
    found = {
        (c.index_a, c.index_b): (c.tca_offset_s, c.miss_distance_km) for c in result.conjunctions
    }
    assert len(expected) > 300
    assert found.keys() == expected.keys()
    for pair, (t, miss) in expected.items():
        assert abs(found[pair][0] - t) < 0.01
        assert abs(found[pair][1] - miss) < 1e-4
