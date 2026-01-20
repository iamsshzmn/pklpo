"""
Volume indicator specifications.

This module contains all volume-related feature specifications.
"""

from ..models import FeatureSpec

# Volume indicators
VOLUME_FEATURES = {
    "obv": FeatureSpec(
        name="obv",
        type="volume",
        params={},
        requires=["close", "volume"],
        description="On Balance Volume",
    ),
    "ad": FeatureSpec(
        name="ad",
        type="volume",
        params={},
        requires=["high", "low", "close", "volume"],
        description="Accumulation/Distribution Line",
    ),
    "adosc": FeatureSpec(
        name="adosc",
        type="volume",
        params={"fast_period": 3, "slow_period": 10},
        requires=["high", "low", "close", "volume"],
        description="Chaikin A/D Oscillator (3, 10)",
    ),
    "cmf": FeatureSpec(
        name="cmf",
        type="volume",
        params={"period": 20},
        requires=["high", "low", "close", "volume"],
        description="Chaikin Money Flow (20 periods)",
    ),
    "mfi": FeatureSpec(
        name="mfi",
        type="volume",
        params={"period": 14},
        requires=["high", "low", "close", "volume"],
        description="Money Flow Index (14 periods)",
    ),
    "vwap": FeatureSpec(
        name="vwap",
        type="volume",
        params={},
        requires=["high", "low", "close", "volume"],
        description="Volume Weighted Average Price",
    ),
    "vwma": FeatureSpec(
        name="vwma",
        type="volume",
        params={"period": 20},
        requires=["close", "volume"],
        description="Volume Weighted Moving Average (20 periods)",
    ),
    "volume_sma20": FeatureSpec(
        name="volume_sma20",
        type="volume",
        params={"period": 20},
        requires=["volume"],
        description="Volume Simple Moving Average (20 periods)",
    ),
    "vp_point_of_control": FeatureSpec(
        name="vp_point_of_control",
        type="volume",
        params={"window_size": 50, "bins": 20},
        requires=["close", "volume"],
        description="Volume Profile Point of Control (POC)",
    ),
    "vp_value_area_high": FeatureSpec(
        name="vp_value_area_high",
        type="volume",
        params={"window_size": 50, "bins": 20, "value_area_percent": 70},
        requires=["close", "volume"],
        description="Volume Profile Value Area High (VAH)",
    ),
    "vp_value_area_low": FeatureSpec(
        name="vp_value_area_low",
        type="volume",
        params={"window_size": 50, "bins": 20, "value_area_percent": 70},
        requires=["close", "volume"],
        description="Volume Profile Value Area Low (VAL)",
    ),
}

# Stage D: Additional Volume
VOLM_STAGE_D = {
    "efi": FeatureSpec(
        name="efi",
        type="volume",
        params={"length": 13},
        requires=["close", "volume"],
        description="Elder Force Index",
    ),
    "eom": FeatureSpec(
        name="eom",
        type="volume",
        params={"length": 14},
        requires=["high", "low", "close", "volume"],
        description="Ease of Movement",
    ),
    "nvi": FeatureSpec(
        name="nvi",
        type="volume",
        params={},
        requires=["close", "volume"],
        description="Negative Volume Index",
    ),
    "pvi": FeatureSpec(
        name="pvi",
        type="volume",
        params={},
        requires=["close", "volume"],
        description="Positive Volume Index",
    ),
    "pvt": FeatureSpec(
        name="pvt",
        type="volume",
        params={},
        requires=["close", "volume"],
        description="Price Volume Trend",
    ),
}
