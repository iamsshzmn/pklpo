"""
Конфигурация параметров для системы сигналов.
"""

from pathlib import Path
from typing import Any

import yaml

# Пороги для индикаторов
THRESHOLDS = {
    # RSI
    "rsi_buy": 30,
    "rsi_sell": 70,
    # ADX
    "adx_threshold": 25,
    # Stochastic
    "stoch_k_buy": 20,
    "stoch_k_sell": 80,
    # Bollinger Bands (в процентах от ширины полос)
    "bb_touch_threshold": 0.1,
    # Keltner Channel (в процентах от ширины канала)
    "kc_touch_threshold": 0.1,
    # Общие пороги
    "min_score_for_buy": 3,
    "min_score_for_sell": -3,
}

# Веса правил (влияние на финальный сигнал)
RULE_WEIGHTS = {
    # Трендовые правила
    "ema21_sma50": 1.0,
    "sma50_sma200": 2.0,  # Более важный - долгосрочный тренд
    "macd": 1.5,
    "adx14": 1.2,
    "ichimoku": 1.3,
    # Осцилляторы
    "rsi14": 1.0,
    "bollinger": 1.1,
    "stochastic": 1.0,
    "keltner": 1.1,
    # Объемные
    "obv_cmf": 0.8,  # Менее важный
}

# Стратегии (предустановленные конфигурации)
STRATEGIES = {
    "conservative": {
        "min_score_for_buy": 4,
        "min_score_for_sell": -4,
        "rule_weights": {
            "sma50_sma200": 2.5,  # Больше веса долгосрочному тренду
            "macd": 1.8,
            "adx14": 1.5,
        },
    },
    "aggressive": {
        "min_score_for_buy": 2,
        "min_score_for_sell": -2,
        "rule_weights": {
            "rsi14": 1.3,
            "stochastic": 1.2,
            "bollinger": 1.3,
        },
    },
    "balanced": {
        "min_score_for_buy": 3,
        "min_score_for_sell": -3,
        "rule_weights": RULE_WEIGHTS.copy(),
    },
}


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """Загружает конфигурацию из YAML файла."""
    if config_path is None:
        return {
            "thresholds": THRESHOLDS,
            "rule_weights": RULE_WEIGHTS,
            "strategies": STRATEGIES,
        }

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Конфигурационный файл не найден: {config_path}")

    with open(config_file, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config: dict[str, Any], config_path: str):
    """Сохраняет конфигурацию в YAML файл."""
    config_file = Path(config_path)
    config_file.parent.mkdir(parents=True, exist_ok=True)

    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


def get_threshold(key: str, default: Any = None) -> Any:
    """Получает значение порога по ключу."""
    return THRESHOLDS.get(key, default)


def get_rule_weight(rule_name: str, default: float = 1.0) -> float:
    """Получает вес правила по имени."""
    return RULE_WEIGHTS.get(rule_name, default)


def get_strategy_config(strategy_name: str) -> dict[str, Any]:
    """Получает конфигурацию стратегии."""
    return STRATEGIES.get(strategy_name, STRATEGIES["balanced"])
