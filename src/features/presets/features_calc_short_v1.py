"""
Features Calc Short v1 Feature Preset - минимальный набор для features_calc_short DAG.

24 индикатора, разделённые на категории:
- Context (старшие ТФ): 7 индикаторов
- Triggers (младшие ТФ): 8 индикаторов
- Volatility/Risk: 4 индикатора
- Volume: 3 индикатора
- PA Filters: 2 индикатора
"""

FEATURES_CALC_SHORT_SPECS = [
    # Context (старшие ТФ)
    "ema_21",
    "ema_55",
    "supertrend_direction",  # только direction, не значение
    "adx_14",
    "chop",
    "dc_upper",  # Donchian upper
    "dc_lower",  # Donchian lower
    # Triggers (младшие ТФ)
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_histogram",
    "ppo",
    "tsi",
    "stoch_k",
    "stoch_d",
    # Volatility/Risk
    "atr_14",
    "natr_14",
    "kc_upper",  # Keltner Channels
    "kc_lower",
    # Volume
    "obv",
    "cmf",
    "mfi",
    # PA Filters
    "ha_open",  # Heikin Ashi (для фильтра тренда)
    "ha_close",
]

# Разделение на категории (для логики)
CONTEXT_FEATURES = [
    "ema_21",
    "ema_55",
    "supertrend_direction",
    "adx_14",
    "chop",
    "dc_upper",
    "dc_lower",
]

TRIGGER_FEATURES = [
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_histogram",
    "ppo",
    "tsi",
    "stoch_k",
    "stoch_d",
]
