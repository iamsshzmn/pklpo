"""
Performance indicator specifications.

This module contains all performance-related feature specifications.
"""

from ..domain.models import FeatureSpec

# Performance
PERFORMANCE_FEATURES = {
    "log_return": FeatureSpec(
        name="log_return",
        type="performance",
        params={},
        requires=["close"],
        description="Log return of close",
    ),
    "percent_return": FeatureSpec(
        name="percent_return",
        type="performance",
        params={},
        requires=["close"],
        description="Percent return of close",
    ),
    "trend_return_20": FeatureSpec(
        name="trend_return_20",
        type="performance",
        params={"window": 20},
        requires=["close"],
        description="Rolling cumulative return over window (20)",
    ),
    "drawdown": FeatureSpec(
        name="drawdown",
        type="performance",
        params={},
        requires=["close"],
        description="Drawdown from running max",
    ),
    "returns_20": FeatureSpec(
        name="returns_20",
        type="performance",
        params={"window": 20},
        requires=["close"],
        description="Rolling returns (20 periods)",
    ),
    "volatility_20": FeatureSpec(
        name="volatility_20",
        type="performance",
        params={"window": 20},
        requires=["close"],
        description="Rolling volatility (20 periods)",
    ),
    "sharpe_20": FeatureSpec(
        name="sharpe_20",
        type="performance",
        params={"window": 20},
        requires=["close"],
        description="Rolling Sharpe ratio (20 periods)",
    ),
    "max_drawdown_20": FeatureSpec(
        name="max_drawdown_20",
        type="performance",
        params={"window": 20},
        requires=["close"],
        description="Rolling maximum drawdown (20 periods)",
    ),
}
