"""Stdlib-only configuration objects for domain services."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityGateConfig:
    """Configuration required by DataQualityGate."""

    thresholds: dict[str, dict[str, float]]
    warmup_min_bars: int
    gap_threshold_multiplier: float
    tf_bar_ms: dict[str, int]

    def get_quality_thresholds(self, timeframe: str) -> dict[str, float]:
        """Return quality thresholds for a timeframe."""
        return self.thresholds.get(
            timeframe,
            {"fill_min": 0.95, "gap_max": 0.02, "lag_max_min": 60},
        )

    def get_tf_bar_ms(self, timeframe: str) -> int:
        """Return bar size in milliseconds for a timeframe."""
        return self.tf_bar_ms.get(timeframe, 60_000)


@dataclass(frozen=True)
class RegimeClassifierConfig:
    """Configuration required by RegimeClassifier."""

    basket_k: int
    adx_trend_threshold: int
    adx_range_threshold: int
    trend_up_threshold: float
    trend_down_threshold: float
    tf_weights: dict[str, float]
    regime_tfs: list[str]


@dataclass(frozen=True)
class ScoringConfig:
    """Configuration required by ScoringEngine."""

    base_weights: dict[str, float]
    regime_deltas: dict[str, dict[str, float]]
    tf_weights: dict[str, float]
    missing_senior_penalty: dict[str, float]
    missing_junior_penalty: float
    volatile_min_liq_score: float
    winsorize_percentiles: tuple[float, float]
    winsorize_small_universe: tuple[float, float]
    small_universe_threshold: int
    fallback_zscore_threshold: int


@dataclass(frozen=True)
class UniverseConfig:
    """Configuration required by UniverseManager."""

    top_n: int
    buffer: int
    score_std_7d_max: float
    score_std_30d_max: float
    min_history_days: int
    min_universe_hard: int
    min_universe_soft: int
    systemic_senior_outage_threshold: float
