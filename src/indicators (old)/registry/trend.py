TREND_INDICATORS = [
    "ichimoku_tenkan",
    "ichimoku_kijun",
    "ichimoku_senkou_a",
    "ichimoku_senkou_b",
    "ichimoku_chikou",
    "adx14",
    "adx_pos_di",
    "adx_neg_di",
]

TREND_CONFIG = {
    "ichimoku_tenkan": {
        "tenkan": 9,
        "description": "Ichimoku Tenkan-sen (Conversion Line, 9)",
        "requires": ["high", "low"],
    },
    "ichimoku_kijun": {
        "kijun": 26,
        "description": "Ichimoku Kijun-sen (Base Line, 26)",
        "requires": ["high", "low"],
    },
    "ichimoku_senkou_a": {
        "tenkan": 9,
        "kijun": 26,
        "senkou": 26,
        "description": "Ichimoku Senkou Span A (Leading Span A, 9, 26)",
        "requires": ["high", "low"],
    },
    "ichimoku_senkou_b": {
        "senkou_b": 52,
        "senkou": 26,
        "description": "Ichimoku Senkou Span B (Leading Span B, 52, 26)",
        "requires": ["high", "low"],
    },
    "ichimoku_chikou": {
        "chikou": 26,
        "description": "Ichimoku Chikou Span (Lagging Span, 26)",
        "requires": ["close"],
    },
    "adx14": {
        "period": 14,
        "description": "Average Directional Index (ADX, 14)",
        "requires": ["high", "low", "close"],
    },
    "adx_pos_di": {
        "period": 14,
        "description": "ADX Positive Directional Indicator (+DI, 14)",
        "requires": ["high", "low", "close"],
    },
    "adx_neg_di": {
        "period": 14,
        "description": "ADX Negative Directional Indicator (-DI, 14)",
        "requires": ["high", "low", "close"],
    },
}
