"""
Constants for ta_safe module.

This module contains configuration constants and allowlists.
Name mappings consolidated in schema/name_aliases.py (SSoT).
"""

import os

from src.config import get_settings


def get_backend() -> str:
    """Resolve TA backend lazily on each call."""
    env_backend = os.getenv("FEATURES_TA_BACKEND")
    if env_backend:
        return env_backend
    try:
        return get_settings().features.ta_backend
    except Exception:
        return "auto"


# Required OHLCV columns
REQ = ("open", "high", "low", "close", "volume")

# Allowlist of permitted pandas_ta functions
ALLOW = {
    # Moving Averages
    "ema",
    "sma",
    "wma",
    "hma",
    "kama",
    "tema",
    "dema",
    "alma",
    "fwma",
    "rma",
    "t3",
    "trima",
    "vidya",
    "zlma",
    "sinwma",
    "swma",
    "pwma",
    "hwma",
    "linreg",
    # Oscillators
    "rsi",
    "stoch",
    "stochrsi",
    "cci",
    "mfi",
    "roc",
    "ppo",
    "trix",
    "willr",
    "ao",
    "apo",
    "bop",
    "kdj",
    "tsi",
    "fisher",
    "slope",
    "bias",
    "brar",
    "cfo",
    "cg",
    "coppock",
    "er",
    "eri",
    "inertia",
    "pgo",
    "psl",
    "pvo",
    "qqe",
    "rvgi",
    "smi",
    "uo",
    # Volatility
    "bbands",
    "kc",
    "atr",
    "aberration",
    "accbands",
    "massi",
    "pdist",
    "rvi",
    "ui",
    "natr",
    # trange, tr, cdl_doji, cdl_inside excluded from pipeline
    # - tr/trange: ATR computes True Range internally
    # - cdl_doji/cdl_inside: custom implementations in candles.py
    # Volume
    "obv",
    "cmf",
    "efi",
    "eom",
    "nvi",
    "pvi",
    "pvt",
    "ad",
    "adosc",
    # Trend
    "adx",
    "aroon",
    "supertrend",
    "psar",
    "ichimoku",
    "amat",
    "chop",
    "decay",
    "decreasing",
    "dpo",
    "increasing",
    "long_run",
    "qstick",
    "short_run",
    "ttm_trend",
    "vortex",
    # Squeeze
    "squeeze_pro",
    # Candles - excluded, use custom implementations in candles.py
    # MACD
    "macd",
}
