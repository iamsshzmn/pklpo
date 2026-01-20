"""
Candlestick pattern indicator specifications.

This module contains all candlestick pattern-related feature specifications.
"""

from ..models import FeatureSpec

# Candle indicators (computed via indicator_groups.candles without pandas_ta)
CANDLES_FEATURES = {
    "ha_open": FeatureSpec(
        name="ha_open",
        type="candles",
        params={},
        requires=["open", "high", "low", "close"],
        description="Heikin-Ashi Open",
    ),
    "ha_high": FeatureSpec(
        name="ha_high",
        type="candles",
        params={},
        requires=["open", "high", "low", "close"],
        description="Heikin-Ashi High",
    ),
    "ha_low": FeatureSpec(
        name="ha_low",
        type="candles",
        params={},
        requires=["open", "high", "low", "close"],
        description="Heikin-Ashi Low",
    ),
    "ha_close": FeatureSpec(
        name="ha_close",
        type="candles",
        params={},
        requires=["open", "high", "low", "close"],
        description="Heikin-Ashi Close",
    ),
    "cdl_doji": FeatureSpec(
        name="cdl_doji",
        type="candles",
        params={"threshold": 0.1},
        requires=["open", "high", "low", "close"],
        description="Doji candlestick (body/range <= threshold)",
    ),
    "cdl_inside": FeatureSpec(
        name="cdl_inside",
        type="candles",
        params={},
        requires=["high", "low"],
        description="Inside bar (high<=prev_high & low>=prev_low)",
    ),
}
