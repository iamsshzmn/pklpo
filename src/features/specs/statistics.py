"""
Statistical indicator specifications.

This module contains all statistical feature specifications.
"""

from ..models import FeatureSpec

# Statistics (rolling, default window=20)
STATISTICS_FEATURES = {
    "median_20": FeatureSpec(
        name="median_20",
        type="statistics",
        params={"window": 20},
        requires=["close"],
        description="Rolling median of close (20)",
    ),
    "mad_20": FeatureSpec(
        name="mad_20",
        type="statistics",
        params={"window": 20},
        requires=["close"],
        description="Rolling MAD of close (20)",
    ),
    "stdev_20": FeatureSpec(
        name="stdev_20",
        type="statistics",
        params={"window": 20},
        requires=["close"],
        description="Rolling standard deviation of close (20)",
    ),
    "variance_20": FeatureSpec(
        name="variance_20",
        type="statistics",
        params={"window": 20},
        requires=["close"],
        description="Rolling variance of close (20)",
    ),
    "skew_20": FeatureSpec(
        name="skew_20",
        type="statistics",
        params={"window": 20},
        requires=["close"],
        description="Rolling skewness of close (20)",
    ),
    "kurtosis_20": FeatureSpec(
        name="kurtosis_20",
        type="statistics",
        params={"window": 20},
        requires=["close"],
        description="Rolling kurtosis of close (20)",
    ),
    "zscore_20": FeatureSpec(
        name="zscore_20",
        type="statistics",
        params={"window": 20},
        requires=["close"],
        description="Z-score of close with rolling mean/std (20)",
    ),
    "std_20": FeatureSpec(
        name="std_20",
        type="statistics",
        params={"window": 20},
        requires=["close"],
        description="Rolling standard deviation (20 periods)",
    ),
    "var_20": FeatureSpec(
        name="var_20",
        type="statistics",
        params={"window": 20},
        requires=["close"],
        description="Rolling variance (20 periods)",
    ),
    "kurt_20": FeatureSpec(
        name="kurt_20",
        type="statistics",
        params={"window": 20},
        requires=["close"],
        description="Rolling kurtosis (20 periods)",
    ),
}
