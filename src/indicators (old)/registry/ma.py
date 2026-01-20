MA_INDICATORS = [
    "ema12",
    "ema21",
    "ema26",
    "ema50",
    "ema200",
    "sma34",
    "sma50",
    "sma200",
    "ema_8",
    "ema_13",
    "ema_21",
    "ema_34",
    "ema_55",
    "ema_89",
    "ema_144",
    "ema_233",
]

MA_CONFIG = {
    "ema12": {
        "period": 12,
        "description": "Exponential Moving Average (12 periods)",
        "requires": ["close"],
    },
    "ema21": {
        "period": 21,
        "description": "Exponential Moving Average (21 periods)",
        "requires": ["close"],
    },
    "ema26": {
        "period": 26,
        "description": "Exponential Moving Average (26 periods)",
        "requires": ["close"],
    },
    "ema50": {
        "period": 50,
        "description": "Exponential Moving Average (50 periods)",
        "requires": ["close"],
    },
    "ema200": {
        "period": 200,
        "description": "Exponential Moving Average (200 periods)",
        "requires": ["close"],
    },
    "sma34": {
        "period": 34,
        "description": "Simple Moving Average (34 periods)",
        "requires": ["close"],
    },
    "sma50": {
        "period": 50,
        "description": "Simple Moving Average (50 periods)",
        "requires": ["close"],
    },
    "sma200": {
        "period": 200,
        "description": "Simple Moving Average (200 periods)",
        "requires": ["close"],
    },
    # EMA-Ribbon
    **{
        f"ema_{p}": {
            "period": p,
            "description": f"EMA Ribbon ({p})",
            "requires": ["close"],
        }
        for p in [8, 13, 21, 34, 55, 89, 144, 233]
    },
}
