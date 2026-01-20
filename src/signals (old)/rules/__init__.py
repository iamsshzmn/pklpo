"""
Пакет с правилами для генерации торговых сигналов.
"""

from .oscillator_rules import *
from .trend_rules import *
from .volume_rules import *

# Словарь всех правил для удобного доступа
RULES = {
    # Трендовые правила
    "ema21_sma50": rule_ema21_sma50,
    "sma50_sma200": rule_sma50_sma200,
    "macd": rule_macd,
    "adx14": rule_adx14,
    "ichimoku": rule_ichimoku,
    # Осцилляторы
    "rsi14": rule_rsi14,
    "bollinger": rule_bollinger,
    "stochastic": rule_stochastic,
    "keltner": rule_keltner,
    # Объёмные индикаторы
    "volume_obv_cmf": rule_volume_obv_cmf,
}

__all__ = [
    "RULES",
    # Трендовые правила
    "rule_ema21_sma50",
    "rule_sma50_sma200",
    "rule_macd",
    "rule_adx14",
    "rule_ichimoku",
    # Осцилляторы
    "rule_rsi14",
    "rule_bollinger",
    "rule_stochastic",
    "rule_keltner",
    # Объёмные индикаторы
    "rule_volume_obv_cmf",
]
