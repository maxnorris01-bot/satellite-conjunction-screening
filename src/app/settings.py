"""Screening parameters, loaded from `config/screening.yaml`.

Separate from `app.config.Config`, which holds the template's environment-driven runtime knobs
(tracing, LLM mode, agent caps). These are domain parameters - thresholds, scope, time window - and
live in a versioned file so a run's report can record exactly which values produced it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SETTINGS_PATH = Path("config/screening.yaml")


@dataclass(frozen=True)
class SourceSettings:
    celestrak_base_url: str = "https://celestrak.org"
    cache_dir: str = "cache/celestrak"
    cache_ttl_hours: float = 2.0
    max_epoch_age_days: float = 14.0
    http_timeout_s: float = 30.0


@dataclass(frozen=True)
class PropagationSettings:
    window_hours: float = 24.0
    step_seconds: float = 60.0


@dataclass(frozen=True)
class ScreeningSettings:
    threshold_km: float = 5.0
    max_relative_speed_km_s: float = 16.0
    co_located_max_relative_speed_km_s: float = 0.1


@dataclass(frozen=True)
class RiskSettings:
    high_miss_km: float = 1.0
    moderate_miss_km_active: float = 2.5
    hypervelocity_km_s: float = 1.0


@dataclass(frozen=True)
class Settings:
    groups: tuple[str, ...] = ("stations", "fengyun-1c-debris")
    source: SourceSettings = field(default_factory=SourceSettings)
    propagation: PropagationSettings = field(default_factory=PropagationSettings)
    screening: ScreeningSettings = field(default_factory=ScreeningSettings)
    risk: RiskSettings = field(default_factory=RiskSettings)
    report_dir: str = "runs/reports"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_overrides(
        self,
        *,
        groups: list[str] | None = None,
        window_hours: float | None = None,
        step_seconds: float | None = None,
        threshold_km: float | None = None,
    ) -> Settings:
        s = self
        if groups:
            s = replace(s, groups=tuple(groups))
        if window_hours is not None:
            s = replace(s, propagation=replace(s.propagation, window_hours=window_hours))
        if step_seconds is not None:
            s = replace(s, propagation=replace(s.propagation, step_seconds=step_seconds))
        if threshold_km is not None:
            s = replace(s, screening=replace(s.screening, threshold_km=threshold_km))
        return s


def load_settings(path: Path = DEFAULT_SETTINGS_PATH) -> Settings:
    raw: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
    return Settings(
        groups=tuple(raw.get("scope", {}).get("groups", Settings.groups)),
        source=SourceSettings(**raw.get("source", {})),
        propagation=PropagationSettings(**raw.get("propagation", {})),
        screening=ScreeningSettings(**raw.get("screening", {})),
        risk=RiskSettings(**raw.get("risk", {})),
        report_dir=raw.get("report", {}).get("output_dir", "runs/reports"),
    )
