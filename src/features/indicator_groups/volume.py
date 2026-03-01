"""
Volume Indicators Module

Group: Volume
Dependencies: volume, close, high, low
Max Lookback: 50 bars
Output Fields: obv, cmf, vwap, mfi, volume_sma_20

This module calculates volume-based indicators for analyzing market participation:
- OBV (On-Balance Volume): Cumulative volume based on price direction
- CMF (Chaikin Money Flow): Money flow over a period
- VWAP (Volume Weighted Average Price): Average price weighted by volume
- MFI (Money Flow Index): Volume-weighted RSI
- Volume SMA: Simple moving average of volume
"""

import numpy as np
import pandas as pd

from src.logging import get_logger

from ..ta_safe import safe_ta_with_fallback
from ..utils.indicator_utils import check_min_length

logger = get_logger(__name__)


def calc_volume_indicators(
    df: pd.DataFrame, available: set[str], **kwargs
) -> dict[str, pd.Series]:
    """
    Calculate Volume indicators for market participation analysis.

    Args:
        df: DataFrame with OHLCV data (must have 'open', 'high', 'low', 'close', 'volume' columns)
        available: Set of indicator names to calculate
        **kwargs: Additional parameters (unused, for Protocol compliance)

    Returns:
        Dictionary mapping indicator names to pandas Series with calculated values

    Example:
        >>> volume_indicators = calc_volume_indicators(df, {'obv', 'cmf', 'vwap'})
        >>> obv = volume_indicators['obv']
    """
    result: dict[str, pd.Series] = {}

    # OBV
    if "obv" in available:
        obv_series = safe_ta_with_fallback(df, "obv")
        result["obv"] = obv_series

    # CMF
    if "cmf" in available:
        cmf_series = safe_ta_with_fallback(df, "cmf", length=20)
        result["cmf"] = cmf_series

    # VWAP - упрощенная версия
    if "vwap" in available:
        try:
            typical_price = (df["high"] + df["low"] + df["close"]) / 3
            vwap_series = (typical_price * df["volume"]).cumsum() / df[
                "volume"
            ].cumsum()
            result["vwap"] = vwap_series
        except Exception as e:
            print(f"❌ Ошибка VWAP: {e}")
            result["vwap"] = pd.Series([np.nan] * len(df), index=df.index)

    # Volume SMA
    if "volume_sma20" in available:
        volume_sma_series = safe_ta_with_fallback(df, "sma", length=20)
        result["volume_sma20"] = volume_sma_series

    # Money Flow Index
    if "mfi" in available:
        mfi_series = safe_ta_with_fallback(df, "mfi", length=14)
        result["mfi"] = mfi_series

    # Accumulation/Distribution
    if "ad" in available:
        ad_series = safe_ta_with_fallback(df, "ad")
        result["ad"] = ad_series

    # A/D Oscillator
    if "adosc" in available:
        adosc_series = safe_ta_with_fallback(df, "adosc", fast=3, slow=10)
        result["adosc"] = adosc_series

    # Volume Weighted Moving Average
    if "vwma" in available:
        vwma_series = safe_ta_with_fallback(df, "vwma", length=20)
        result["vwma"] = vwma_series

    # Volume Profile indicators (вызываем один раз)
    if (
        "vp_point_of_control" in available
        or "vp_value_area_high" in available
        or "vp_value_area_low" in available
    ):
        if not check_min_length(df, "vp"):
            logger.warning("VP: недостаточно данных (len<50), возвращаю NaN")
            if "vp_point_of_control" in available:
                result["vp_point_of_control"] = pd.Series(
                    [np.nan] * len(df), index=df.index
                )
            if "vp_value_area_high" in available:
                result["vp_value_area_high"] = pd.Series(
                    [np.nan] * len(df), index=df.index
                )
            if "vp_value_area_low" in available:
                result["vp_value_area_low"] = pd.Series(
                    [np.nan] * len(df), index=df.index
                )
            return result
        vp_result = safe_ta_with_fallback(df, "vp")
        if isinstance(vp_result, pd.DataFrame):
            # ta_safe.fallback возвращает 'vpc', 'vah', 'val' (lowercase)
            if "vp_point_of_control" in available:
                col = next((c for c in vp_result.columns if c.lower() == "vpc"), None)
                result["vp_point_of_control"] = (
                    vp_result[col]
                    if col is not None
                    else pd.Series([np.nan] * len(df), index=df.index)
                )
            if "vp_value_area_high" in available:
                col = next((c for c in vp_result.columns if c.lower() == "vah"), None)
                result["vp_value_area_high"] = (
                    vp_result[col]
                    if col is not None
                    else pd.Series([np.nan] * len(df), index=df.index)
                )
            if "vp_value_area_low" in available:
                col = next((c for c in vp_result.columns if c.lower() == "val"), None)
                result["vp_value_area_low"] = (
                    vp_result[col]
                    if col is not None
                    else pd.Series([np.nan] * len(df), index=df.index)
                )
        else:
            logger.warning("VP: результат не DataFrame, возвращаю NaN")
            if "vp_point_of_control" in available:
                result["vp_point_of_control"] = pd.Series(
                    [np.nan] * len(df), index=df.index
                )
            if "vp_value_area_high" in available:
                result["vp_value_area_high"] = pd.Series(
                    [np.nan] * len(df), index=df.index
                )
            if "vp_value_area_low" in available:
                result["vp_value_area_low"] = pd.Series(
                    [np.nan] * len(df), index=df.index
                )

    # Negative Volume Index
    if "nvi" in available:
        nvi_series = safe_ta_with_fallback(df, "nvi")
        result["nvi"] = nvi_series

    # Positive Volume Index
    if "pvi" in available:
        pvi_series = safe_ta_with_fallback(df, "pvi")
        result["pvi"] = pvi_series

    # Price Volume Trend
    if "pvt" in available:
        pvt_series = safe_ta_with_fallback(df, "pvt")
        result["pvt"] = pvt_series

    return result
