"""
Тесты для regime classifier (классификация режима рынка).
"""

import pandas as pd
import pytest

from src.market_selection.config import MarketSelectionConfig
from src.market_selection.domain.regime import (
    GlobalRegime,
    RegimeClassifier,
    RegimeType,
    TFRegime,
)


@pytest.fixture
def config():
    """Фикстура конфигурации."""
    return MarketSelectionConfig()


@pytest.fixture
def regime_classifier(config):
    """Фикстура regime classifier."""
    return RegimeClassifier(config)


def test_select_basket(regime_classifier):
    """Тест выбора корзины символов."""
    volume_data = pd.DataFrame({
        "symbol": ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT", "ADA-USDT"],
        "volume_median": [1000000, 800000, 600000, 400000, 200000],
    })

    basket = regime_classifier.select_basket(volume_data)
    assert len(basket) == min(5, regime_classifier.regime_config.basket_k)
    assert "BTC-USDT" in basket
    assert basket[0] == "BTC-USDT"  # Самый большой объем


def test_select_basket_small_universe(regime_classifier):
    """Тест выбора корзины при малом количестве символов."""
    volume_data = pd.DataFrame({
        "symbol": ["BTC-USDT", "ETH-USDT"],
        "volume_median": [1000000, 800000],
    })

    basket = regime_classifier.select_basket(volume_data)
    # Если символов меньше basket_k, возвращаем все
    assert len(basket) == 2


def test_classify_single_tf_volatile(regime_classifier):
    """Тест классификации режима VOLATILE."""
    tf_regime = regime_classifier.classify_single_tf(
        timeframe="1H",
        adx_median=20.0,
        atr_close_ratio=0.05,
        ema_slope=0.0,
        atr_p80=0.03,  # atr_close_ratio (0.05) > atr_p80 (0.03)
    )

    assert tf_regime.regime == RegimeType.VOLATILE
    assert tf_regime.strength > 0


def test_classify_single_tf_trend_up(regime_classifier):
    """Тест классификации режима TREND_UP."""
    tf_regime = regime_classifier.classify_single_tf(
        timeframe="1H",
        adx_median=30.0,  # >= adx_trend_threshold (25)
        atr_close_ratio=0.02,
        ema_slope=0.001,  # Положительный наклон
        atr_p80=0.03,
    )

    assert tf_regime.regime == RegimeType.TREND_UP
    assert tf_regime.strength > 0


def test_classify_single_tf_trend_down(regime_classifier):
    """Тест классификации режима TREND_DOWN."""
    tf_regime = regime_classifier.classify_single_tf(
        timeframe="1H",
        adx_median=30.0,
        atr_close_ratio=0.02,
        ema_slope=-0.001,  # Отрицательный наклон
        atr_p80=0.03,
    )

    assert tf_regime.regime == RegimeType.TREND_DOWN
    assert tf_regime.strength > 0


def test_classify_single_tf_range(regime_classifier):
    """Тест классификации режима RANGE."""
    tf_regime = regime_classifier.classify_single_tf(
        timeframe="1H",
        adx_median=15.0,  # < adx_range_threshold (18)
        atr_close_ratio=0.01,
        ema_slope=0.0,
        atr_p80=0.03,
    )

    assert tf_regime.regime == RegimeType.RANGE
    assert tf_regime.strength > 0


def test_aggregate_basket_metrics(regime_classifier):
    """Тест агрегации метрик корзины."""
    basket_data = pd.DataFrame({
        "symbol": ["BTC-USDT", "ETH-USDT", "SOL-USDT"],
        "volume_median": [1000000, 800000, 600000],
        "adx_median": [25.0, 30.0, 20.0],
        "atr_close_ratio": [0.02, 0.025, 0.015],
        "ema_slope": [0.001, -0.0005, 0.0008],
    })

    agg = regime_classifier.aggregate_basket_metrics(basket_data)

    assert "adx" in agg
    assert "atr_close" in agg
    assert "ema_slope" in agg
    assert agg["adx"] > 0
    assert agg["atr_close"] > 0


def test_aggregate_basket_metrics_empty(regime_classifier):
    """Тест агрегации пустой корзины."""
    empty_df = pd.DataFrame()
    agg = regime_classifier.aggregate_basket_metrics(empty_df)

    assert agg["adx"] == 20.0
    assert agg["atr_close"] == 0.01
    assert agg["ema_slope"] == 0.0


def test_aggregate_across_tfs(regime_classifier):
    """Тест агрегации режимов по таймфреймам."""
    tf_regimes = {
        "1D": TFRegime(
            timeframe="1D",
            regime=RegimeType.TREND_UP,
            strength=0.8,
            adx_median=30.0,
            atr_close_ratio=0.02,
            ema_slope=0.001,
        ),
        "4H": TFRegime(
            timeframe="4H",
            regime=RegimeType.TREND_UP,
            strength=0.7,
            adx_median=28.0,
            atr_close_ratio=0.025,
            ema_slope=0.0008,
        ),
        "1H": TFRegime(
            timeframe="1H",
            regime=RegimeType.TREND_UP,
            strength=0.6,
            adx_median=25.0,
            atr_close_ratio=0.02,
            ema_slope=0.0005,
        ),
    }

    global_regime = regime_classifier.aggregate_across_tfs(tf_regimes)

    assert isinstance(global_regime, GlobalRegime)
    assert global_regime.regime == RegimeType.TREND_UP
    assert global_regime.strength > 0
    assert global_regime.confidence > 0
    assert len(global_regime.tf_regimes) == 3


def test_aggregate_across_tfs_volatile_priority(regime_classifier):
    """Тест: VOLATILE режим имеет приоритет."""
    tf_regimes = {
        "1D": TFRegime(
            timeframe="1D",
            regime=RegimeType.TREND_UP,
            strength=0.8,
            adx_median=30.0,
            atr_close_ratio=0.02,
            ema_slope=0.001,
        ),
        "4H": TFRegime(
            timeframe="4H",
            regime=RegimeType.VOLATILE,
            strength=0.9,
            adx_median=20.0,
            atr_close_ratio=0.05,
            ema_slope=0.0,
        ),
    }

    global_regime = regime_classifier.aggregate_across_tfs(tf_regimes)

    # VOLATILE должен иметь приоритет
    assert global_regime.regime == RegimeType.VOLATILE


def test_compute_global_regime(regime_classifier):
    """Тест вычисления глобального режима."""
    basket_symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]

    tf_data = {
        "1D": pd.DataFrame({
            "symbol": basket_symbols,
            "adx_median": [25.0, 30.0, 20.0],
            "atr_close_ratio": [0.02, 0.025, 0.015],
            "ema_slope": [0.001, -0.0005, 0.0008],
            "volume_median": [1000000, 800000, 600000],
        }),
        "4H": pd.DataFrame({
            "symbol": basket_symbols,
            "adx_median": [28.0, 32.0, 22.0],
            "atr_close_ratio": [0.022, 0.027, 0.017],
            "ema_slope": [0.0012, -0.0006, 0.0009],
            "volume_median": [1000000, 800000, 600000],
        }),
        "1H": pd.DataFrame({
            "symbol": basket_symbols,
            "adx_median": [24.0, 29.0, 19.0],
            "atr_close_ratio": [0.021, 0.026, 0.016],
            "ema_slope": [0.0011, -0.0005, 0.0007],
            "volume_median": [1000000, 800000, 600000],
        }),
    }

    atr_percentiles = {"1D": 0.03, "4H": 0.03, "1H": 0.03}

    global_regime = regime_classifier.compute_global_regime(
        basket_symbols, tf_data, atr_percentiles
    )

    assert isinstance(global_regime, GlobalRegime)
    assert global_regime.basket_size == 3
    assert len(global_regime.basket_symbols) == 3
    assert global_regime.regime in RegimeType


def test_compute_global_regime_missing_tf(regime_classifier):
    """Тест вычисления режима при отсутствии данных для таймфрейма."""
    basket_symbols = ["BTC-USDT"]
    tf_data = {
        "1D": pd.DataFrame({
            "symbol": ["BTC-USDT"],
            "adx_median": [25.0],
            "atr_close_ratio": [0.02],
            "ema_slope": [0.001],
            "volume_median": [1000000],
        }),
        # Отсутствует 4H и 1H
    }

    atr_percentiles = {"1D": 0.03}

    global_regime = regime_classifier.compute_global_regime(
        basket_symbols, tf_data, atr_percentiles
    )

    # Должен использоваться дефолтный режим RANGE для отсутствующих TF
    assert isinstance(global_regime, GlobalRegime)
    assert "1D" in global_regime.tf_regimes
    assert "4H" in global_regime.tf_regimes
    assert "1H" in global_regime.tf_regimes
