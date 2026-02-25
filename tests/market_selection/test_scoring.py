"""
Тесты для scoring engine (система оценки).
"""

import pandas as pd
import pytest

from src.market_selection.config import MarketSelectionConfig
from src.market_selection.domain.regime import RegimeType
from src.market_selection.domain.scoring import FinalScore, ScoringEngine, TFScore


@pytest.fixture
def config():
    """Фикстура конфигурации."""
    return MarketSelectionConfig()


@pytest.fixture
def scoring_engine(config):
    """Фикстура scoring engine."""
    return ScoringEngine(config)


def test_normalize_metrics_basic(scoring_engine):
    """Тест нормализации метрик."""
    metrics_df = pd.DataFrame({
        "symbol": ["BTC-USDT", "ETH-USDT", "SOL-USDT"],
        "vol_raw": [0.02, 0.03, 0.01],
        "trend_q_raw": [0.5, 0.6, 0.4],
        "noise_raw": [1.5, 1.2, 1.8],
        "stability_raw": [0.8, 0.9, 0.7],
        "liq_raw": [1000, 2000, 500],
    })

    normalized = scoring_engine.normalize_metrics(metrics_df, "1H")

    assert len(normalized) == 3
    assert "vol_score" in normalized.columns
    assert "trend_q_score" in normalized.columns
    assert "noise_score" in normalized.columns
    assert "stability_score" in normalized.columns
    assert "liq_score" in normalized.columns

    # Все scores должны быть в диапазоне [0, 1]
    for col in ["vol_score", "trend_q_score", "noise_score", "stability_score", "liq_score"]:
        assert (normalized[col] >= 0).all()
        assert (normalized[col] <= 1).all()


def test_normalize_metrics_empty(scoring_engine):
    """Тест нормализации пустого DataFrame."""
    empty_df = pd.DataFrame()
    normalized = scoring_engine.normalize_metrics(empty_df, "1H")
    assert len(normalized) == 0


def test_normalize_metrics_missing_columns(scoring_engine):
    """Тест нормализации с отсутствующими колонками."""
    metrics_df = pd.DataFrame({
        "symbol": ["BTC-USDT"],
        "vol_raw": [0.02],
    })
    normalized = scoring_engine.normalize_metrics(metrics_df, "1H")
    # Отсутствующие колонки должны быть заполнены нулями
    assert "trend_q_score" in normalized.columns
    assert normalized["trend_q_score"].iloc[0] == 0.0


def test_get_adjusted_weights(scoring_engine):
    """Тест получения скорректированных весов для режима."""
    weights_trend = scoring_engine.get_adjusted_weights(RegimeType.TREND_UP)
    weights_range = scoring_engine.get_adjusted_weights(RegimeType.RANGE)
    weights_volatile = scoring_engine.get_adjusted_weights(RegimeType.VOLATILE)

    # Веса должны суммироваться в 1.0
    assert sum(weights_trend.values()) == pytest.approx(1.0, abs=1e-6)
    assert sum(weights_range.values()) == pytest.approx(1.0, abs=1e-6)
    assert sum(weights_volatile.values()) == pytest.approx(1.0, abs=1e-6)

    # В режиме TREND_UP trend_q должен иметь больший вес
    assert weights_trend["trend_q"] > scoring_engine.scoring_config.base_weights["trend_q"]


def test_calculate_tf_scores(scoring_engine):
    """Тест расчета оценок для таймфрейма."""
    normalized_df = pd.DataFrame({
        "symbol": ["BTC-USDT", "ETH-USDT"],
        "vol_score": [0.8, 0.6],
        "trend_q_score": [0.9, 0.7],
        "noise_score": [0.7, 0.5],
        "stability_score": [0.85, 0.75],
        "liq_score": [0.9, 0.8],
    })

    quality_scores = {"BTC-USDT": 1.0, "ETH-USDT": 0.9}
    scores = scoring_engine.calculate_tf_scores(
        normalized_df, "1H", RegimeType.TREND_UP, quality_scores
    )

    assert len(scores) == 2
    assert all(isinstance(s, TFScore) for s in scores)
    assert scores[0].symbol == "BTC-USDT"
    assert scores[0].score_tf_base > 0
    assert scores[0].score_tf == pytest.approx(scores[0].score_tf_base * 1.0)


def test_aggregate_mtf_scores_basic(scoring_engine):
    """Тест агрегации оценок по таймфреймам."""
    tf_scores = {
        "4H": {"BTC-USDT": 0.8, "ETH-USDT": 0.7},
        "1H": {"BTC-USDT": 0.75, "ETH-USDT": 0.65},
        "15m": {"BTC-USDT": 0.7, "ETH-USDT": 0.6},
        "5m": {"BTC-USDT": 0.65, "ETH-USDT": 0.55},
    }

    final_scores = scoring_engine.aggregate_mtf_scores(tf_scores, RegimeType.TREND_UP)

    assert len(final_scores) == 2
    assert all(isinstance(s, FinalScore) for s in final_scores)
    assert final_scores[0].symbol == "BTC-USDT"
    assert final_scores[0].final_score > final_scores[1].final_score
    assert final_scores[0].rank == 1
    assert final_scores[1].rank == 2


def test_aggregate_mtf_scores_missing_senior_tf(scoring_engine):
    """Тест агрегации при отсутствии старших таймфреймов."""
    # Отсутствует 4H и 1H - символ должен быть исключен
    tf_scores = {
        "15m": {"BTC-USDT": 0.7},
        "5m": {"BTC-USDT": 0.65},
    }

    final_scores = scoring_engine.aggregate_mtf_scores(tf_scores, RegimeType.TREND_UP)
    # Символ без старших таймфреймов должен быть исключен
    assert len(final_scores) == 0


def test_aggregate_mtf_scores_missing_4h_soft(scoring_engine):
    """Тест агрегации при отсутствии 4H (мягкое наказание)."""
    tf_scores = {
        "1H": {"BTC-USDT": 0.75},
        "15m": {"BTC-USDT": 0.7},
        "5m": {"BTC-USDT": 0.65},
    }

    final_scores = scoring_engine.aggregate_mtf_scores(tf_scores, RegimeType.TREND_UP)

    assert len(final_scores) == 1
    assert final_scores[0].symbol == "BTC-USDT"
    # Должно быть применено наказание за отсутствие 4H
    assert final_scores[0].penalty_applied > 0
    # Проверяем, что есть флаг
    from src.market_selection.domain.quality_gate import ReasonFlag
    assert ReasonFlag.MISSING_4H_SOFT in final_scores[0].reason_flags


def test_aggregate_mtf_scores_missing_junior_tf(scoring_engine):
    """Тест агрегации при отсутствии младших таймфреймов."""
    tf_scores = {
        "4H": {"BTC-USDT": 0.8},
        "1H": {"BTC-USDT": 0.75},
        # Отсутствуют 15m и 5m
    }

    final_scores = scoring_engine.aggregate_mtf_scores(tf_scores, RegimeType.TREND_UP)

    assert len(final_scores) == 1
    # Должно быть применено наказание за отсутствие младших таймфреймов
    assert final_scores[0].penalty_applied > 0


def test_apply_volatile_filter(scoring_engine):
    """Тест фильтрации по ликвидности в режиме VOLATILE."""
    scores = [
        TFScore(
            symbol="BTC-USDT",
            timeframe="1H",
            vol_score=0.8,
            trend_q_score=0.7,
            noise_score=0.6,
            stability_score=0.75,
            liq_score=0.4,  # Выше порога
            score_tf_base=0.7,
            score_tf=0.7,
        ),
        TFScore(
            symbol="ETH-USDT",
            timeframe="1H",
            vol_score=0.7,
            trend_q_score=0.6,
            noise_score=0.5,
            stability_score=0.65,
            liq_score=0.2,  # Ниже порога (0.30)
            score_tf_base=0.6,
            score_tf=0.6,
        ),
    ]

    liq_scores = {"BTC-USDT": 0.4, "ETH-USDT": 0.2}
    excluded = scoring_engine.apply_volatile_filter(scores, liq_scores)

    assert "ETH-USDT" in excluded
    assert "BTC-USDT" not in excluded


def test_zscore_sigmoid_normalize(scoring_engine):
    """Тест нормализации через z-score и sigmoid для малых выборок."""
    import numpy as np
    import pandas as pd

    # Малая выборка (меньше fallback_zscore_threshold=20)
    metrics_df = pd.DataFrame({
        "symbol": [f"SYM-{i}" for i in range(10)],
        "vol_raw": np.random.uniform(0.01, 0.05, 10),
        "trend_q_raw": np.random.uniform(0.3, 0.7, 10),
        "noise_raw": np.random.uniform(1.0, 2.0, 10),
        "stability_raw": np.random.uniform(0.6, 0.9, 10),
        "liq_raw": np.random.uniform(500, 2000, 10),
    })

    normalized = scoring_engine.normalize_metrics(metrics_df, "1H")

    # Все scores должны быть в диапазоне [0, 1]
    for col in ["vol_score", "trend_q_score", "noise_score", "stability_score", "liq_score"]:
        assert (normalized[col] >= 0).all()
        assert (normalized[col] <= 1).all()
