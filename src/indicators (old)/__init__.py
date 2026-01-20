"""
Система технических индикаторов - модульная система для расчета технических индикаторов.
"""

from .calc_indicators import (
    fetch_ohlcv_df,
    get_symbol_timeframes_to_update,
    main,
    upsert_indicators,
)
from .indicator_groups import (
    calc_ma_indicators,
    calc_oscillator_indicators,
    calc_squeeze_indicators,
    calc_trend_indicators,
    calc_volatility_indicators,
    calc_volume_indicators,
)
from .indicator_utils import calc_indicators
from .registry import AVAILABLE_INDICATORS, INDICATOR_CONFIG

__all__ = [
    # Основные функции
    "main",
    "get_symbol_timeframes_to_update",
    "fetch_ohlcv_df",
    "upsert_indicators",
    "calc_indicators",
    # Реестр индикаторов
    "AVAILABLE_INDICATORS",
    "INDICATOR_CONFIG",
    # Группы расчета
    "calc_ma_indicators",
    "calc_oscillator_indicators",
    "calc_volatility_indicators",
    "calc_volume_indicators",
    "calc_trend_indicators",
    "calc_squeeze_indicators",
]
