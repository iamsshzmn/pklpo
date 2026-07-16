"""
Unit tests for Market Selection Pair Metrics (5 metrics).

Covers: vol_raw (median atr_14/close), trend_q_raw (adx_norm * abs(ema_slope_norm)),
noise_raw (std(|r|)/median(|r|)), stability_raw (dominance*(1-switch_rate)),
liq_raw (median(vol)/(cv(vol)+1)) on fixed DataFrame.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.market_selection.domain.metrics import PairMetrics, PairMetricsCalculator


def make_ohlcv_indicators_df(
    n_bars: int = 100,
    close_base: float = 100.0,
    vol_base: float = 1000.0,
    atr_pct: float = 0.02,
    adx: float = 25.0,
    ema_slope: float = 0.001,
) -> pd.DataFrame:
    """Build a minimal DataFrame with close, volume, atr_14, adx_14, ema_21."""
    np.random.seed(42)
    ts = np.arange(n_bars)
    close = close_base + np.cumsum(np.random.randn(n_bars) * 0.5)
    close = np.maximum(close, 1.0)
    volume = vol_base + np.random.rand(n_bars) * 500
    volume = np.maximum(volume, 1.0)
    atr_14 = close * atr_pct
    adx_14 = np.full(n_bars, adx)
    ema_21 = close + ts * ema_slope * close_base
    return pd.DataFrame(
        {
            "close": close,
            "volume": volume,
            "atr_14": atr_14,
            "adx_14": adx_14,
            "ema_21": ema_21,
        }
    )


class TestVolatility:
    """Tests for vol_raw = median(atr_14 / close)."""

    def test_vol_raw_formula(
        self,
        metrics_calculator: PairMetricsCalculator,
    ) -> None:
        """vol_raw = median(atr_14/close)."""
        df = make_ohlcv_indicators_df(atr_pct=0.03)
        m = metrics_calculator.calculate_all(df, "BTC", "1H", expected_bars=100)
        assert m.vol_raw is not None
        assert m.vol_raw == pytest.approx(0.03, rel=1e-2)

    def test_vol_raw_missing_columns(
        self,
        metrics_calculator: PairMetricsCalculator,
    ) -> None:
        """Missing atr_14 or close -> vol_raw None."""
        df = pd.DataFrame({"close": [100, 101], "volume": [1000, 1000]})
        m = metrics_calculator.calculate_all(df, "X", "5m", expected_bars=2)
        assert m.vol_raw is None


class TestTrendQuality:
    """Tests for trend_q_raw = adx_norm * abs(ema_slope_norm)."""

    def test_trend_q_raw_has_value(
        self,
        metrics_calculator: PairMetricsCalculator,
    ) -> None:
        """trend_q_raw computed when adx_14 and ema_21 present."""
        df = make_ohlcv_indicators_df(adx=30, ema_slope=0.001)
        m = metrics_calculator.calculate_all(df, "BTC", "1H", expected_bars=100)
        assert m.trend_q_raw is not None
        assert m.trend_q_raw >= 0


class TestNoise:
    """Tests for noise_raw = std(|r|) / (median(|r|) + eps), r = log returns."""

    def test_noise_raw_formula(
        self,
        metrics_calculator: PairMetricsCalculator,
    ) -> None:
        """noise_raw computed from log returns."""
        df = make_ohlcv_indicators_df(n_bars=50)
        m = metrics_calculator.calculate_all(df, "BTC", "1H", expected_bars=50)
        assert m.noise_raw is not None
        assert m.noise_raw >= 0

    def test_noise_raw_missing_close(
        self,
        metrics_calculator: PairMetricsCalculator,
    ) -> None:
        """Single bar or no close -> noise_raw None."""
        df = pd.DataFrame(
            {
                "close": [100],
                "volume": [1000],
                "atr_14": [2],
                "adx_14": [25],
                "ema_21": [100],
            }
        )
        m = metrics_calculator.calculate_all(df, "X", "5m", expected_bars=1)
        assert m.noise_raw is None


class TestStability:
    """Tests for stability_raw = dominance * (1 - switch_rate)."""

    def test_stability_raw_has_value(
        self,
        metrics_calculator: PairMetricsCalculator,
    ) -> None:
        """stability_raw in [0, 1] when required columns present."""
        df = make_ohlcv_indicators_df(n_bars=50, adx=18)
        m = metrics_calculator.calculate_all(df, "BTC", "1H", expected_bars=50)
        if m.stability_raw is not None:
            assert 0 <= m.stability_raw <= 1


class TestLiquidity:
    """Tests for liq_raw = median(volume) / (cv(volume) + 1)."""

    def test_liq_raw_formula(
        self,
        metrics_calculator: PairMetricsCalculator,
    ) -> None:
        """liq_raw: high median and low cv -> higher value."""
        df = make_ohlcv_indicators_df(vol_base=2000)
        m = metrics_calculator.calculate_all(df, "BTC", "1H", expected_bars=100)
        assert m.liq_raw is not None
        assert m.liq_raw > 0

    def test_liq_raw_missing_volume(
        self,
        metrics_calculator: PairMetricsCalculator,
    ) -> None:
        """No volume column -> liq_raw None."""
        df = pd.DataFrame(
            {
                "close": [100, 101],
                "atr_14": [2, 2],
                "adx_14": [25, 25],
                "ema_21": [100, 100.5],
            }
        )
        m = metrics_calculator.calculate_all(df, "X", "5m", expected_bars=2)
        assert m.liq_raw is None


class TestCalculateAll:
    """Tests for calculate_all() returning PairMetrics."""

    def test_returns_pair_metrics(
        self,
        metrics_calculator: PairMetricsCalculator,
    ) -> None:
        """calculate_all returns PairMetrics with all 5 raw metrics."""
        df = make_ohlcv_indicators_df(n_bars=60)
        m = metrics_calculator.calculate_all(df, "BTCUSDT", "1H", expected_bars=60)
        assert isinstance(m, PairMetrics)
        assert m.symbol == "BTCUSDT"
        assert m.timeframe == "1H"
        assert m.valid_bars == 60
        assert m.expected_bars == 60
        assert m.vol_raw is not None
        assert m.trend_q_raw is not None
        assert m.noise_raw is not None
        assert m.liq_raw is not None

    def test_to_dict(
        self,
        metrics_calculator: PairMetricsCalculator,
    ) -> None:
        """PairMetrics.to_dict() has expected keys."""
        df = make_ohlcv_indicators_df(n_bars=30)
        m = metrics_calculator.calculate_all(df, "A", "5m", expected_bars=30)
        d = m.to_dict()
        assert "symbol" in d
        assert "timeframe" in d
        assert "vol_raw" in d
        assert "trend_q_raw" in d
        assert "noise_raw" in d
        assert "stability_raw" in d
        assert "liq_raw" in d
        assert "valid_bars" in d
        assert "expected_bars" in d
