"""`propagate_orbits`: vectorized SGP4 over a time window, in the TEME frame.

TEME is fine for conjunction screening without any frame conversion: separation between two objects
propagated to the same instant in the same frame is frame-independent (see ADR 0002).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sgp4 import omm
from sgp4.api import SGP4_ERRORS, Satrec, SatrecArray, accelerated, jday

from app.data.models import CatalogObject, TleSet

log = logging.getLogger(__name__)

SECONDS_PER_DAY = 86400.0
Vec3 = NDArray[np.float64]


@dataclass
class PropagationResult:
    """Positions/velocities for the objects that propagated cleanly across the whole window.

    `positions[i, k]` and `velocities[i, k]` are object `objects[i]` at `window_start +
    offsets_s[k]`, in km and km/s (TEME). `satrecs[i]` is kept so screening can re-propagate a
    single pair at arbitrary instants when refining a closest-approach time.
    """

    objects: list[CatalogObject]
    satrecs: list[Satrec]
    window_start: datetime
    offsets_s: NDArray[np.float64]
    positions: NDArray[np.float64]
    velocities: NDArray[np.float64]
    dropped: list[dict[str, Any]] = field(default_factory=list)

    @property
    def step_s(self) -> float:
        return float(self.offsets_s[1] - self.offsets_s[0]) if len(self.offsets_s) > 1 else 0.0

    def time_at(self, offset_s: float) -> datetime:
        return self.window_start + timedelta(seconds=offset_s)

    def state_at(self, index: int, offset_s: float) -> tuple[Vec3, Vec3]:
        """Propagate one object to `window_start + offset_s` (for TCA refinement)."""
        jd0, fr0 = _jday(self.window_start)
        err, r, v = self.satrecs[index].sgp4(jd0, fr0 + offset_s / SECONDS_PER_DAY)
        if err:
            raise RuntimeError(f"SGP4 error {err} for {self.objects[index].norad_id}")
        return np.asarray(r), np.asarray(v)


def _jday(t: datetime) -> tuple[float, float]:
    t = t.astimezone(UTC)
    jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond / 1e6)
    return float(jd), float(fr)


def build_satrec(obj: CatalogObject) -> Satrec:
    sat = Satrec()
    omm.initialize(sat, {k: str(v) for k, v in obj.elements.items()})
    return sat


def propagate_orbits(
    tle_set: TleSet,
    *,
    window_start: datetime,
    window_hours: float,
    step_s: float,
    max_epoch_age_days: float | None = None,
) -> tuple[PropagationResult, dict[str, Any]]:
    """Propagate every object in `tle_set` from `window_start` for `window_hours` at `step_s`.

    Objects are dropped (logged, recorded in `result.dropped`, never raised) if their elements are
    older than `max_epoch_age_days`, fail to initialize, or return any SGP4 error code anywhere in
    the window (e.g. decay during the window). Returns the result and a stats dict for tracing.
    """
    dropped: list[dict[str, Any]] = []
    kept: list[CatalogObject] = []
    satrecs: list[Satrec] = []
    for obj in tle_set.objects:
        age_days = (window_start - obj.epoch).total_seconds() / SECONDS_PER_DAY
        if max_epoch_age_days is not None and age_days > max_epoch_age_days:
            dropped.append(_drop(obj, "stale_epoch", epoch_age_days=round(age_days, 2)))
            continue
        try:
            sat = build_satrec(obj)
        except (ValueError, KeyError) as exc:
            dropped.append(_drop(obj, "init_failed", error=repr(exc)))
            continue
        if sat.error:
            dropped.append(_drop(obj, "init_failed", error=SGP4_ERRORS.get(sat.error)))
            continue
        kept.append(obj)
        satrecs.append(sat)

    n_steps = int(round(window_hours * 3600.0 / step_s)) + 1
    offsets = np.arange(n_steps, dtype=np.float64) * step_s
    jd0, fr0 = _jday(window_start)
    jd = np.full(n_steps, jd0)
    fr = fr0 + offsets / SECONDS_PER_DAY

    if satrecs:
        err, r, v = SatrecArray(satrecs).sgp4(jd, fr)
        bad = np.flatnonzero(err.any(axis=1))
    else:
        err = np.zeros((0, n_steps), dtype=np.uint8)
        r = v = np.zeros((0, n_steps, 3))
        bad = np.array([], dtype=np.int64)
    for i in bad:
        code = int(err[i][err[i] != 0][0])
        dropped.append(
            _drop(kept[i], "sgp4_error", error_code=code, error=SGP4_ERRORS.get(code, "unknown"))
        )
    good = np.setdiff1d(np.arange(len(kept)), bad)
    for d in dropped:
        log.warning("dropped %s (%s): %s", d["norad_id"], d["name"], d["reason"])

    result = PropagationResult(
        objects=[kept[i] for i in good],
        satrecs=[satrecs[i] for i in good],
        window_start=window_start,
        offsets_s=offsets,
        positions=np.ascontiguousarray(r[good]),
        velocities=np.ascontiguousarray(v[good]),
        dropped=dropped,
    )
    reasons: dict[str, int] = {}
    for d in dropped:
        reasons[d["reason"]] = reasons.get(d["reason"], 0) + 1
    stats = {
        "objects_in": len(tle_set),
        "objects_propagated": len(result.objects),
        "dropped": reasons,
        "timesteps": n_steps,
        "state_evaluations": len(result.objects) * n_steps,
        "sgp4_accelerated": bool(accelerated),
        "positions_mb": round(result.positions.nbytes / 1e6, 1),
    }
    return result, stats


def _drop(obj: CatalogObject, reason: str, **extra: Any) -> dict[str, Any]:
    return {"norad_id": obj.norad_id, "name": obj.name, "reason": reason, **extra}
