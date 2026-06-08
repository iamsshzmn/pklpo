"""
Unit tests for Market Selection Regime (GlobalRegime, RegimeClassifier).

Covers: basket selection, per-TF classification (TREND_UP/DOWN, RANGE, VOLATILE),
aggregation across TFs (weights 1D:0.5, 4H:0.3, 1H:0.2), direction_score, volatile_flag.
"""

from __future__ import annotations

import pandas as pd

from src.market_selection.domain.regime import (
    RegimeClassifier,
    RegimeType,
    TFRegime,
)


class TestSelectBasket:
    """Tests for RegimeClassifier.select_basket()."""

    def test_top_k_by_volume(
        self,
        regime_classifier: RegimeClassifier,
    ) -> None:
        """Returns top-K symbols by volume_median descending."""
        volume_data = pd.DataFrame({
            "symbol": ["A", "B", "C", "D", "E", "F"],
            "volume_median": [1000, 800, 600, 400, 200, 100],
        })
        basket = regime_classifier.select_basket(volume_data)
        assert len(basket) == min(6, regime_classifier.config.basket_k)
        assert basket[0] == "A"
        assert basket[1] == "B"

    def test_less_than_k_returns_all(
        self,
        regime_classifier: RegimeClassifier,
    ) -> None:
        """When len(volume_data) <= K, return all symbols."""
        volume_data = pd.DataFrame({
            "symbol": ["A", "B", "C"],
            "volume_median": [100, 80, 60],
        })
        basket = regime_classifier.select_basket(volume_data)
        assert len(basket) == 3
        assert set(basket) == {"A", "B", "C"}


class TestClassifySingleTf:
    """Tests for RegimeClassifier.classify_single_tf()."""

    def test_volatile_when_atr_above_p80(
        self,
        regime_classifier: RegimeClassifier,
    ) -> None:
        """ATR/close > atr_p80 -> VOLATILE."""
        result = regime_classifier.classify_single_tf(
            timeframe="4H",
            adx_median=30,
            atr_close_ratio=0.05,
            ema_slope=0.001,
            atr_p80=0.03,
        )
        assert result.regime == RegimeType.VOLATILE

    def test_trend_up_when_adx_high_positive_slope(
        self,
        regime_classifier: RegimeClassifier,
    ) -> None:
        """ADX >= 25 and ema_slope > 0 -> TREND_UP."""
        result = regime_classifier.classify_single_tf(
            timeframe="4H",
            adx_median=30,
            atr_close_ratio=0.01,
            ema_slope=0.001,
            atr_p80=0.05,
        )
        assert result.regime == RegimeType.TREND_UP

    def test_trend_down_when_adx_high_negative_slope(
        self,
        regime_classifier: RegimeClassifier,
    ) -> None:
        """ADX >= 25 and ema_slope < 0 -> TREND_DOWN."""
        result = regime_classifier.classify_single_tf(
            timeframe="4H",
            adx_median=30,
            atr_close_ratio=0.01,
            ema_slope=-0.001,
            atr_p80=0.05,
        )
        assert result.regime == RegimeType.TREND_DOWN

    def test_range_when_adx_low(
        self,
        regime_classifier: RegimeClassifier,
    ) -> None:
        """ADX < 18 -> RANGE."""
        result = regime_classifier.classify_single_tf(
            timeframe="4H",
            adx_median=15,
            atr_close_ratio=0.01,
            ema_slope=0.0,
            atr_p80=0.05,
        )
        assert result.regime == RegimeType.RANGE


class TestAggregateBasketMetrics:
    """Tests for RegimeClassifier.aggregate_basket_metrics()."""

    def test_weighted_aggregation(
        self,
        regime_classifier: RegimeClassifier,
    ) -> None:
        """Returns adx, atr_close, ema_slope from weighted aggregation."""
        basket_data = pd.DataFrame({
            "symbol": ["A", "B"],
            "volume_median": [1000, 500],
            "adx_median": [30, 20],
            "atr_close_ratio": [0.02, 0.01],
            "ema_slope": [0.001, -0.0005],
        })
        agg = regime_classifier.aggregate_basket_metrics(basket_data)
        assert "adx" in agg
        assert "atr_close" in agg
        assert "ema_slope" in agg
        assert 15 <= agg["adx"] <= 35
        assert 0.005 <= agg["atr_close"] <= 0.03

    def test_empty_returns_defaults(
        self,
        regime_classifier: RegimeClassifier,
    ) -> None:
        """Empty basket returns default metrics."""
        basket_data = pd.DataFrame(
            columns=["symbol", "volume_median", "adx_median", "atr_close_ratio", "ema_slope"]
        )
        agg = regime_classifier.aggregate_basket_metrics(basket_data)
        assert agg["adx"] == 20.0
        assert agg["atr_close"] == 0.01
        assert agg["ema_slope"] == 0.0


class TestAggregateAcrossTfs:
    """Tests for RegimeClassifier.aggregate_across_tfs()."""

    def test_trend_up_when_direction_above_threshold(
        self,
        regime_classifier: RegimeClassifier,
    ) -> None:
        """direction_score >= 0.35 -> TREND_UP."""
        tf_regimes = {
            "1D": TFRegime("1D", RegimeType.TREND_UP, 0.8, 30, 0.02, 0.001),
            "4H": TFRegime("4H", RegimeType.TREND_UP, 0.7, 28, 0.015, 0.0008),
            "1H": TFRegime("1H", RegimeType.RANGE, 0.3, 20, 0.01, 0.0),
        }
        global_regime = regime_classifier.aggregate_across_tfs(tf_regimes)
        assert global_regime.regime == RegimeType.TREND_UP
        assert global_regime.strength >= 0
        assert global_regime.confidence >= 0

    def test_trend_down_when_direction_below_threshold(
        self,
        regime_classifier: RegimeClassifier,
    ) -> None:
        """direction_score <= -0.35 -> TREND_DOWN."""
        tf_regimes = {
            "1D": TFRegime("1D", RegimeType.TREND_DOWN, 0.8, 30, 0.02, -0.001),
            "4H": TFRegime("4H", RegimeType.TREND_DOWN, 0.7, 28, 0.015, -0.0008),
            "1H": TFRegime("1H", RegimeType.RANGE, 0.3, 20, 0.01, 0.0),
        }
        global_regime = regime_classifier.aggregate_across_tfs(tf_regimes)
        assert global_regime.regime == RegimeType.TREND_DOWN

    def test_volatile_when_any_tf_volatile(
        self,
        regime_classifier: RegimeClassifier,
    ) -> None:
        """If any TF is VOLATILE -> global VOLATILE."""
        tf_regimes = {
            "1D": TFRegime("1D", RegimeType.RANGE, 0.5, 20, 0.01, 0.0),
            "4H": TFRegime("4H", RegimeType.VOLATILE, 0.9, 25, 0.05, 0.0),
            "1H": TFRegime("1H", RegimeType.RANGE, 0.5, 18, 0.01, 0.0),
        }
        global_regime = regime_classifier.aggregate_across_tfs(tf_regimes)
        assert global_regime.regime == RegimeType.VOLATILE

    def test_range_when_no_trend_no_volatile(
        self,
        regime_classifier: RegimeClassifier,
    ) -> None:
        """All RANGE and direction in (-0.35, 0.35) -> RANGE."""
        tf_regimes = {
            "1D": TFRegime("1D", RegimeType.RANGE, 0.5, 15, 0.01, 0.0),
            "4H": TFRegime("4H", RegimeType.RANGE, 0.5, 17, 0.01, 0.0),
            "1H": TFRegime("1H", RegimeType.RANGE, 0.5, 16, 0.01, 0.0),
        }
        global_regime = regime_classifier.aggregate_across_tfs(tf_regimes)
        assert global_regime.regime == RegimeType.RANGE


class TestComputeGlobalRegime:
    """Tests for RegimeClassifier.compute_global_regime()."""

    def test_compute_global_regime_with_basket(
        self,
        regime_classifier: RegimeClassifier,
    ) -> None:
        """Full flow: basket symbols + tf_data + atr_percentiles -> GlobalRegime."""
        basket_symbols = ["A", "B"]
        tf_data = {
            "1D": pd.DataFrame({
                "symbol": ["A", "B"],
                "adx_median": [25, 22],
                "atr_close_ratio": [0.015, 0.012],
                "ema_slope": [0.0005, 0.0003],
                "volume_median": [1000, 800],
            }),
            "4H": pd.DataFrame({
                "symbol": ["A", "B"],
                "adx_median": [26, 23],
                "atr_close_ratio": [0.014, 0.013],
                "ema_slope": [0.0004, 0.0002],
                "volume_median": [1000, 800],
            }),
            "1H": pd.DataFrame({
                "symbol": ["A", "B"],
                "adx_median": [24, 21],
                "atr_close_ratio": [0.013, 0.011],
                "ema_slope": [0.0003, 0.0001],
                "volume_median": [1000, 800],
            }),
        }
        atr_percentiles = {"1D": 0.02, "4H": 0.02, "1H": 0.02}
        global_regime = regime_classifier.compute_global_regime(
            basket_symbols, tf_data, atr_percentiles
        )
        assert global_regime.regime in (
            RegimeType.TREND_UP,
            RegimeType.TREND_DOWN,
            RegimeType.RANGE,
            RegimeType.VOLATILE,
        )
        assert global_regime.basket_size == 2
        assert global_regime.basket_symbols == basket_symbols
        assert len(global_regime.tf_regimes) == 3
