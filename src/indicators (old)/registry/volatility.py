VOL_INDICATORS = [
    "bb_upper",
    "bb_middle",
    "bb_lower",
    "kc_upper",
    "kc_middle",
    "kc_lower",
    "atr14",
]

VOL_CONFIG = {
    "bb_upper": {
        "period": 20,
        "std_dev": 2,
        "description": "Bollinger Bands Upper (20, 2)",
        "requires": ["close"],
    },
    "bb_middle": {
        "period": 20,
        "std_dev": 2,
        "description": "Bollinger Bands Middle (20, 2)",
        "requires": ["close"],
    },
    "bb_lower": {
        "period": 20,
        "std_dev": 2,
        "description": "Bollinger Bands Lower (20, 2)",
        "requires": ["close"],
    },
    "kc_upper": {
        "length": 20,
        "mult": 2,
        "description": "Keltner Channel Upper (20, 2)",
        "requires": ["high", "low", "close"],
    },
    "kc_middle": {
        "length": 20,
        "mult": 2,
        "description": "Keltner Channel Middle (20, 2)",
        "requires": ["high", "low", "close"],
    },
    "kc_lower": {
        "length": 20,
        "mult": 2,
        "description": "Keltner Channel Lower (20, 2)",
        "requires": ["high", "low", "close"],
    },
    "atr14": {
        "period": 14,
        "description": "Average True Range (14 periods)",
        "requires": ["high", "low", "close"],
    },
}
