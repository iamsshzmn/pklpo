VOLU_INDICATORS = [
    "obv",
    "cmf",
    "vwap",
    "vp_value_area_high",
    "vp_value_area_low",
    "vp_point_of_control",
    "volume_sma20",
]

VOLU_CONFIG = {
    "obv": {"description": "On-Balance Volume (OBV)", "requires": ["close", "volume"]},
    "cmf": {
        "period": 20,
        "description": "Chaikin Money Flow (CMF, 20)",
        "requires": ["high", "low", "close", "volume"],
    },
    "vwap": {
        "description": "Volume Weighted Average Price (VWAP)",
        "requires": ["high", "low", "close", "volume"],
    },
    "vp_value_area_high": {
        "description": "Volume Profile Value Area High (VAH)",
        "requires": ["close", "volume"],
    },
    "vp_value_area_low": {
        "description": "Volume Profile Value Area Low (VAL)",
        "requires": ["close", "volume"],
    },
    "vp_point_of_control": {
        "description": "Volume Profile Point of Control (POC)",
        "requires": ["close", "volume"],
    },
    "volume_sma20": {
        "period": 20,
        "description": "Volume Simple Moving Average (20 periods)",
        "requires": ["volume"],
    },
}
