"""
Name mapping utilities for pandas_ta indicators.

This module provides robust mapping between pandas_ta raw indicator names
and standardized feature names, with capability checking and fallback handling.
"""

import logging

import pandas as pd

try:
    import pandas_ta as ta  # type: ignore[import-untyped]
except ImportError:
    ta = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Version pinning for stability
PANDAS_TA_VERSION = "0.3.14b0"
PANDAS_VERSION = "2.3.1"

# Comprehensive mapping of pandas_ta indicator names to standardized names
INDICATOR_NAME_MAPPING = {
    # Moving Averages
    "EMA": "ema",
    "SMA": "sma",
    "WMA": "wma",
    "HMA": "hma",
    "DEMA": "dema",
    "TEMA": "tema",
    "TRIMA": "trima",
    "KAMA": "kama",
    "MAMA": "mama",
    "VWMA": "vwma",
    # Trend Indicators
    "ADX": "adx",
    "DMP": "adx_pos_di",
    "DMN": "adx_neg_di",
    "AROON": "aroon",
    "AROONOSC": "aroon_osc",
    "CCI": "cci",
    "DMI": "dmi",
    "DX": "dx",
    "PSAR": "psar",
    "TRIX": "trix",
    "UO": "uo",
    "WILLR": "willr",
    # Oscillators
    "RSI": "rsi",
    "STOCH": "stoch",
    "STOCHF": "stochf",
    "STOCHRSI": "stochrsi",
    "CMO": "cmo",
    "ROC": "roc",
    "MOM": "mom",
    "PPO": "ppo",
    "SLOPE": "slope",
    "STDDEV": "stddev",
    # MACD Family
    "MACD": "macd",
    "MACD_SIGNAL": "macd_signal",  # ✅ Added for test fix
    "MACDS": "macd_signal",
    "MACDs_12_26_9": "macd_signal",  # pandas_ta format
    "MACDH": "macd_histogram",
    "MACDh_12_26_9": "macd_histogram",  # pandas_ta format
    "MACD_12_26_9": "macd",  # pandas_ta format
    "MACDEXT": "macd_ext",
    "MACDEXT_S": "macd_ext_signal",
    "MACDEXT_H": "macd_ext_histogram",
    # Volatility
    "ATR": "atr",
    "NATR": "natr",
    "TRANGE": "trange",
    "BBANDS": "bb_upper",
    "BBANDS_M": "bb_middle",
    "BBANDS_L": "bb_lower",
    "BBWIDTH": "bb_width",
    "BBP": "bb_percent",
    "KC": "kc_upper",
    "KC_M": "kc_middle",
    "KC_L": "kc_lower",
    "DC": "dc_upper",
    "DC_M": "dc_middle",
    "DC_L": "dc_lower",
    "UI": "ui",
    "VHF": "vhf",
    # Volume
    "OBV": "obv",
    "AD": "ad",
    "ADOSC": "adosc",
    "CMF": "cmf",
    "FI": "fi",
    "EOM": "eom",
    "VWAP": "vwap",
    "MFI": "mfi",
    "NVI": "nvi",
    "PVI": "pvi",
    "PVO": "pvo",
    # Candles
    "CDL2CROWS": "cdl_2crows",
    "CDL3BLACKCROWS": "cdl_3blackcrows",
    "CDL3INSIDE": "cdl_3inside",
    "CDL3LINESTRIKE": "cdl_3linestrike",
    "CDL3OUTSIDE": "cdl_3outside",
    "CDL3STARSINSOUTH": "cdl_3starsinsouth",
    "CDL3WHITESOLDIERS": "cdl_3whitesoldiers",
    "CDLABANDONEDBABY": "cdl_abandonedbaby",
    "CDLADVANCEBLOCK": "cdl_advanceblock",
    "CDLBELTHOLD": "cdl_belthold",
    "CDLBREAKAWAY": "cdl_breakaway",
    "CDLCLOSINGMARUBOZU": "cdl_closingmarubozu",
    "CDLCONCEALBABYSWALL": "cdl_concealbabyswall",
    "CDLCOUNTERATTACK": "cdl_counterattack",
    "CDLDARKCLOUDCOVER": "cdl_darkcloudcover",
    "CDLDOJI": "cdl_doji",
    "CDLDOJISTAR": "cdl_dojistar",
    "CDLDRAGONFLYDOJI": "cdl_dragonflydoji",
    "CDLENGULFING": "cdl_engulfing",
    "CDLEVENINGDOJISTAR": "cdl_eveningdojistar",
    "CDLEVENINGSTAR": "cdl_eveningstar",
    "CDLGAPSIDESIDEWHITE": "cdl_gapsidesidewhite",
    "CDLGRAVESTONEDOJI": "cdl_gravestonedoji",
    "CDLHAMMER": "cdl_hammer",
    "CDLHANGINGMAN": "cdl_hangingman",
    "CDLHARAMI": "cdl_harami",
    "CDLHARAMICROSS": "cdl_haramicross",
    "CDLHIGHWAVE": "cdl_highwave",
    "CDLHIKKAKE": "cdl_hikkake",
    "CDLHIKKAKEMOD": "cdl_hikkakemod",
    "CDLHOMINGPIGEON": "cdl_homingpigeon",
    "CDLIDENTICAL3CROWS": "cdl_identical3crows",
    "CDLINNECK": "cdl_inneck",
    "CDLINVERTEDHAMMER": "cdl_invertedhammer",
    "CDLKICKING": "cdl_kicking",
    "CDLKICKINGBYLENGTH": "cdl_kickingbylength",
    "CDLLADDERBOTTOM": "cdl_ladderbottom",
    "CDLLONGLEGGEDDOJI": "cdl_longleggeddoji",
    "CDLLONGLINE": "cdl_longline",
    "CDLMARUBOZU": "cdl_marubozu",
    "CDLMATCHINGLOW": "cdl_matchinglow",
    "CDLMATHOLD": "cdl_mathold",
    "CDLMORNINGDOJISTAR": "cdl_morningdojistar",
    "CDLMORNINGSTAR": "cdl_morningstar",
    "CDLONNECK": "cdl_onneck",
    "CDLPIERCING": "cdl_piercing",
    "CDLRICKSHAWMAN": "cdl_rickshawman",
    "CDLRISEFALL3METHODS": "cdl_risefall3methods",
    "CDLSEPARATINGLINES": "cdl_separatinglines",
    "CDLSHOOTINGSTAR": "cdl_shootingstar",
    "CDLSHORTLINE": "cdl_shortline",
    "CDLSPINNINGTOP": "cdl_spinningtop",
    "CDLSTALLEDPATTERN": "cdl_stalledpattern",
    "CDLSTICKSANDWICH": "cdl_sticksandwich",
    "CDLTAKURI": "cdl_takuri",
    "CDLTASUKIGAP": "cdl_tasukigap",
    "CDLTHRUSTING": "cdl_thrusting",
    "CDLTRISTAR": "cdl_tristar",
    "CDLUNIQUE3RIVER": "cdl_unique3river",
    "CDLUPSIDEGAP2CROWS": "cdl_upsidegap2crows",
    "CDLXSIDEGAP3METHODS": "cdl_xsidegap3methods",
    # Statistics
    "CORREL": "correl",
    "LINEARREG": "linearreg",
    "LINEARREG_ANGLE": "linearreg_angle",
    "LINEARREG_INTERCEPT": "linearreg_intercept",
    "LINEARREG_SLOPE": "linearreg_slope",
    "VAR": "var",
    "ZSCORE": "zscore",
    # Performance
    "LOG_RETURN": "log_return",
    "PERCENT_RETURN": "percent_return",
    "CUMRET": "cumret",
}

# Multi-output indicators that need special handling
MULTI_OUTPUT_INDICATORS = {
    "BBANDS": ["bb_upper", "bb_middle", "bb_lower", "bb_width", "bb_percent"],
    "KC": ["kc_upper", "kc_middle", "kc_lower"],
    "DC": ["dc_upper", "dc_middle", "dc_lower"],
    "MACD": ["macd", "macd_signal", "macd_histogram"],
    "MACDEXT": ["macd_ext", "macd_ext_signal", "macd_ext_histogram"],
    "STOCH": ["stoch_k", "stoch_d"],
    "STOCHF": ["stochf_k", "stochf_d"],
    "STOCHRSI": ["stochrsi_k", "stochrsi_d"],
    "AROON": ["aroon_up", "aroon_down"],
    "DMI": ["dmi_plus", "dmi_minus"],
    "MAMA": ["mama", "fama"],
}

# Cache for capability checking
_capability_cache: dict[str, bool] = {}


def check_indicator_capability(indicator_name: str) -> bool:
    """
    Check if a pandas_ta indicator is available.

    Args:
        indicator_name: Name of the indicator to check

    Returns:
        True if indicator is available, False otherwise
    """
    if indicator_name in _capability_cache:
        return _capability_cache[indicator_name]

    try:
        # Try to access the indicator function
        if hasattr(ta, indicator_name):
            _capability_cache[indicator_name] = True
            return True
        _capability_cache[indicator_name] = False
        logger.warning(f"Indicator {indicator_name} not available in pandas_ta")
        return False
    except Exception as e:
        _capability_cache[indicator_name] = False
        logger.warning(f"Error checking capability for {indicator_name}: {e}")
        return False


def normalize_indicator_name(raw_name: str) -> str:
    """
    Normalize raw pandas_ta indicator name to standardized feature name.

    This function handles the complex mapping between pandas_ta's naming
    conventions and our standardized feature names.

    Args:
        raw_name: Raw indicator name from pandas_ta

    Returns:
        Standardized feature name
    """
    raw = str(raw_name).strip()
    if not raw:
        return raw

    # Сначала проверяем маппинг из name_aliases (для overlap и других критических индикаторов)
    try:
        from .schema.name_aliases import PANDAS_TA_TO_CANONICAL

        if raw in PANDAS_TA_TO_CANONICAL:
            return PANDAS_TA_TO_CANONICAL[raw]
    except ImportError:
        pass

    up = raw.upper()

    # Handle special cases first (multi-parameter indicators)
    # ✅ Check exact matches first before prefix matches
    if up == "MACD_SIGNAL":
        return "macd_signal"
    if up.startswith("MACD_") and not up.startswith(("MACDS_", "MACDH_")):
        return "macd"
    if up.startswith("MACDS_"):
        return "macd_signal"
    if up.startswith("MACDH_"):
        return "macd_histogram"
    if up.startswith("STOCHK_"):
        return "stoch_k"
    if up.startswith("STOCHD_"):
        return "stoch_d"
    if up.startswith("STOCHRSIK_"):
        return "stochrsi_k"
    if up.startswith("STOCHRSID_"):
        return "stochrsi_d"
    if up.startswith("BBANDS_"):
        if up.endswith("_U"):
            return "bb_upper"
        if up.endswith("_M"):
            return "bb_middle"
        if up.endswith("_L"):
            return "bb_lower"
        if up.endswith("_W"):
            return "bb_width"
        if up.endswith("_P"):
            return "bb_percent"
    elif up.startswith("KC_"):
        if up.endswith("_U"):
            return "kc_upper"
        if up.endswith("_M"):
            return "kc_middle"
        if up.endswith("_L"):
            return "kc_lower"
    elif up.startswith("DC_"):
        if up.endswith("_U"):
            return "dc_upper"
        if up.endswith("_M"):
            return "dc_middle"
        if up.endswith("_L"):
            return "dc_lower"
    elif up.startswith("DMP_"):
        return "adx_pos_di"
    elif up.startswith("DMN_"):
        return "adx_neg_di"

    # Handle period-based indicators (e.g., EMA_14, RSI_14)
    for base_name, standard_name in INDICATOR_NAME_MAPPING.items():
        if up.startswith(f"{base_name}_"):
            try:
                # Extract period
                parts = up.split("_")
                if len(parts) >= 2:
                    period = parts[1]
                    return f"{standard_name}_{int(period)}"
            except (ValueError, IndexError):
                pass
        elif up == base_name:
            return standard_name

    # ШАГ 4: Улучшенная нормализация имен (исправить EMA200 → ema_200)
    import re

    # Handle patterns like EMA200 -> ema_200, SMA200 -> sma_200
    m = re.match(r"^([A-Za-z]+)(\d+)$", raw)
    if m:
        return f"{m.group(1).lower()}_{m.group(2)}"

    # Handle patterns like BBANDS -> bbands, MACD -> macd
    normalized = raw.strip().lower()
    normalized = re.sub(r"\s+", "_", normalized)  # Replace spaces with underscores
    return re.sub(
        r"[^a-z0-9_]", "", normalized
    )  # Remove non-alphanumeric except underscores


def get_available_indicators() -> set[str]:
    """
    Get set of available pandas_ta indicators.

    Returns:
        Set of available indicator names
    """
    try:
        # Get all attributes that are likely indicators (functions)
        indicators = set()
        for attr_name in dir(ta):
            if not attr_name.startswith("_") and callable(getattr(ta, attr_name)):
                # Filter out non-indicator functions
                if attr_name.upper() in INDICATOR_NAME_MAPPING or any(
                    attr_name.upper().startswith(base)
                    for base in INDICATOR_NAME_MAPPING
                ):
                    indicators.add(attr_name)
        return indicators
    except Exception as e:
        logger.warning(f"Error getting available indicators: {e}")
        return set()


def safe_indicator_call(indicator_name: str, *args, **kwargs) -> pd.Series | None:
    """
    Safely call a pandas_ta indicator with capability checking.

    Args:
        indicator_name: Name of the indicator to call
        *args: Arguments to pass to the indicator
        **kwargs: Keyword arguments to pass to the indicator

    Returns:
        Series with indicator values, or None if indicator is not available
    """
    if not check_indicator_capability(indicator_name):
        logger.warning(
            f"Indicator {indicator_name} not available, returning NaN series"
        )
        if args and len(args) > 0 and hasattr(args[0], "__len__"):
            # Return NaN series with same length as input
            return pd.Series(
                [float("nan")] * len(args[0]), index=getattr(args[0], "index", None)
            )
        return None

    try:
        indicator_func = getattr(ta, indicator_name)
        return indicator_func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"Error calling indicator {indicator_name}: {e}")
        if args and len(args) > 0 and hasattr(args[0], "__len__"):
            return pd.Series(
                [float("nan")] * len(args[0]), index=getattr(args[0], "index", None)
            )
        return None


def get_version_info() -> dict[str, str]:
    """
    Get version information for pandas_ta and pandas.

    Returns:
        Dictionary with version information
    """
    return {
        "pandas_ta": getattr(ta, "__version__", "unknown"),
        "pandas": pd.__version__,
        "expected_pandas_ta": PANDAS_TA_VERSION,
        "expected_pandas": PANDAS_VERSION,
    }


def validate_versions() -> bool:
    """
    Validate that we're using the expected versions of pandas_ta and pandas.

    Returns:
        True if versions match expected, False otherwise
    """
    version_info = get_version_info()

    pandas_ta_ok = version_info["pandas_ta"] == PANDAS_TA_VERSION
    pandas_ok = version_info["pandas"] == PANDAS_VERSION

    if not pandas_ta_ok:
        logger.warning(
            f"pandas_ta version mismatch: expected {PANDAS_TA_VERSION}, got {version_info['pandas_ta']}"
        )
    if not pandas_ok:
        logger.warning(
            f"pandas version mismatch: expected {PANDAS_VERSION}, got {version_info['pandas']}"
        )

    return pandas_ta_ok and pandas_ok
