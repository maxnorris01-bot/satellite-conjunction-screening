from __future__ import annotations

from datetime import timedelta

import numpy as np

from app.data.models import TleSet
from app.propagation.sgp4_propagator import propagate_orbits
from conftest import ISS_EPOCH, gp_record, objects_from


def _tle_set(records: list[dict[str, object]]) -> TleSet:
    return TleSet(objects_from(records), "test", ("test",), ISS_EPOCH)


def test_iss_propagates_to_a_physically_sane_orbit() -> None:
    prop, stats = propagate_orbits(
        _tle_set([gp_record()]),
        window_start=ISS_EPOCH + timedelta(hours=1),
        window_hours=2,
        step_s=60,
    )
    assert prop.positions.shape == (1, 121, 3)
    radius = np.linalg.norm(prop.positions[0], axis=1)
    speed = np.linalg.norm(prop.velocities[0], axis=1)
    # ~415-425 km altitude on a 6378 km Earth; ~7.66 km/s orbital speed.
    assert np.all((radius > 6780) & (radius < 6815))
    assert np.all((speed > 7.6) & (speed < 7.7))
    assert stats["timesteps"] == 121 and stats["dropped"] == {}


def test_state_at_matches_the_vectorized_grid() -> None:
    prop, _ = propagate_orbits(
        _tle_set([gp_record()]), window_start=ISS_EPOCH, window_hours=1, step_s=60
    )
    r, v = prop.state_at(0, 600.0)
    np.testing.assert_allclose(r, prop.positions[0, 10], atol=1e-6)
    np.testing.assert_allclose(v, prop.velocities[0, 10], atol=1e-9)


def test_stale_and_decaying_objects_are_dropped_not_raised() -> None:
    records = [
        gp_record(),
        gp_record(NORAD_CAT_ID=2, EPOCH="2026-08-01T00:00:00.000000"),
        # Perigee well below the surface: SGP4 returns error 6 (decayed) partway through.
        gp_record(NORAD_CAT_ID=3, MEAN_MOTION=15.5, ECCENTRICITY=0.3, BSTAR=0.0),
    ]
    prop, stats = propagate_orbits(
        _tle_set(records),
        window_start=ISS_EPOCH,
        window_hours=24,
        step_s=60,
        max_epoch_age_days=14,
    )
    assert [o.norad_id for o in prop.objects] == [25544]
    assert prop.positions.shape[0] == 1
    assert stats["dropped"] == {"stale_epoch": 1, "sgp4_error": 1}
    reasons = {d["norad_id"]: d for d in prop.dropped}
    assert reasons[3]["error_code"] == 6
