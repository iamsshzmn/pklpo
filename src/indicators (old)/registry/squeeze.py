SQUEEZE_INDICATORS = ["ttm_squeeze_on", "ttm_squeeze_hist", "ttm_squeeze_value"]

SQUEEZE_CONFIG = {
    "ttm_squeeze_on": {
        "description": "TTM Squeeze On/Off (bool)",
        "requires": ["close", "high", "low"],
    },
    "ttm_squeeze_hist": {
        "description": "TTM Squeeze Histogram",
        "requires": ["close", "high", "low"],
    },
    "ttm_squeeze_value": {
        "description": "TTM Squeeze Value",
        "requires": ["close", "high", "low"],
    },
}
