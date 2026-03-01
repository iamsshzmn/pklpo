"""
Constants for ta_safe module.

This module contains configuration constants, allowlists, and rename mappings.
"""

import os

# Backend configuration
BACKEND = os.getenv("FEATURES_TA_BACKEND", "auto")

# Обязательные колонки для OHLCV
REQ = ("open", "high", "low", "close", "volume")

# Маппинг имен pandas_ta на наши specs
RENAME_MAP = {
    # pandas_ta -> наши имена
    "RSI_14": "rsi_14",
    "ATRr_14": "atr_14",
    "BBL_20_2.0": "bb_lower",
    "BBM_20_2.0": "bb_middle",
    "BBU_20_2.0": "bb_upper",
    "MACD_12_26_9": "macd",
    "MACDs_12_26_9": "macd_signal",
    "MACDh_12_26_9": "macd_histogram",
    "STOCHk_14_3_3": "stoch_k",
    "STOCHd_14_3_3": "stoch_d",
    "ADX_14": "adx_14",
    "DMP_14": "adx_pos_di",
    "DMN_14": "adx_neg_di",
    "SUPERT_10_3.0": "supertrend",
    "SUPERTd_10_3.0": "supertrend_direction",
    "SUPERTl_10_3.0": "supertrend_long",
    "SUPERTs_10_3.0": "supertrend_short",
    "PSARl_0.02_0.2": "psar_long",
    "PSARs_0.02_0.2": "psar_short",
    "AROONU_14": "aroon_up",
    "AROOND_14": "aroon_down",
    "AROONOSC_14": "aroon_osc",
}

# Список разрешенных функций pandas_ta
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
    # trange, tr, cdl_doji, cdl_inside исключены из пайплайна
    # - tr/trange: ATR считает True Range внутри себя
    # - cdl_doji/cdl_inside: используют собственные реализации в candles.py
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
    # Candles - исключены, используют собственные реализации в candles.py
    # MACD
    "macd",
}
