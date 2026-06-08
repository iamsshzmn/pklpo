"""
Тесты для scoring engine.
"""

import numpy as np
import pandas as pd
import pytest

from src.market_selection.application.config_projection import build_scoring_config
from src.market_selection.config import MarketSelectionConfig
from src.market_selection.domain.quality_gate import ReasonFlag
from src.market_selection.domain.regime import RegimeType
from src.market_selection.domain.scoring import FinalScore, ScoringEngine, TFScore


@pytest.fixture
def scoring_engine():
    config = build_scoring_config(MarketSelectionConfig())
    return ScoringEngine(config)


def test_normalize_metrics_basic(scoring_engine):
    metrics_df = pd.DataFrame(
        {
            "symbol": ["BTC-USDT", "ETH-USDT", "SOL-USDT"],
            "vol_raw": [0.02, 0.03, 0.01],
            "trend_q_raw": [0.5, 0.6, 0.4],
            "noise_raw": [1.5, 1.2, 1.8],
            "stability_raw": [0.8, 0.9, 0.7],
            "liq_raw": [1000, 2000, 500],
        }
    )

    normalized = scoring_engine.normalize_metrics(metrics_df, "1H")

    for col in [
        "vol_score",
        "trend_q_score",
        "noise_score",
        "stability_score",
        "liq_score",
    ]:
        assert col in normalized.columns
        assert (normalized[col] >= 0).all()
        assert (normalized[col] <= 1).all()


def test_normalize_metrics_handles_missing_columns(scoring_engine):
    normalized = scoring_engine.normalize_metrics(
        pd.DataFrame({"symbol": ["BTC-USDT"], "vol_raw": [0.02]}),
        "1H",
    )
    assert normalized["trend_q_score"].iloc[0] == 0.0
    assert normalized["noise_score"].iloc[0] == 0.0


def test_zscore_sigmoid_normalize_small_universe(scoring_engine):
    metrics_df = pd.DataFrame(
        {
            "symbol": [f"SYM-{i}" for i in range(10)],
            "vol_raw": np.linspace(0.01, 0.05, 10),
            "trend_q_raw": np.linspace(0.3, 0.7, 10),
            "noise_raw": np.linspace(1.0, 2.0, 10),
            "stability_raw": np.linspace(0.6, 0.9, 10),
            "liq_raw": np.linspace(500, 2000, 10),
        }
    )

    normalized = scoring_engine.normalize_metrics(metrics_df, "1H")
    assert (normalized["vol_score"] >= 0).all()
    assert (normalized["vol_score"] <= 1).all()


def test_get_adjusted_weights(scoring_engine):
    weights_trend = scoring_engine.get_adjusted_weights(RegimeType.TREND_UP)
    weights_range = scoring_engine.get_adjusted_weights(RegimeType.RANGE)
    weights_volatile = scoring_engine.get_adjusted_weights(RegimeType.VOLATILE)

    assert sum(weights_trend.values()) == pytest.approx(1.0, abs=1e-6)
    assert sum(weights_range.values()) == pytest.approx(1.0, abs=1e-6)
    assert sum(weights_volatile.values()) == pytest.approx(1.0, abs=1e-6)
    assert weights_trend["trend_q"] > scoring_engine.config.base_weights["trend_q"]


def test_calculate_tf_scores(scoring_engine):
    normalized_df = pd.DataFrame(
        {
            "symbol": ["BTC-USDT", "ETH-USDT"],
            "vol_score": [0.8, 0.6],
            "trend_q_score": [0.9, 0.7],
            "noise_score": [0.7, 0.5],
            "stability_score": [0.85, 0.75],
            "liq_score": [0.9, 0.8],
        }
    )

    scores = scoring_engine.calculate_tf_scores(
        normalized_df,
        "1H",
        RegimeType.TREND_UP,
        {"BTC-USDT": 1.0, "ETH-USDT": 0.9},
    )

    assert all(isinstance(score, TFScore) for score in scores)
    assert scores[0].weights_used
    assert scores[1].score_tf == pytest.approx(scores[1].score_tf_base * 0.9)


def test_aggregate_mtf_scores_basic(scoring_engine):
    tf_scores = {
        "4H": {"BTC-USDT": 0.8, "ETH-USDT": 0.7},
        "1H": {"BTC-USDT": 0.75, "ETH-USDT": 0.65},
        "15m": {"BTC-USDT": 0.7, "ETH-USDT": 0.6},
        "5m": {"BTC-USDT": 0.65, "ETH-USDT": 0.55},
    }

    final_scores = scoring_engine.aggregate_mtf_scores(tf_scores, RegimeType.TREND_UP)
    assert all(isinstance(score, FinalScore) for score in final_scores)
    assert final_scores[0].symbol == "BTC-USDT"
    assert final_scores[0].rank == 1
    assert final_scores[1].rank == 2


def test_aggregate_mtf_scores_excludes_without_senior_tfs(scoring_engine):
    final_scores = scoring_engine.aggregate_mtf_scores(
        {"15m": {"BTC-USDT": 0.7}, "5m": {"BTC-USDT": 0.65}},
        RegimeType.TREND_UP,
    )
    assert final_scores == []


def test_aggregate_mtf_scores_applies_soft_penalties(scoring_engine):
    tf_scores = {
        "1H": {"BTC-USDT": 0.75},
        "15m": {"BTC-USDT": 0.7},
        "5m": {"BTC-USDT": 0.65},
    }

    final_scores = scoring_engine.aggregate_mtf_scores(tf_scores, RegimeType.TREND_UP)
    assert len(final_scores) == 1
    assert final_scores[0].penalty_applied > 0
    assert ReasonFlag.MISSING_4H_SOFT in final_scores[0].reason_flags


def test_aggregate_mtf_scores_applies_junior_penalties(scoring_engine):
    tf_scores = {
        "4H": {"BTC-USDT": 0.8},
        "1H": {"BTC-USDT": 0.75},
    }

    final_scores = scoring_engine.aggregate_mtf_scores(tf_scores, RegimeType.TREND_UP)
    assert len(final_scores) == 1
    assert final_scores[0].penalty_applied > 0


def test_apply_volatile_filter(scoring_engine):
    scores = [
        TFScore("BTC-USDT", "1H", 0.8, 0.7, 0.6, 0.75, 0.4, 0.7, 0.7),
        TFScore("ETH-USDT", "1H", 0.7, 0.6, 0.5, 0.65, 0.2, 0.6, 0.6),
    ]

    excluded = scoring_engine.apply_volatile_filter(
        scores,
        {"BTC-USDT": 0.4, "ETH-USDT": 0.2},
    )

    assert excluded == ["ETH-USDT"]
