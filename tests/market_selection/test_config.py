"""
Тесты для конфигурации market_selection.
"""

import pytest

from src.market_selection.config import (
    MarketSelectionConfig,
    QualityConfig,
    RegimeConfig,
    ScoringConfig,
    UniverseConfig,
    get_config,
    set_config,
)


def test_regime_config_defaults():
    """Тест значений по умолчанию для RegimeConfig."""
    config = RegimeConfig()
    assert config.basket_k == 20
    assert config.basket_volume_tf == "4H"
    assert config.basket_volume_window_days == 30
    assert config.adx_trend_threshold == 25
    assert config.adx_range_threshold == 18
    assert config.trend_up_threshold == 0.35
    assert config.trend_down_threshold == -0.35


def test_regime_config_validation():
    """Тест валидации RegimeConfig."""
    # basket_k должен быть в диапазоне [5, 50]
    with pytest.raises(Exception):
        RegimeConfig(basket_k=4)
    with pytest.raises(Exception):
        RegimeConfig(basket_k=51)

    # adx_trend_threshold должен быть в диапазоне [15, 40]
    with pytest.raises(Exception):
        RegimeConfig(adx_trend_threshold=14)
    with pytest.raises(Exception):
        RegimeConfig(adx_trend_threshold=41)


def test_quality_config_defaults():
    """Тест значений по умолчанию для QualityConfig."""
    config = QualityConfig()
    assert "5m" in config.thresholds
    assert "15m" in config.thresholds
    assert "1H" in config.thresholds
    assert "4H" in config.thresholds
    assert config.warmup_min_bars == 280
    assert config.gap_threshold_multiplier == 1.5


def test_quality_config_validation():
    """Тест валидации QualityConfig."""
    # warmup_min_bars должен быть >= 100
    with pytest.raises(Exception):
        QualityConfig(warmup_min_bars=99)

    # gap_threshold_multiplier должен быть в диапазоне [1.1, 3.0]
    with pytest.raises(Exception):
        QualityConfig(gap_threshold_multiplier=1.0)
    with pytest.raises(Exception):
        QualityConfig(gap_threshold_multiplier=3.1)


def test_scoring_config_defaults():
    """Тест значений по умолчанию для ScoringConfig."""
    config = ScoringConfig()
    assert sum(config.base_weights.values()) == pytest.approx(1.0, abs=1e-6)
    assert "vol" in config.base_weights
    assert "trend_q" in config.base_weights
    assert "noise" in config.base_weights
    assert "stability" in config.base_weights
    assert "liq" in config.base_weights
    assert "TREND_UP" in config.regime_deltas
    assert "TREND_DOWN" in config.regime_deltas
    assert "RANGE" in config.regime_deltas
    assert "VOLATILE" in config.regime_deltas


def test_universe_config_defaults():
    """Тест значений по умолчанию для UniverseConfig."""
    config = UniverseConfig()
    assert config.top_n == 30
    assert config.buffer == 10
    assert config.score_std_7d_max == 0.12
    assert config.score_std_30d_max == 0.18
    assert config.min_universe_hard == 5
    assert config.min_universe_soft == 10


def test_universe_config_validation():
    """Тест валидации UniverseConfig."""
    # top_n должен быть в диапазоне [10, 100]
    with pytest.raises(Exception):
        UniverseConfig(top_n=9)
    with pytest.raises(Exception):
        UniverseConfig(top_n=101)

    # buffer должен быть в диапазоне [5, 30]
    with pytest.raises(Exception):
        UniverseConfig(buffer=4)
    with pytest.raises(Exception):
        UniverseConfig(buffer=31)


def test_market_selection_config_defaults():
    """Тест значений по умолчанию для MarketSelectionConfig."""
    config = MarketSelectionConfig()
    assert config.selection_tfs == ["5m", "15m", "1H", "4H"]
    assert config.regime_tfs == ["1D", "4H", "1H"]
    assert isinstance(config.regime, RegimeConfig)
    assert isinstance(config.quality, QualityConfig)
    assert isinstance(config.scoring, ScoringConfig)
    assert isinstance(config.universe, UniverseConfig)


def test_config_hash():
    """Тест генерации хеша конфигурации."""
    config1 = MarketSelectionConfig()
    config2 = MarketSelectionConfig()
    config3 = MarketSelectionConfig(universe=UniverseConfig(top_n=50))

    hash1 = config1.config_hash()
    hash2 = config2.config_hash()
    hash3 = config3.config_hash()

    # Одинаковые конфигурации дают одинаковый хеш
    assert hash1 == hash2
    # Разные конфигурации дают разный хеш
    assert hash1 != hash3
    # Хеш имеет длину 16 символов
    assert len(hash1) == 16


def test_get_tf_window_ms():
    """Тест получения окна в миллисекундах."""
    config = MarketSelectionConfig()
    window_ms = config.get_tf_window_ms("1H")
    assert window_ms == 90 * 24 * 60 * 60 * 1000  # 90 дней для 1H


def test_get_tf_bar_ms():
    """Тест получения длительности бара в миллисекундах."""
    config = MarketSelectionConfig()
    assert config.get_tf_bar_ms("5m") == 5 * 60_000
    assert config.get_tf_bar_ms("1H") == 60 * 60_000
    assert config.get_tf_bar_ms("4H") == 4 * 60 * 60_000
    assert config.get_tf_bar_ms("1D") == 24 * 60 * 60_000


def test_get_quality_thresholds():
    """Тест получения порогов качества для таймфрейма."""
    config = MarketSelectionConfig()
    thresholds = config.get_quality_thresholds("5m")
    assert "fill_min" in thresholds
    assert "gap_max" in thresholds
    assert "lag_max_min" in thresholds

    # Для неизвестного таймфрейма должны быть дефолтные значения
    thresholds_unknown = config.get_quality_thresholds("unknown")
    assert thresholds_unknown["fill_min"] == 0.95
    assert thresholds_unknown["gap_max"] == 0.02
    assert thresholds_unknown["lag_max_min"] == 60


def test_get_config_singleton():
    """Тест singleton паттерна для get_config."""
    # Сброс singleton
    set_config(None)

    config1 = get_config()
    config2 = get_config()

    # Должен возвращаться один и тот же объект
    assert config1 is config2


def test_set_config():
    """Тест установки конфигурации."""
    custom_config = MarketSelectionConfig(universe=UniverseConfig(top_n=50))
    set_config(custom_config)

    retrieved = get_config()
    assert retrieved.universe.top_n == 50
    assert retrieved is custom_config

    # Восстановление дефолтной конфигурации
    set_config(None)
    default_config = get_config()
    assert default_config.universe.top_n == 30
