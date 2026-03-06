"""
Overlap Indicators Module

Group: Overlap
Dependencies: OHLC only
Max Lookback: 1 bar (no lag)
Output Fields: hlc3, hl2, ohlc4, wcp (weighted close price)

This module calculates basic price representations used by other indicators.
It strictly honors the `available` set: only explicitly requested indicators
are computed here. Dependencies must be resolved upstream.
"""

import numpy as np
import pandas as pd

from src.logging import get_logger

from .registry import GroupRegistry

logger = get_logger(__name__)


@GroupRegistry.register(
    "overlap",
    order=0,
    dependencies=[],
    description="Basic price transformations (hl2, hlc3, ohlc4, wcp)",
)
def calc_overlap_indicators(
    df: pd.DataFrame, available: set[str], **kwargs
) -> dict[str, pd.Series]:
    """
    Calculate Overlap indicators (basic price transformations).

    Args:
        df: DataFrame with OHLC data (must have 'open', 'high', 'low', 'close' columns)
        available: Set of indicator names to calculate
        **kwargs: Additional parameters (unused, for Protocol compliance)

    Returns:
        Dict mapping indicator names to pandas Series with calculated values

    Contract:
        - Only compute indicators explicitly requested in `available`.
        - Do not force-compute critical indicators; dependencies should be resolved upstream.
    """
    result: dict[str, pd.Series] = {}

    logger.debug(f"calc_overlap_indicators: available={sorted(available)}")
    overlap_keys = {"hl2", "midpoint", "midprice", "hlc3", "ohlc4", "wcp"}
    overlap_in_available = overlap_keys.intersection(set(available))
    logger.debug(
        f"calc_overlap_indicators: overlap indicators in available: {sorted(overlap_in_available)}"
    )

    # hl2 / midpoint / midprice
    if {"hl2", "midpoint", "midprice"} & available:
        hl2 = (df["high"].astype(float) + df["low"].astype(float)) / 2.0
        result["hl2"] = hl2
        if "midpoint" in available:
            result["midpoint"] = hl2
        if "midprice" in available:
            result["midprice"] = hl2
        logger.debug(
            f"calc_overlap_indicators: calculated hl2: {hl2.notna().sum()}/{len(hl2)} non-null"
        )

    # hlc3
    if "hlc3" in available:
        try:
            hlc3_series = (
                df["high"].astype(float)
                + df["low"].astype(float)
                + df["close"].astype(float)
            ) / 3.0
            result["hlc3"] = hlc3_series
            logger.debug(
                f"calc_overlap_indicators: calculated hlc3: {hlc3_series.notna().sum()}/{len(hlc3_series)} non-null"
            )
        except Exception as e:
            logger.error(f"calc_overlap_indicators: error calculating hlc3: {e}")
            result["hlc3"] = pd.Series([np.nan] * len(df), index=df.index)

    # ohlc4
    if "ohlc4" in available:
        ohlc4_series = (
            df["open"].astype(float)
            + df["high"].astype(float)
            + df["low"].astype(float)
            + df["close"].astype(float)
        ) / 4.0
        result["ohlc4"] = ohlc4_series
        logger.debug(
            f"calc_overlap_indicators: calculated ohlc4: {ohlc4_series.notna().sum()}/{len(ohlc4_series)} non-null"
        )

    # wcp
    if "wcp" in available:
        # Weighted Close Price: default weights o:h:l:c = 1:1:1:2
        o = df["open"].astype(float)
        h = df["high"].astype(float)
        low = df["low"].astype(float)
        c = df["close"].astype(float)
        wcp_series = (o + h + low + 2.0 * c) / 5.0
        result["wcp"] = wcp_series
        logger.debug(
            f"calc_overlap_indicators: calculated wcp: {wcp_series.notna().sum()}/{len(wcp_series)} non-null"
        )

    # Ensure missing requested keys for THIS GROUP only are present as NaN series
    for key in overlap_in_available:
        if key not in result:
            result[key] = pd.Series([np.nan] * len(df), index=df.index)

    # Debug log for hlc3
    if "hlc3" in result:
        hlc3_series = result["hlc3"]
        non_null_count = hlc3_series.notna().sum()
        logger.debug(f"overlap hlc3 non-null: {non_null_count}/{len(hlc3_series)}")
        if non_null_count > 0:
            logger.debug(f"overlap hlc3 head(2): {hlc3_series.head(2).tolist()}")

    return result
