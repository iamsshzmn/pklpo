"""
Pytest fixtures for Market Selection tests.

Provides fixed config, domain components, and sample data.
"""

from __future__ import annotations

import pytest

from src.market_selection.config import (
    MarketSelectionConfig,
    QualityConfig,
    RegimeConfig,
    ScoringConfig,
    UniverseConfig,
)
from src.market_selection.domain.metrics import PairMetricsCalculator
from src.market_selection.domain.quality_gate import DataQualityGate
from src.market_selection.domain.regime import RegimeClassifier
from src.market_selection.domain.scoring import ScoringEngine
from src.market_selection.domain.universe import UniverseManager


@pytest.fixture
def market_selection_config() -> MarketSelectionConfig:
    """Default config for tests (fixed windows, thresholds, weights)."""
    return MarketSelectionConfig(
        selection_tfs=["5m", "15m", "1H", "4H"],
        regime_tfs=["1D", "4H", "1H"],
        windows_days={"5m": 30, "15m": 45, "1H": 90, "4H": 120},
        regime_windows_days={"1D": 180, "4H": 120, "1H": 60},
        regime=RegimeConfig(
            basket_k=20,
            adx_trend_threshold=25,
            adx_range_threshold=18,
            trend_up_threshold=0.35,
            trend_down_threshold=-0.35,
        ),
        quality=QualityConfig(
            thresholds={
                "5m": {"fill_min": 0.97, "gap_max": 0.015, "lag_max_min": 15},
                "15m": {"fill_min": 0.98, "gap_max": 0.010, "lag_max_min": 45},
                "1H": {"fill_min": 0.99, "gap_max": 0.005, "lag_max_min": 180},
                "4H": {"fill_min": 0.99, "gap_max": 0.005, "lag_max_min": 720},
            },
            warmup_min_bars=280,
            gap_threshold_multiplier=1.5,
        ),
        scoring=ScoringConfig(
            base_weights={
                "vol": 0.25,
                "trend_q": 0.30,
                "noise": 0.20,
                "stability": 0.15,
                "liq": 0.10,
            },
            tf_weights={"4H": 0.40, "1H": 0.30, "15m": 0.20, "5m": 0.10},
            winsorize_percentiles=(1.0, 99.0),
            winsorize_small_universe=(5.0, 95.0),
            small_universe_threshold=50,
            fallback_zscore_threshold=20,
        ),
        universe=UniverseConfig(
            top_n=30,
            buffer=10,
            score_std_7d_max=0.12,
            score_std_30d_max=0.18,
            min_history_days=7,
            min_universe_hard=5,
            min_universe_soft=10,
        ),
    )


@pytest.fixture
def quality_gate(market_selection_config: MarketSelectionConfig) -> DataQualityGate:
    """DataQualityGate with test config."""
    return DataQualityGate(market_selection_config)


@pytest.fixture
def scoring_engine(market_selection_config: MarketSelectionConfig) -> ScoringEngine:
    """ScoringEngine with test config."""
    return ScoringEngine(market_selection_config)


@pytest.fixture
def regime_classifier(market_selection_config: MarketSelectionConfig) -> RegimeClassifier:
    """RegimeClassifier with test config."""
    return RegimeClassifier(market_selection_config)


@pytest.fixture
def metrics_calculator() -> PairMetricsCalculator:
    """PairMetricsCalculator with default params."""
    return PairMetricsCalculator(
        ema_slope_source="ema_21",
        slope_lookback_bars=50,
        adx_trend_threshold=25,
        adx_range_threshold=18,
    )


@pytest.fixture
def universe_manager(market_selection_config: MarketSelectionConfig) -> UniverseManager:
    """UniverseManager with test config."""
    return UniverseManager(market_selection_config)
