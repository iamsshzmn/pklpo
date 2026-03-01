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

logger = get_logger(__name__)


def calc_ma_indicators(df: pd.DataFrame, available: set) -> dict:
    """
    Calculate Moving Average indicators.

    Args:
        df: DataFrame with OHLC data (must have 'open', 'high', 'low', 'close' columns)
        available: Set of indicator names to calculate

    Returns:
        Dictionary mapping indicator names to pandas Series with calculated values

    Example:
        >>> ma_indicators = calc_ma_indicators(df, {'ema_21', 'sma_50', 'sma_200'})
        >>> ema_21 = ma_indicators['ema_21']
    """
    log_group_start("MA", df, available)
    result = {}

    # EMA индикаторы
    for period in [8, 12, 13, 21, 26, 34, 50, 55, 89, 144, 200, 233]:
        key = f"ema_{period}"
        if key in available:
            ema_series = safe_ta_with_fallback(df, "ema", length=period)
            result[key] = ema_series

    # SMA индикаторы
    for period in [20, 34, 50, 200]:
        key = f"sma_{period}"
        if key in available:
            sma_series = safe_ta_with_fallback(df, "sma", length=period)
            result[key] = sma_series

    # WMA индикаторы
    for period in [20]:
        key = f"wma_{period}"
        if key in available:
            wma_series = safe_ta_with_fallback(df, "wma", length=period)
            result[key] = wma_series

    # HMA индикаторы
    for period in [20]:
        key = f"hma_{period}"
        if key in available:
            hma_series = safe_ta_with_fallback(df, "hma", length=period)
            result[key] = hma_series

    # KAMA индикаторы
    for period in [20]:
        key = f"kama_{period}"
        if key in available:
            kama_series = safe_ta_with_fallback(
                df, "kama", length=period, fast=2, slow=30
            )
            result[key] = kama_series

    # TEMA индикаторы
    for period in [20]:
        key = f"tema_{period}"
        if key in available:
            tema_series = safe_ta_with_fallback(df, "tema", length=period)
            result[key] = tema_series

    # DEMA индикаторы
    for period in [20]:
        key = f"dema_{period}"
        if key in available:
            dema_series = safe_ta_with_fallback(df, "dema", length=period)
            result[key] = dema_series

    # ALMA индикаторы
    for period in [20]:
        key = f"alma_{period}"
        if key in available:
            alma_series = safe_ta_with_fallback(df, "alma", length=period)
            result[key] = alma_series

    # FWMA индикаторы
    for period in [20]:
        key = f"fwma_{period}"
        if key in available:
            fwma_series = safe_ta_with_fallback(df, "fwma", length=period)
            result[key] = fwma_series

    # RMA индикаторы
    for period in [20]:
        key = f"rma_{period}"
        if key in available:
            rma_series = safe_ta_with_fallback(df, "rma", length=period)
            result[key] = rma_series

    # T3 индикаторы
    for period in [20]:
        key = f"t3_{period}"
        if key in available:
            logger.info(f"T3: Calculating {key} (key in available: {key in available})")
            try:
                t3_result = safe_ta_with_fallback(df, "t3", length=period)
                t3_series = _first_col_or_series(t3_result, key, df.index)
                result[key] = t3_series
            except Exception as e:
                logger.error(f"Ошибка расчёта T3_{period}: {type(e).__name__}: {e}")
                result[key] = _nan_series(df.index, key)

    # TRIMA индикаторы
    for period in [20]:
        key = f"trima_{period}"
        if key in available:
            trima_series = safe_ta_with_fallback(df, "trima", length=period)
            result[key] = trima_series

    # VIDYA индикаторы
    for period in [20]:
        key = f"vidya_{period}"
        if key in available:
            vidya_series = safe_ta_with_fallback(df, "vidya", length=period)
            result[key] = vidya_series

    # ZLMA индикаторы
    for period in [20]:
        key = f"zlma_{period}"
        if key in available:
            zlma_series = safe_ta_with_fallback(df, "zlma", length=period)
            result[key] = zlma_series

    # SINWMA индикаторы
    for period in [20]:
        key = f"sinwma_{period}"
        if key in available:
            sinwma_series = safe_ta_with_fallback(df, "sinwma", length=period)
            result[key] = sinwma_series

    # SWMA индикаторы
    for period in [20]:
        key = f"swma_{period}"
        if key in available:
            swma_series = safe_ta_with_fallback(df, "swma", length=period)
            result[key] = swma_series

    # PWMA индикаторы
    for period in [20]:
        key = f"pwma_{period}"
        if key in available:
            pwma_series = safe_ta_with_fallback(df, "pwma", length=period)
            result[key] = pwma_series

    # HWMA индикаторы
    for period in [20]:
        key = f"hwma_{period}"
        if key in available:
            hwma_series = safe_ta_with_fallback(df, "hwma", length=period)
            result[key] = hwma_series

    # LINREG индикаторы
    for period in [20]:
        key = f"linreg_{period}"
        if key in available:
            linreg_series = safe_ta_with_fallback(df, "linreg", length=period)
            result[key] = linreg_series

    log_group_results("MA", result)
    return result
