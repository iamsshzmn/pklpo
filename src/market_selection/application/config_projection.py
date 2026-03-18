"""Projection of application config into domain-friendly shapes."""

from __future__ import annotations

from ..config import MarketSelectionConfig
from ..domain.config import (
    QualityGateConfig,
    RegimeClassifierConfig,
    ScoringConfig as DomainScoringConfig,
    UniverseConfig as DomainUniverseConfig,
)

TF_TO_MS = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1H": 60 * 60_000,
    "4H": 4 * 60 * 60_000,
    "12H": 12 * 60 * 60_000,
    "1D": 24 * 60 * 60_000,
    "1W": 7 * 24 * 60 * 60_000,
    "1M": 30 * 24 * 60 * 60_000,
}


def build_quality_gate_config(config: MarketSelectionConfig) -> QualityGateConfig:
    """Project application config into the domain quality config."""
    return QualityGateConfig(
        thresholds={tf: values.copy() for tf, values in config.quality.thresholds.items()},
        warmup_min_bars=config.quality.warmup_min_bars,
        gap_threshold_multiplier=config.quality.gap_threshold_multiplier,
        tf_bar_ms=TF_TO_MS.copy(),
    )


def build_regime_classifier_config(
    config: MarketSelectionConfig,
) -> RegimeClassifierConfig:
    """Project application config into the domain regime config."""
    return RegimeClassifierConfig(
        basket_k=config.regime.basket_k,
        adx_trend_threshold=config.regime.adx_trend_threshold,
        adx_range_threshold=config.regime.adx_range_threshold,
        trend_up_threshold=config.regime.trend_up_threshold,
        trend_down_threshold=config.regime.trend_down_threshold,
        tf_weights=config.regime.tf_weights.copy(),
        regime_tfs=list(config.regime_tfs),
    )


def build_scoring_config(config: MarketSelectionConfig) -> DomainScoringConfig:
    """Project application config into the domain scoring config."""
    return DomainScoringConfig(
        base_weights=config.scoring.base_weights.copy(),
        regime_deltas={
            regime: deltas.copy() for regime, deltas in config.scoring.regime_deltas.items()
        },
        tf_weights=config.scoring.tf_weights.copy(),
        missing_senior_penalty=config.scoring.missing_senior_penalty.copy(),
        missing_junior_penalty=config.scoring.missing_junior_penalty,
        volatile_min_liq_score=config.scoring.volatile_min_liq_score,
        winsorize_percentiles=config.scoring.winsorize_percentiles,
        winsorize_small_universe=config.scoring.winsorize_small_universe,
        small_universe_threshold=config.scoring.small_universe_threshold,
        fallback_zscore_threshold=config.scoring.fallback_zscore_threshold,
    )


def build_universe_config(config: MarketSelectionConfig) -> DomainUniverseConfig:
    """Project application config into the domain universe config."""
    return DomainUniverseConfig(
        top_n=config.universe.top_n,
        buffer=config.universe.buffer,
        score_std_7d_max=config.universe.score_std_7d_max,
        score_std_30d_max=config.universe.score_std_30d_max,
        min_history_days=config.universe.min_history_days,
        min_universe_hard=config.universe.min_universe_hard,
        min_universe_soft=config.universe.min_universe_soft,
        systemic_senior_outage_threshold=config.universe.systemic_senior_outage_threshold,
    )
