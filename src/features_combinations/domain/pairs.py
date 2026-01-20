PAIRS = {
    "macd_rsi": {
        "indicators": ["macd", "rsi14"],
        "roles": ["импульс", "перекуп/перепрод"],
        "description": "MACD + RSI: импульс + перекуп/перепрод",
    },
    "macd_ichimoku": {
        "indicators": [
            "macd",
            "ichimoku_tenkan",
            "ichimoku_kijun",
            "ichimoku_senkou_a",
            "ichimoku_senkou_b",
        ],
        "roles": ["импульс", "тренд-структура"],
        "description": "MACD + Ichimoku: тренд-структура облака + импульс",
    },
    "ema_adx": {
        "indicators": ["ema12", "ema26", "ema50", "ema200", "adx14"],
        "roles": ["направление тренда", "сила тренда"],
        "description": "EMA (12/26/50/200) + ADX: направление тренда + его сила",
    },
    "sma_stoch": {
        "indicators": ["sma34", "sma200", "stoch_k", "stoch_d"],
        "roles": ["долгосрочный тренд", "краткосрочный импульс"],
        "description": "34/200-SMA cross + Stochastic (9-3-3): долгосрочный тренд + краткосрочный импульс",
    },
    "rsi_obv": {
        "indicators": ["rsi14", "obv"],
        "roles": ["импульс цены", "подтверждение объёмом"],
        "description": "RSI + OBV: импульс цены + подтверждение объёмом",
    },
    "rsi_cmf": {
        "indicators": ["rsi14", "cmf"],
        "roles": ["импульс цены", "денежный поток"],
        "description": "RSI + CMF: импульс цены + денежный поток (CMF)",
    },
    "rsi_vwap_vp": {
        "indicators": [
            "rsi14",
            "vwap",
            "vp_value_area_high",
            "vp_value_area_low",
            "vp_point_of_control",
        ],
        "roles": ["импульс", "объём-ориентированный уровень"],
        "description": "RSI + VWAP-Deviation / Volume Profile: импульс + объём-ориентированный уровень",
    },
    "obv_macd": {
        "indicators": ["obv", "macd"],
        "roles": ["объём-давление", "импульс"],
        "description": "OBV + MACD: объём-давление + импульс",
    },
    "macd_bbands": {
        "indicators": ["macd", "bb_upper", "bb_middle", "bb_lower"],
        "roles": ["импульс", "волатильность-канал"],
        "description": "MACD + Bollinger Bands: импульс + волатильность-канал",
    },
}
