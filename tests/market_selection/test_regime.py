"""
Тесты для regime classifier.
"""

import pandas as pd
import pytest

from src.market_selection.application.config_projection import (
    build_regime_classifier_config,
)
from src.market_selection.config import MarketSelectionConfig
from src.market_selection.domain.regime import (
    GlobalRegime,
    RegimeClassifier,
    RegimeType,
    TFRegime,
)


@pytest.fixture
def regime_classifier():
    config = build_regime_classifier_config(MarketSelectionConfig())
    return RegimeClassifier(config)


def test_select_basket(regime_classifier):
    volume_data = pd.DataFrame(
        {
            "symbol": ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT", "ADA-USDT"],
            "volume_median": [1000000, 800000, 600000, 400000, 200000],
        }
    )

    basket = regime_classifier.select_basket(volume_data)
    assert len(basket) == 5
    assert basket[0] == "BTC-USDT"


def test_classify_single_tf_variants(regime_classifier):
    volatile = regime_classifier.classify_single_tf("1H", 20.0, 0.05, 0.0, 0.03)
    trend_up = regime_classifier.classify_single_tf("1H", 30.0, 0.02, 0.001, 0.03)
    trend_down = regime_classifier.classify_single_tf("1H", 30.0, 0.02, -0.001, 0.03)
    range_regime = regime_classifier.classify_single_tf("1H", 15.0, 0.01, 0.0, 0.03)

    assert volatile.regime == RegimeType.VOLATILE
    assert trend_up.regime == RegimeType.TREND_UP
    assert trend_down.regime == RegimeType.TREND_DOWN
    assert range_regime.regime == RegimeType.RANGE


def test_aggregate_basket_metrics(regime_classifier):
    basket_data = pd.DataFrame(
        {
            "symbol": ["BTC-USDT", "ETH-USDT", "SOL-USDT"],
            "volume_median": [1000000, 800000, 600000],
            "adx_median": [25.0, 30.0, 20.0],
            "atr_close_ratio": [0.02, 0.025, 0.015],
            "ema_slope": [0.001, -0.0005, 0.0008],
        }
    )

    agg = regime_classifier.aggregate_basket_metrics(basket_data)
    assert agg["adx"] > 0
    assert agg["atr_close"] > 0
    assert agg["ema_slope"] != 0


def test_aggregate_basket_metrics_empty(regime_classifier):
    agg = regime_classifier.aggregate_basket_metrics(pd.DataFrame())
    assert agg == {"adx": 20.0, "atr_close": 0.01, "ema_slope": 0.0}


def test_aggregate_across_tfs_volatile_priority(regime_classifier):
    tf_regimes = {
        "1D": TFRegime("1D", RegimeType.TREND_UP, 0.8, 30.0, 0.02, 0.001),
        "4H": TFRegime("4H", RegimeType.VOLATILE, 0.9, 20.0, 0.05, 0.0),
    }

    global_regime = regime_classifier.aggregate_across_tfs(tf_regimes)
    assert isinstance(global_regime, GlobalRegime)
    assert global_regime.regime == RegimeType.VOLATILE
    assert 0 <= global_regime.confidence <= 1


def test_aggregate_across_tfs_trend_direction(regime_classifier):
    tf_regimes = {
        "1D": TFRegime("1D", RegimeType.TREND_UP, 0.8, 30.0, 0.02, 0.001),
        "4H": TFRegime("4H", RegimeType.TREND_UP, 0.7, 28.0, 0.025, 0.0008),
        "1H": TFRegime("1H", RegimeType.TREND_UP, 0.6, 25.0, 0.02, 0.0005),
    }

    global_regime = regime_classifier.aggregate_across_tfs(tf_regimes)
    assert global_regime.regime == RegimeType.TREND_UP
    assert global_regime.strength > 0
    assert global_regime.confidence > 0


def test_compute_global_regime_includes_missing_tf_defaults(regime_classifier):
    basket_symbols = ["BTC-USDT"]
    tf_data = {
        "1D": pd.DataFrame(
            {
                "symbol": ["BTC-USDT"],
                "adx_median": [25.0],
                "atr_close_ratio": [0.02],
                "ema_slope": [0.001],
                "volume_median": [1000000],
            }
        )
    }

    global_regime = regime_classifier.compute_global_regime(
        basket_symbols=basket_symbols,
        tf_data=tf_data,
        atr_percentiles={"1D": 0.03},
    )

    assert set(global_regime.tf_regimes) == {"1D", "4H", "1H"}
    assert global_regime.basket_symbols == basket_symbols
    assert global_regime.basket_size == 1


def test_global_regime_to_dict_uses_default_tf_payloads():
    regime = GlobalRegime(
        regime=RegimeType.RANGE,
        strength=0.5,
        confidence=0.7,
    )

    payload = regime.to_dict()
    assert payload["global_regime"] == "RANGE"
    assert payload["regime_1d"] == "RANGE"
    assert payload["regime_4h"] == "RANGE"
    assert payload["regime_1h"] == "RANGE"
