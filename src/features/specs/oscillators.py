"""
Oscillator indicator specifications.

This module contains all oscillator-related feature specifications.
"""

from ..models import FeatureSpec

# Oscillator indicators (subset of trend indicators that are oscillators)
OSCILLATOR_FEATURES = {
    "rsi_14": FeatureSpec(
        name="rsi_14",
        type="oscillator",
        params={"period": 14},
        requires=["close"],
        description="Relative Strength Index (14 periods)",
    ),
    "macd": FeatureSpec(
        name="macd",
        type="oscillator",
        params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
        requires=["close"],
        description="MACD Line (12, 26, 9)",
    ),
    "macd_signal": FeatureSpec(
        name="macd_signal",
        type="oscillator",
        params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
        requires=["close"],
        description="MACD Signal Line (12, 26, 9)",
    ),
    "macd_histogram": FeatureSpec(
        name="macd_histogram",
        type="oscillator",
        params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
        requires=["close"],
        description="MACD Histogram (12, 26, 9)",
    ),
    # References to TREND_FEATURES (will be imported)
    "stoch_k": FeatureSpec(
        name="stoch_k",
        type="oscillator",
        params={"k_period": 14, "d_period": 3},
        requires=["high", "low", "close"],
        description="Stochastic %K (14, 3)",
    ),
    "stoch_d": FeatureSpec(
        name="stoch_d",
        type="oscillator",
        params={"k_period": 14, "d_period": 3},
        requires=["high", "low", "close"],
        description="Stochastic %D (14, 3)",
    ),
    "cci_20": FeatureSpec(
        name="cci_20",
        type="oscillator",
        params={"period": 20},
        requires=["high", "low", "close"],
        description="Commodity Channel Index (20 periods)",
    ),
    "dpo_20": FeatureSpec(
        name="dpo_20",
        type="oscillator",
        params={"period": 20},
        requires=["close"],
        description="Detrended Price Oscillator (20 periods)",
    ),
    "kst": FeatureSpec(
        name="kst",
        type="oscillator",
        params={
            "r1": 10,
            "r2": 15,
            "r3": 20,
            "r4": 30,
            "s1": 9,
            "s2": 9,
            "s3": 9,
            "s4": 9,
        },
        requires=["close"],
        description="Know Sure Thing indicator",
    ),
    "mom_10": FeatureSpec(
        name="mom_10",
        type="oscillator",
        params={"period": 10},
        requires=["close"],
        description="Momentum (10 periods)",
    ),
    "ppo": FeatureSpec(
        name="ppo",
        type="oscillator",
        params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
        requires=["close"],
        description="Percentage Price Oscillator (12, 26, 9)",
    ),
    "roc_10": FeatureSpec(
        name="roc_10",
        type="oscillator",
        params={"period": 10},
        requires=["close"],
        description="Rate of Change (10 periods)",
    ),
    "trix": FeatureSpec(
        name="trix",
        type="oscillator",
        params={"period": 18},
        requires=["close"],
        description="TRIX (18 periods)",
    ),
    "ultosc": FeatureSpec(
        name="ultosc",
        type="oscillator",
        params={"period1": 7, "period2": 14, "period3": 28},
        requires=["high", "low", "close"],
        description="Ultimate Oscillator (7, 14, 28)",
    ),
    "willr": FeatureSpec(
        name="willr",
        type="oscillator",
        params={"period": 14},
        requires=["high", "low", "close"],
        description="Williams %R (14 periods)",
    ),
}

# Stage C: Additional Oscillators / Momentum
OSC_STAGE_C = {
    "ao": FeatureSpec(
        name="ao",
        type="oscillator",
        params={},
        requires=["high", "low"],
        description="Awesome Oscillator",
    ),
    "apo": FeatureSpec(
        name="apo",
        type="oscillator",
        params={"fast": 12, "slow": 26},
        requires=["close"],
        description="Absolute Price Oscillator",
    ),
    "bop": FeatureSpec(
        name="bop",
        type="oscillator",
        params={},
        requires=["open", "high", "low", "close"],
        description="Balance of Power",
    ),
    "kdj_k": FeatureSpec(
        name="kdj_k",
        type="oscillator",
        params={"length": 14},
        requires=["high", "low", "close"],
        description="KDJ %K",
    ),
    "kdj_d": FeatureSpec(
        name="kdj_d",
        type="oscillator",
        params={"length": 14},
        requires=["high", "low", "close"],
        description="KDJ %D",
    ),
    "rsx_14": FeatureSpec(
        name="rsx_14",
        type="oscillator",
        params={"period": 14},
        requires=["close"],
        description="Jurik RSX (14)",
    ),
    "tsi": FeatureSpec(
        name="tsi",
        type="oscillator",
        params={},
        requires=["close"],
        description="True Strength Index",
    ),
    "fisher": FeatureSpec(
        name="fisher",
        type="oscillator",
        params={"length": 9},
        requires=["high", "low"],
        description="Fisher Transform",
    ),
    "slope_20": FeatureSpec(
        name="slope_20",
        type="oscillator",
        params={"window": 20},
        requires=["close"],
        description="Slope of close over window (20)",
    ),
}

# Stage E: Remaining Momentum/Trend indicators
MOMENTUM_STAGE_E = {
    "bias": FeatureSpec(
        name="bias",
        type="oscillator",
        params={"length": 26},
        requires=["close"],
        description="Bias",
    ),
    "brar": FeatureSpec(
        name="brar",
        type="oscillator",
        params={"length": 26},
        requires=["open", "high", "low", "close"],
        description="BRAR",
    ),
    "cfo": FeatureSpec(
        name="cfo",
        type="oscillator",
        params={"length": 14},
        requires=["close"],
        description="Chande Forecast Oscillator",
    ),
    "cg": FeatureSpec(
        name="cg",
        type="oscillator",
        params={"length": 10},
        requires=["close"],
        description="Center of Gravity",
    ),
    "coppock": FeatureSpec(
        name="coppock",
        type="oscillator",
        params={"length": 14},
        requires=["close"],
        description="Coppock Curve",
    ),
    "er": FeatureSpec(
        name="er",
        type="oscillator",
        params={"length": 10},
        requires=["close"],
        description="Efficiency Ratio",
    ),
    "eri": FeatureSpec(
        name="eri",
        type="oscillator",
        params={"length": 14},
        requires=["open", "high", "low", "close"],
        description="Elder Ray Index",
    ),
    "inertia": FeatureSpec(
        name="inertia",
        type="oscillator",
        params={"length": 14},
        requires=["close"],
        description="Inertia",
    ),
    "pgo": FeatureSpec(
        name="pgo",
        type="oscillator",
        params={"length": 14},
        requires=["close"],
        description="Pretty Good Oscillator",
    ),
    "psl": FeatureSpec(
        name="psl",
        type="oscillator",
        params={"length": 12},
        requires=["close"],
        description="Percentage Scale",
    ),
    "pvo": FeatureSpec(
        name="pvo",
        type="oscillator",
        params={"fast": 12, "slow": 26, "signal": 9},
        requires=["volume"],
        description="Percentage Volume Oscillator",
    ),
    "qqe": FeatureSpec(
        name="qqe",
        type="oscillator",
        params={"length": 14},
        requires=["close"],
        description="Quantitative Qualitative Estimation",
    ),
    "rsx": FeatureSpec(
        name="rsx",
        type="oscillator",
        params={"length": 14},
        requires=["close"],
        description="Relative Strength X",
    ),
    "rvgi": FeatureSpec(
        name="rvgi",
        type="oscillator",
        params={"length": 14},
        requires=["open", "high", "low", "close"],
        description="Relative Vigor Index",
    ),
    "smi": FeatureSpec(
        name="smi",
        type="oscillator",
        params={"length": 14},
        requires=["high", "low", "close"],
        description="Stochastic Momentum Index",
    ),
    "tsi": FeatureSpec(
        name="tsi",
        type="oscillator",
        params={"length": 25},
        requires=["close"],
        description="True Strength Index",
    ),
    "uo": FeatureSpec(
        name="uo",
        type="oscillator",
        params={"length": 14},
        requires=["high", "low", "close"],
        description="Ultimate Oscillator",
    ),
}

# StochRSI indicators
STOCHRSI_FEATURES = {
    "stochrsi_k": FeatureSpec(
        name="stochrsi_k",
        type="oscillator",
        params={"length": 14, "rsi_length": 14, "k": 3, "d": 3},
        requires=["close"],
        description="Stochastic RSI %K (14,14,3,3)",
    ),
    "stochrsi_d": FeatureSpec(
        name="stochrsi_d",
        type="oscillator",
        params={"length": 14, "rsi_length": 14, "k": 3, "d": 3},
        requires=["close"],
        description="Stochastic RSI %D (14,14,3,3)",
    ),
}
