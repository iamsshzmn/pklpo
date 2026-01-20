"""
Volatility indicator specifications.

This module contains all volatility-related feature specifications.
"""

from ..models import FeatureSpec

# Volatility indicators
VOLATILITY_FEATURES = {
    "atr_14": FeatureSpec(
        name="atr_14",
        type="volatility",
        params={"period": 14},
        requires=["high", "low", "close"],
        description="Average True Range (14 periods)",
    ),
    "natr_14": FeatureSpec(
        name="natr_14",
        type="volatility",
        params={"period": 14},
        requires=["high", "low", "close"],
        description="Normalized Average True Range (14 periods)",
    ),
    "bb_upper": FeatureSpec(
        name="bb_upper",
        type="volatility",
        params={"period": 20, "std_dev": 2},
        requires=["close"],
        description="Bollinger Bands Upper (20, 2)",
    ),
    "bb_middle": FeatureSpec(
        name="bb_middle",
        type="volatility",
        params={"period": 20, "std_dev": 2},
        requires=["close"],
        description="Bollinger Bands Middle (20, 2)",
    ),
    "bb_lower": FeatureSpec(
        name="bb_lower",
        type="volatility",
        params={"period": 20, "std_dev": 2},
        requires=["close"],
        description="Bollinger Bands Lower (20, 2)",
    ),
    "bbands_width": FeatureSpec(
        name="bbands_width",
        type="volatility",
        params={"period": 20, "std_dev": 2},
        requires=["close"],
        description="Bollinger Bands Width (20, 2)",
    ),
    "bbands_percent": FeatureSpec(
        name="bbands_percent",
        type="volatility",
        params={"period": 20, "std_dev": 2},
        requires=["close"],
        description="Bollinger Bands %B (20, 2)",
    ),
    "kc_upper": FeatureSpec(
        name="kc_upper",
        type="volatility",
        params={"period": 20, "atr_period": 10, "multiplier": 2},
        requires=["high", "low", "close"],
        description="Keltner Channel Upper (20, 10, 2)",
    ),
    "kc_middle": FeatureSpec(
        name="kc_middle",
        type="volatility",
        params={"period": 20, "atr_period": 10, "multiplier": 2},
        requires=["high", "low", "close"],
        description="Keltner Channel Middle (20, 10, 2)",
    ),
    "kc_lower": FeatureSpec(
        name="kc_lower",
        type="volatility",
        params={"period": 20, "atr_period": 10, "multiplier": 2},
        requires=["high", "low", "close"],
        description="Keltner Channel Lower (20, 10, 2)",
    ),
    "dc_upper": FeatureSpec(
        name="dc_upper",
        type="volatility",
        params={"period": 20},
        requires=["high", "low", "close"],
        description="Donchian Channel Upper (20)",
    ),
    "dc_middle": FeatureSpec(
        name="dc_middle",
        type="volatility",
        params={"period": 20},
        requires=["high", "low", "close"],
        description="Donchian Channel Middle (20)",
    ),
    "dc_lower": FeatureSpec(
        name="dc_lower",
        type="volatility",
        params={"period": 20},
        requires=["high", "low", "close"],
        description="Donchian Channel Lower (20)",
    ),
    "parkinson_vol": FeatureSpec(
        name="parkinson_vol",
        type="volatility",
        params={"period": 14},
        requires=["high", "low"],
        description="Parkinson Volatility (14 periods)",
    ),
}

# Stage D: Additional Volatility
VOL_STAGE_D = {
    "aberration": FeatureSpec(
        name="aberration",
        type="volatility",
        params={"length": 20},
        requires=["close"],
        description="Aberration bands width/value",
    ),
    "accbands_upper": FeatureSpec(
        name="accbands_upper",
        type="volatility",
        params={"length": 20},
        requires=["high", "low", "close"],
        description="Acceleration Bands Upper",
    ),
    "accbands_middle": FeatureSpec(
        name="accbands_middle",
        type="volatility",
        params={"length": 20},
        requires=["high", "low", "close"],
        description="Acceleration Bands Middle",
    ),
    "accbands_lower": FeatureSpec(
        name="accbands_lower",
        type="volatility",
        params={"length": 20},
        requires=["high", "low", "close"],
        description="Acceleration Bands Lower",
    ),
    "massi": FeatureSpec(
        name="massi",
        type="volatility",
        params={"length": 25},
        requires=["high", "low"],
        description="Mass Index",
    ),
    "pdist": FeatureSpec(
        name="pdist",
        type="volatility",
        params={"length": 14},
        requires=["close"],
        description="Price Distance",
    ),
    "rvi": FeatureSpec(
        name="rvi",
        type="volatility",
        params={"length": 14},
        requires=["open", "high", "low", "close"],
        description="Relative Volatility Index",
    ),
    "ui": FeatureSpec(
        name="ui",
        type="volatility",
        params={"length": 14},
        requires=["close"],
        description="Ulcer Index",
    ),
}

# Squeeze indicators (TTM Squeeze)
SQUEEZE_FEATURES = {
    "ttm_squeeze_on": FeatureSpec(
        name="ttm_squeeze_on",
        type="squeeze",
        params={},
        requires=["high", "low", "close"],
        description="TTM Squeeze on-state (wide/normal/narrow any)",
    ),
    "ttm_squeeze_hist": FeatureSpec(
        name="ttm_squeeze_hist",
        type="squeeze",
        params={},
        requires=["high", "low", "close"],
        description="TTM Squeeze histogram proxy",
    ),
    "ttm_squeeze_value": FeatureSpec(
        name="ttm_squeeze_value",
        type="squeeze",
        params={},
        requires=["high", "low", "close"],
        description="TTM Squeeze value",
    ),
}
