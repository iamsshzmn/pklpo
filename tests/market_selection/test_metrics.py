"""
Тесты для pair metrics calculator.
"""

import numpy as np
import pandas as pd
import pytest

from src.market_selection.domain.metrics import PairMetrics, PairMetricsCalculator


@pytest.fixture
def metrics_calc():
    return PairMetricsCalculator(
        ema_slope_source="ema_21",
        slope_lookback_bars=50,
        adx_trend_threshold=25,
        adx_range_threshold=18,
    )


@pytest.fixture
def sample_data():
    n_bars = 100
    timestamps = np.arange(1000000, 1000000 + n_bars * 60000, 60000)
    trend = np.linspace(50000, 52000, n_bars)
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "close": trend,
            "volume": np.full(n_bars, 1_000_000.0),
            "atr_14": np.full(n_bars, 500.0),
            "adx_14": np.full(n_bars, 30.0),
            "ema_21": trend,
            "ema_55": trend - 50,
        }
    )


def test_calculate_all(metrics_calc, sample_data):
    metrics = metrics_calc.calculate_all(sample_data, "BTC-USDT", "1H", expected_bars=100)

    assert isinstance(metrics, PairMetrics)
    assert metrics.symbol == "BTC-USDT"
    assert metrics.timeframe == "1H"
    assert metrics.valid_bars == 100
    assert metrics.expected_bars == 100
    assert metrics.vol_raw is not None
    assert metrics.trend_q_raw is not None
    assert metrics.noise_raw is not None
    assert metrics.stability_raw is not None
    assert metrics.liq_raw is not None


def test_calc_volatility(metrics_calc, sample_data):
    assert metrics_calc._calc_volatility(sample_data) > 0
    assert metrics_calc._calc_volatility(sample_data.drop(columns=["atr_14"])) is None


def test_calc_trend_quality(metrics_calc, sample_data):
    assert metrics_calc._calc_trend_quality(sample_data) > 0
    assert metrics_calc._calc_trend_quality(sample_data.drop(columns=["adx_14"])) is None


def test_calc_ema_slope(metrics_calc, sample_data):
    assert metrics_calc._calc_ema_slope(sample_data, "ema_21") > 0
    assert metrics_calc._calc_ema_slope(sample_data.head(5), "ema_21") is None


def test_calc_noise(metrics_calc, sample_data):
    assert metrics_calc._calc_noise(sample_data) is not None
    assert metrics_calc._calc_noise(sample_data.head(1)) is None


def test_calc_stability(metrics_calc, sample_data):
    stability = metrics_calc._calc_stability(sample_data)
    assert stability is not None
    assert 0 <= stability <= 1
    assert metrics_calc._calc_stability(sample_data.head(10)) is None


def test_classify_bar_regime(metrics_calc, sample_data):
    valid_df = sample_data[["adx_14", "atr_14", "close", "ema_21"]].dropna()
    atr_close = valid_df["atr_14"] / valid_df["close"]
    ema_values = valid_df["ema_21"].to_numpy()
    atr_p80 = float(atr_close.quantile(0.8))

    regime = metrics_calc._classify_bar_regime(
        valid_df=valid_df,
        ema_values=ema_values,
        atr_close_ratio=atr_close,
        atr_p80=atr_p80,
        index=len(valid_df) - 1,
    )
    assert regime in {"TREND", "RANGE", "VOLATILE", "NEUTRAL"}


def test_calc_window_ema_slope_norm(metrics_calc, sample_data):
    valid_df = sample_data[["close", "ema_21"]]
    window_ema = valid_df["ema_21"].to_numpy()[:20]
    slope_norm = metrics_calc._calc_window_ema_slope_norm(valid_df, window_ema, 0, 19)
    assert slope_norm > 0


def test_calc_liquidity(metrics_calc, sample_data):
    assert metrics_calc._calc_liquidity(sample_data) > 0
    assert metrics_calc._calc_liquidity(sample_data.drop(columns=["volume"])) is None


def test_to_dict(metrics_calc, sample_data):
    metrics = metrics_calc.calculate_all(sample_data, "BTC-USDT", "1H", expected_bars=100)
    metrics_dict = metrics.to_dict()
    assert metrics_dict["symbol"] == "BTC-USDT"
    assert metrics_dict["timeframe"] == "1H"
    assert "stability_raw" in metrics_dict
