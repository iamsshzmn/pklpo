"""
Тесты для pair metrics calculator (калькулятор метрик пар).
"""

import numpy as np
import pandas as pd
import pytest

from src.market_selection.domain.metrics import PairMetrics, PairMetricsCalculator


@pytest.fixture
def metrics_calc():
    """Фикстура калькулятора метрик."""
    return PairMetricsCalculator(
        ema_slope_source="ema_21",
        slope_lookback_bars=50,
        adx_trend_threshold=25,
        adx_range_threshold=18,
    )


@pytest.fixture
def sample_data():
    """Фикстура примера данных."""
    n_bars = 100
    timestamps = np.arange(1000000, 1000000 + n_bars * 60000, 60000)

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "close": 50000 + np.cumsum(np.random.randn(n_bars) * 100),
            "volume": 1000000 + np.random.randn(n_bars) * 100000,
            "atr_14": 500 + np.random.randn(n_bars) * 50,
            "adx_14": 20 + np.random.randn(n_bars) * 5,
            "ema_21": 50000 + np.cumsum(np.random.randn(n_bars) * 100),
            "ema_55": 50000 + np.cumsum(np.random.randn(n_bars) * 100),
        }
    )


def test_calculate_all(metrics_calc, sample_data):
    """Тест расчета всех метрик."""
    metrics = metrics_calc.calculate_all(
        sample_data, "BTC-USDT", "1H", expected_bars=100
    )

    assert isinstance(metrics, PairMetrics)
    assert metrics.symbol == "BTC-USDT"
    assert metrics.timeframe == "1H"
    assert metrics.valid_bars == 100
    assert metrics.expected_bars == 100

    # Все метрики должны быть вычислены
    assert metrics.vol_raw is not None
    assert metrics.trend_q_raw is not None
    assert metrics.noise_raw is not None
    assert metrics.stability_raw is not None
    assert metrics.liq_raw is not None


def test_calc_volatility(metrics_calc, sample_data):
    """Тест расчета волатильности."""
    vol = metrics_calc._calc_volatility(sample_data)
    assert vol is not None
    assert vol > 0

    # Тест с отсутствующими колонками
    data_no_atr = sample_data.drop(columns=["atr_14"])
    vol_none = metrics_calc._calc_volatility(data_no_atr)
    assert vol_none is None


def test_calc_trend_quality(metrics_calc, sample_data):
    """Тест расчета качества тренда."""
    trend_q = metrics_calc._calc_trend_quality(sample_data)
    assert trend_q is not None
    assert trend_q >= 0

    # Тест с отсутствующими колонками
    data_no_adx = sample_data.drop(columns=["adx_14"])
    trend_q_none = metrics_calc._calc_trend_quality(data_no_adx)
    assert trend_q_none is None


def test_calc_ema_slope(metrics_calc, sample_data):
    """Тест расчета наклона EMA."""
    slope = metrics_calc._calc_ema_slope(sample_data, "ema_21")
    assert slope is not None

    # Тест с недостаточным количеством данных
    data_short = sample_data.head(5)
    slope_none = metrics_calc._calc_ema_slope(data_short, "ema_21")
    assert slope_none is None


def test_calc_noise(metrics_calc, sample_data):
    """Тест расчета шума."""
    noise = metrics_calc._calc_noise(sample_data)
    assert noise is not None
    assert noise >= 0

    # Тест с недостаточным количеством данных
    data_short = sample_data.head(1)
    noise_none = metrics_calc._calc_noise(data_short)
    assert noise_none is None


def test_calc_stability(metrics_calc, sample_data):
    """Тест расчета стабильности."""
    stability = metrics_calc._calc_stability(sample_data)
    assert stability is not None
    assert 0 <= stability <= 1

    # Тест с недостаточным количеством данных
    data_short = sample_data.head(10)
    stability_none = metrics_calc._calc_stability(data_short)
    assert stability_none is None


def test_calc_liquidity(metrics_calc, sample_data):
    """Тест расчета ликвидности."""
    liq = metrics_calc._calc_liquidity(sample_data)
    assert liq is not None
    assert liq >= 0

    # Тест с отсутствующими колонками
    data_no_volume = sample_data.drop(columns=["volume"])
    liq_none = metrics_calc._calc_liquidity(data_no_volume)
    assert liq_none is None


def test_calc_stability_regime_classification(metrics_calc):
    """Тест классификации режимов для стабильности."""
    # Создаем данные с четким трендом
    n_bars = 100
    trend_data = pd.DataFrame(
        {
            "close": 50000 + np.arange(n_bars) * 10,  # Четкий восходящий тренд
            "atr_14": np.full(n_bars, 500),
            "adx_14": np.full(n_bars, 30),  # Высокий ADX (тренд)
            "ema_21": 50000 + np.arange(n_bars) * 10,
        }
    )

    stability = metrics_calc._calc_stability(trend_data)
    # Стабильный тренд должен дать высокую стабильность
    assert stability is not None
    assert stability > 0.5


def test_calc_liquidity_high_cv(metrics_calc):
    """Тест расчета ликвидности с высоким CV."""
    # Данные с высоким коэффициентом вариации
    high_cv_data = pd.DataFrame(
        {
            "volume": [1000000, 100, 2000000, 50, 1500000],
        }
    )

    liq = metrics_calc._calc_liquidity(high_cv_data)
    # Высокий CV должен снизить ликвидность
    assert liq is not None
    assert liq >= 0


def test_calc_liquidity_low_cv(metrics_calc):
    """Тест расчета ликвидности с низким CV."""
    # Данные с низким коэффициентом вариации
    low_cv_data = pd.DataFrame(
        {
            "volume": np.full(100, 1000000),  # Постоянный объем
        }
    )

    liq = metrics_calc._calc_liquidity(low_cv_data)
    # Низкий CV должен дать высокую ликвидность
    assert liq is not None
    assert liq > 0


def test_to_dict(metrics_calc, sample_data):
    """Тест преобразования метрик в словарь."""
    metrics = metrics_calc.calculate_all(
        sample_data, "BTC-USDT", "1H", expected_bars=100
    )

    metrics_dict = metrics.to_dict()

    assert isinstance(metrics_dict, dict)
    assert metrics_dict["symbol"] == "BTC-USDT"
    assert metrics_dict["timeframe"] == "1H"
    assert "vol_raw" in metrics_dict
    assert "trend_q_raw" in metrics_dict
    assert "noise_raw" in metrics_dict
    assert "stability_raw" in metrics_dict
    assert "liq_raw" in metrics_dict
