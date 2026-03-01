TRIOS = {
    "bbands_kc_ttm": {
        "indicators": [
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "kc_upper",
            "kc_middle",
            "kc_lower",
            "ttm_squeeze_on",
            "ttm_squeeze_hist",
            "ttm_squeeze_value",
        ],
        "roles": ["статус сжатия", "направление"],
        "description": "Bollinger Bands + Keltner Channel + Momentum-Histogram (TTM Squeeze): статус сжатия + направление",
    },
    "ichimoku_macd_rsi": {
        "indicators": [
            "ichimoku_tenkan",
            "ichimoku_kijun",
            "ichimoku_senkou_a",
            "ichimoku_senkou_b",
            "macd",
            "rsi14",
        ],
        "roles": ["структура тренда", "импульс", "фильтр"],
        "description": "Ichimoku + MACD + RSI: структура тренда + импульс + фильтр",
    },
    "macd_rsi_bbands": {
        "indicators": ["macd", "rsi14", "bb_upper", "bb_middle", "bb_lower"],
        "roles": ["импульс", "фильтр", "волатильность"],
        "description": "MACD + RSI + Bollinger Bands: популярный публичный скрипт на TradingView",
    },
}
