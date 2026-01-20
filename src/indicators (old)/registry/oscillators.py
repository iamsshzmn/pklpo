OSC_INDICATORS = [
    "rsi14",
    "stoch_k",
    "stoch_d",
    "macd",
    "macd_signal",
    "macd_histogram",
    "adx14",
    "adx_pos_di",
    "adx_neg_di",
]

OSC_CONFIG = {
    "rsi14": {
        "period": 14,
        "description": "Relative Strength Index (14 periods)",
        "requires": ["close"],
    },
    "stoch_k": {
        "k_period": 14,
        "d_period": 3,
        "description": "Stochastic %K (14, 3)",
        "requires": ["high", "low", "close"],
    },
    "stoch_d": {
        "k_period": 14,
        "d_period": 3,
        "description": "Stochastic %D (14, 3)",
        "requires": ["high", "low", "close"],
    },
    "macd": {
        "fast_period": 12,
        "slow_period": 26,
        "signal_period": 9,
        "description": "MACD (12, 26, 9)",
        "requires": ["close"],
    },
    "macd_signal": {
        "fast_period": 12,
        "slow_period": 26,
        "signal_period": 9,
        "description": "MACD Signal Line",
        "requires": ["close"],
    },
    "macd_histogram": {
        "fast_period": 12,
        "slow_period": 26,
        "signal_period": 9,
        "description": "MACD Histogram",
        "requires": ["close"],
    },
    "adx14": {
        "period": 14,
        "description": "ADX (Average Directional Index, 14)",
        "requires": ["high", "low", "close"],
    },
    "adx_pos_di": {
        "period": 14,
        "description": "+DI (Positive Directional Indicator, 14)",
        "requires": ["high", "low", "close"],
    },
    "adx_neg_di": {
        "period": 14,
        "description": "-DI (Negative Directional Indicator, 14)",
        "requires": ["high", "low", "close"],
    },
}
