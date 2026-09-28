"""`assess_risk`: a documented threshold table, not a probability of collision (ADR 0004).

Rules, first match wins (thresholds from `config/screening.yaml`'s `risk` section):

| Level    | Miss distance            | Closing speed          | Objects                      |
|----------|--------------------------|------------------------|------------------------------|
| high     | < high_miss_km           | >= hypervelocity_km_s  | at least one active payload  |
| moderate | < high_miss_km           | any                    | any                          |
| moderate | < moderate_miss_km_active| any                    | at least one active payload  |
| low      | < screening threshold    | any                    | any                          |

"Active payload" counts unknown status (no SATCAT record) as active: a screening tool should err
toward surfacing a pass, not hiding it. Reasoning for each number is in
docs/working-notes-and-decisions.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.data.models import CatalogObject
from app.settings import RiskSettings

RiskLevel = Literal["high", "moderate", "low"]
RISK_ORDER: dict[str, int] = {"high": 0, "moderate": 1, "low": 2}


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    reason: str
    involves_active_payload: bool


def assess_risk(
    miss_distance_km: float,
    relative_speed_km_s: float,
    object_a: CatalogObject,
    object_b: CatalogObject,
    settings: RiskSettings,
) -> RiskAssessment:
    active = any(o.is_active is not False for o in (object_a, object_b))
    fast = relative_speed_km_s >= settings.hypervelocity_km_s
    if miss_distance_km < settings.high_miss_km and fast and active:
        return RiskAssessment(
            "high",
            f"miss < {settings.high_miss_km} km at >= {settings.hypervelocity_km_s} km/s "
            "with an active payload involved",
            active,
        )
    if miss_distance_km < settings.high_miss_km:
        why = "no active payload involved" if not active else "low closing speed"
        return RiskAssessment("moderate", f"miss < {settings.high_miss_km} km, {why}", active)
    if miss_distance_km < settings.moderate_miss_km_active and active:
        return RiskAssessment(
            "moderate",
            f"miss < {settings.moderate_miss_km_active} km with an active payload involved",
            active,
        )
    return RiskAssessment("low", "within screening threshold only", active)
