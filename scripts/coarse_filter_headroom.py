"""Session 2 Step B: measure how much ADR 0003's altitude-band coarse filter *could* remove.

Measurement only - Step C is not implemented. Run after `scripts/scaling_spike.py` has frozen its
snapshot and produced a report:

    uv run python scripts/coarse_filter_headroom.py

The KD-tree already discards pairs more than 485 km apart, so the question is narrower: of the
pairs the tree *does* return, how many belong to objects whose altitude bands can never come within
the screening threshold? Two band definitions:

- `propagated`: each object's actual radius range over the window, widened by its max radial speed
  x step/2 (radius can move that much between samples). Provably safe: |r_a| - |r_b| <= |r_a - r_b|,
  so two objects whose bands are more than `threshold` apart can never be within `threshold`.
- `elements pad=X`: ADR 0003's version - perigee/apogee from mean elements, padded by X km, since
  SGP4 short-period terms move the osculating radius off the mean-element band.

Each variant is validated against the spike report's actual conjunctions: a safe filter drops none.
"""

from __future__ import annotations

import glob
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from app.data.celestrak_client import fetch_tle_data
from app.propagation.sgp4_propagator import propagate_orbits
from app.settings import load_settings

FREEZE_DIR = Path("cache/scaling-spike")
GROUPS = ["active", "fengyun-1c-debris"]
MU_KM3_S2 = 398600.8  # WGS-72
SAMPLE_EVERY = 30  # timesteps; 49 of 1,441 sampled
ELEMENT_PADS_KM = [0.0, 5.0, 10.0, 20.0, 30.0]


def band_gap(lo: NDArray[np.float64], hi: NDArray[np.float64], i: Any, j: Any) -> Any:
    """Gap between two [lo, hi] intervals (<= 0 means they overlap)."""
    return np.maximum(lo[i], lo[j]) - np.minimum(hi[i], hi[j])


def main() -> int:
    manifest = json.loads((FREEZE_DIR / "manifest.json").read_text())
    base = load_settings().with_overrides(groups=GROUPS)
    settings = replace(
        base, source=replace(base.source, cache_dir=str(FREEZE_DIR), cache_ttl_hours=1e9)
    )
    tle_set, _ = fetch_tle_data(GROUPS, settings.source)
    prop, _ = propagate_orbits(
        tle_set,
        window_start=datetime.fromisoformat(manifest["window_start_utc"]),
        window_hours=settings.propagation.window_hours,
        step_s=settings.propagation.step_seconds,
        max_epoch_age_days=settings.source.max_epoch_age_days,
    )
    threshold = settings.screening.threshold_km
    radius_search = threshold + settings.screening.max_relative_speed_km_s * prop.step_s / 2

    # Propagated band (provably safe).
    r = np.linalg.norm(prop.positions, axis=2)
    v_radial = np.abs(np.einsum("ntk,ntk->nt", prop.positions, prop.velocities)) / r
    slack = v_radial.max(axis=1) * prop.step_s / 2
    prop_lo, prop_hi = r.min(axis=1) - slack, r.max(axis=1) + slack

    # Mean-element band (ADR 0003's pre-propagation version).
    el = [o.elements for o in prop.objects]
    n_rad_s = np.array([float(e["MEAN_MOTION"]) for e in el]) * 2 * np.pi / 86400
    ecc = np.array([float(e["ECCENTRICITY"]) for e in el])
    a = (MU_KM3_S2 / n_rad_s**2) ** (1 / 3)
    el_lo, el_hi = a * (1 - ecc), a * (1 + ecc)

    variants: dict[str, tuple[Any, Any, float]] = {"propagated": (prop_lo, prop_hi, 0.0)}
    for pad in ELEMENT_PADS_KM:
        variants[f"elements pad={pad:g}km"] = (el_lo, el_hi, pad)

    removed = dict.fromkeys(variants, 0)
    total = 0
    steps = range(0, prop.positions.shape[1], SAMPLE_EVERY)
    for k in steps:
        pairs = cKDTree(prop.positions[:, k, :]).query_pairs(radius_search, output_type="ndarray")
        i, j = pairs[:, 0], pairs[:, 1]
        total += len(pairs)
        for name, (lo, hi, pad) in variants.items():
            removed[name] += int(np.count_nonzero(band_gap(lo, hi, i, j) > threshold + pad))

    # Validate against real conjunctions found by the full screen.
    report_path = sorted(glob.glob("runs/scaling-spike/reports/*.json"))[-1]
    report = json.loads(Path(report_path).read_text())
    index = {o.norad_id: n for n, o in enumerate(prop.objects)}
    ca = np.array([index[c["object_a"]["norad_id"]] for c in report["conjunctions"]])
    cb = np.array([index[c["object_b"]["norad_id"]] for c in report["conjunctions"]])
    wrongly_dropped = {
        name: int(np.count_nonzero(band_gap(lo, hi, ca, cb) > threshold + pad))
        for name, (lo, hi, pad) in variants.items()
    }

    result = {
        "objects": len(prop.objects),
        "sampled_timesteps": len(steps),
        "kd_tree_pairs_sampled": total,
        "mean_kd_tree_pairs_per_step": round(total / len(steps), 1),
        "validated_against": {"report": report_path, "conjunctions": len(ca)},
        "variants": {
            name: {
                "fraction_of_kd_tree_pairs_removed": round(removed[name] / total, 4),
                "real_conjunctions_wrongly_dropped": wrongly_dropped[name],
            }
            for name in variants
        },
    }
    out = Path("runs/scaling-spike/coarse_filter_headroom.json")
    out.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
