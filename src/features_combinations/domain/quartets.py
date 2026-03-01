QUARTETS = {
    "macd_rsi_adx_ema200": {
        "indicators": ["macd", "rsi14", "adx14", "ema200"],
        "roles": ["направление", "импульс", "сила", "ориентация"],
        "description": "MACD + RSI + ADX + EMA-200: trend stack",
    },
    "ema_ribbon_adx_rsi_vp_vwap": {
        "indicators": [
            "ema_8",
            "ema_13",
            "ema_21",
            "ema_34",
            "ema_55",
            "ema_89",
            "ema_144",
            "ema_233",
            "adx14",
            "rsi14",
            "vp_value_area_high",
            "vp_value_area_low",
            "vp_point_of_control",
            "vwap",
        ],
        "roles": ["объёмный фильтр"],
        "description": "EMA-Ribbon + ADX + RSI + VP/VWAP: расширенный объёмный фильтр",
    },
}
