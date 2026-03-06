"""
Moving Average Indicators Module

Group: MA (Moving Averages)
Dependencies: OHLC
Max Lookback: 200 bars
Output Fields: ema_8, ema_12, ema_21, ema_50, ema_200, sma_20, sma_50, sma_200, wma_20, hma_20, etc.

This module calculates various types of moving averages including:
- EMA (Exponential Moving Average): Fast-reacting to price changes
- SMA (Simple Moving Average): Equal weighting for all periods
- WMA (Weighted Moving Average): Linear weighting
- HMA (Hull Moving Average): Reduces lag
- KAMA (Kaufman Adaptive MA): Adapts to market volatility
- TEMA/DEMA: Triple/Double exponential
- And more advanced MAs
"""

import pandas as pd

from src.logging import get_logger

from ..ta_safe import safe_ta_with_fallback

# Import from utils package (which re-exports from utils.py module)
from ..utils import _first_col_or_series, _nan_series
from .debug_utils import log_group_results, log_group_start
from .registry import GroupRegistry

logger = get_logger(__name__)


def _fallback_first_col_or_series(
    value: object, default_name: str, index: pd.Index
) -> pd.Series:
    if isinstance(value, pd.Series):
        return value
    if isinstance(value, pd.DataFrame):
        if default_name in value.columns:
            return value[default_name]
        if len(value.columns) > 0:
            return value.iloc[:, 0]
    return pd.Series([float("nan")] * len(index), index=index, name=default_name)


def _fallback_nan_series(index: pd.Index, name: str) -> pd.Series:
    return pd.Series([float("nan")] * len(index), index=index, name=name)


if not callable(_first_col_or_series):
    _first_col_or_series = _fallback_first_col_or_series
if not callable(_nan_series):
    _nan_series = _fallback_nan_series


def _ensure_series(value: object, name: str, index: pd.Index) -> pd.Series:
    """Normalize TA output to a 1D Series."""
    return _first_col_or_series(value, name, index)


@GroupRegistry.register(
    "ma",
    order=1,
    dependencies=["overlap"],
    description="Moving averages (SMA, EMA, WMA, etc.)",
)
def calc_ma_indicators(
    df: pd.DataFrame, available: set[str], **kwargs
) -> dict[str, pd.Series]:
    """
    Calculate Moving Average indicators.

    Args:
        df: DataFrame with OHLC data (must have 'open', 'high', 'low', 'close' columns)
        available: Set of indicator names to calculate
        **kwargs: Additional parameters (unused, for Protocol compliance)

    Returns:
        Dictionary mapping indicator names to pandas Series with calculated values

    Example:
        >>> ma_indicators = calc_ma_indicators(df, {'ema_21', 'sma_50', 'sma_200'})
        >>> ema_21 = ma_indicators['ema_21']
    """
    log_group_start("MA", df, available)
    result: dict[str, pd.Series] = {}

    # EMA
    for period in [8, 12, 13, 21, 26, 34, 50, 55, 89, 144, 200, 233]:
        key = f"ema_{period}"
        if key in available:
            ema_series = safe_ta_with_fallback(df, "ema", length=period)
            result[key] = _ensure_series(ema_series, key, df.index)

    # SMA
    for period in [20, 34, 50, 200]:
        key = f"sma_{period}"
        if key in available:
            sma_series = safe_ta_with_fallback(df, "sma", length=period)
            result[key] = _ensure_series(sma_series, key, df.index)

    # WMA
    for period in [20]:
        key = f"wma_{period}"
        if key in available:
            wma_series = safe_ta_with_fallback(df, "wma", length=period)
            result[key] = _ensure_series(wma_series, key, df.index)

    # HMA
    for period in [20]:
        key = f"hma_{period}"
        if key in available:
            hma_series = safe_ta_with_fallback(df, "hma", length=period)
            result[key] = _ensure_series(hma_series, key, df.index)

    # KAMA
    for period in [20]:
        key = f"kama_{period}"
        if key in available:
            kama_series = safe_ta_with_fallback(
                df, "kama", length=period, fast=2, slow=30
            )
            result[key] = _ensure_series(kama_series, key, df.index)

    # TEMA
    for period in [20]:
        key = f"tema_{period}"
        if key in available:
            tema_series = safe_ta_with_fallback(df, "tema", length=period)
            result[key] = _ensure_series(tema_series, key, df.index)

    # DEMA
    for period in [20]:
        key = f"dema_{period}"
        if key in available:
            dema_series = safe_ta_with_fallback(df, "dema", length=period)
            result[key] = _ensure_series(dema_series, key, df.index)

    # ALMA
    for period in [20]:
        key = f"alma_{period}"
        if key in available:
            alma_series = safe_ta_with_fallback(df, "alma", length=period)
            result[key] = _ensure_series(alma_series, key, df.index)

    # FWMA
    for period in [20]:
        key = f"fwma_{period}"
        if key in available:
            fwma_series = safe_ta_with_fallback(df, "fwma", length=period)
            result[key] = _ensure_series(fwma_series, key, df.index)

    # RMA
    for period in [20]:
        key = f"rma_{period}"
        if key in available:
            rma_series = safe_ta_with_fallback(df, "rma", length=period)
            result[key] = _ensure_series(rma_series, key, df.index)

    # T3
    for period in [20]:
        key = f"t3_{period}"
        if key in available:
            logger.info(f"T3: Calculating {key} (key in available: {key in available})")
            try:
                t3_result = safe_ta_with_fallback(df, "t3", length=period)
                t3_series = _first_col_or_series(t3_result, key, df.index)
                result[key] = t3_series
            except Exception as e:
                logger.error(f"  T3_{period}: {type(e).__name__}: {e}")
                result[key] = _nan_series(df.index, key)

    # TRIMA
    for period in [20]:
        key = f"trima_{period}"
        if key in available:
            trima_series = safe_ta_with_fallback(df, "trima", length=period)
            result[key] = _ensure_series(trima_series, key, df.index)

    # VIDYA
    for period in [20]:
        key = f"vidya_{period}"
        if key in available:
            vidya_series = safe_ta_with_fallback(df, "vidya", length=period)
            result[key] = _ensure_series(vidya_series, key, df.index)

    # ZLMA
    for period in [20]:
        key = f"zlma_{period}"
        if key in available:
            zlma_series = safe_ta_with_fallback(df, "zlma", length=period)
            result[key] = _ensure_series(zlma_series, key, df.index)

    # SINWMA
    for period in [20]:
        key = f"sinwma_{period}"
        if key in available:
            sinwma_series = safe_ta_with_fallback(df, "sinwma", length=period)
            result[key] = _ensure_series(sinwma_series, key, df.index)

    # SWMA
    for period in [20]:
        key = f"swma_{period}"
        if key in available:
            swma_series = safe_ta_with_fallback(df, "swma", length=period)
            result[key] = _ensure_series(swma_series, key, df.index)

    # PWMA
    for period in [20]:
        key = f"pwma_{period}"
        if key in available:
            pwma_series = safe_ta_with_fallback(df, "pwma", length=period)
            result[key] = _ensure_series(pwma_series, key, df.index)

    # HWMA
    for period in [20]:
        key = f"hwma_{period}"
        if key in available:
            hwma_series = safe_ta_with_fallback(df, "hwma", length=period)
            result[key] = _ensure_series(hwma_series, key, df.index)

    # LINREG
    for period in [20]:
        key = f"linreg_{period}"
        if key in available:
            linreg_series = safe_ta_with_fallback(df, "linreg", length=period)
            result[key] = _ensure_series(linreg_series, key, df.index)

    log_group_results("MA", result)
    return result
