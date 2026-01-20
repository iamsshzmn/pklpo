"""
Overlap indicator specifications.

This module contains all overlap-related feature specifications.
"""

from ..models import FeatureSpec

# Overlap simple composites
OVERLAP_FEATURES = {
    "hl2": FeatureSpec(
        name="hl2",
        type="overlap",
        params={},
        requires=["high", "low"],
        description="(high+low)/2",
    ),
    "hlc3": FeatureSpec(
        name="hlc3",
        type="overlap",
        params={},
        requires=["high", "low", "close"],
        description="(high+low+close)/3",
    ),
    "ohlc4": FeatureSpec(
        name="ohlc4",
        type="overlap",
        params={},
        requires=["open", "high", "low", "close"],
        description="(open+high+low+close)/4",
    ),
    "wcp": FeatureSpec(
        name="wcp",
        type="overlap",
        params={"w_open": 1, "w_high": 1, "w_low": 1, "w_close": 2},
        requires=["open", "high", "low", "close"],
        description="Weighted Close Price (default weights o:h:l:c = 1:1:1:2)",
    ),
    "midpoint": FeatureSpec(
        name="midpoint",
        type="overlap",
        params={},
        requires=["high", "low"],
        description="(high+low)/2 alias",
    ),
    "midprice": FeatureSpec(
        name="midprice",
        type="overlap",
        params={},
        requires=["high", "low"],
        description="Mid-price between high and low",
    ),
}
