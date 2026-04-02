"""
Features Calc Short v1 Feature Preset - minimal set for the features_calc_short DAG.

24 indicators, divided into categories:
- Context (higher timeframes): 7 indicators
- Triggers (lower timeframes): 8 indicators
- Volatility/Risk: 4 indicators
- Volume: 3 indicators
- PA Filters: 2 indicators
"""

FEATURES_CALC_SHORT_SPECS = [
    # Context (higher timeframes)
    "ema_21",
    "ema_55",
    "supertrend_direction",  # direction only, not value
    "adx_14",
    "chop",
    "dc_upper",  # Donchian upper
    "dc_lower",  # Donchian lower
    # Triggers (lower timeframes)
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
    "ha_open",  # Heikin Ashi (trend filter)
    "ha_close",
]

# Category splits (for logic)
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
