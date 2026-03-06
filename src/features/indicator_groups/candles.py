import numpy as np
import pandas as pd

from .registry import GroupRegistry


def _heikin_ashi(df: pd.DataFrame) -> dict[str, pd.Series]:
    ha_close = (df["open"] + df["high"] + df["low"] + df["close"]) / 4.0
    ha_open = ha_close.copy()
    if len(df) > 0:
        ha_open.iloc[0] = (df["open"].iloc[0] + df["close"].iloc[0]) / 2.0
    for i in range(1, len(df)):
        ha_open.iloc[i] = (ha_open.iloc[i - 1] + ha_close.iloc[i - 1]) / 2.0
    ha_high = pd.concat([df["high"], ha_open, ha_close], axis=1).max(axis=1)
    ha_low = pd.concat([df["low"], ha_open, ha_close], axis=1).min(axis=1)
    return {
        "ha_open": ha_open,
        "ha_high": ha_high,
        "ha_low": ha_low,
        "ha_close": ha_close,
    }


def _cdl_doji(df: pd.DataFrame, threshold: float = 0.1) -> pd.Series:
    body = (df["close"] - df["open"]).abs()
    range_ = (df["high"] - df["low"]).replace(0, np.nan)
    ratio = (body / range_).fillna(0)
    return (ratio <= threshold).astype(int)


def _cdl_inside(df: pd.DataFrame) -> pd.Series:
    prev_high = df["high"].shift(1)
    prev_low = df["low"].shift(1)
    inside = (df["high"] <= prev_high) & (df["low"] >= prev_low)
    return inside.astype(int)


@GroupRegistry.register(
    "candles",
    order=7,
    dependencies=["overlap"],
    description="Candlestick patterns",
)
def calc_candles_indicators(
    df: pd.DataFrame, available: set[str], **kwargs
) -> dict[str, pd.Series]:
    """
    Calculate candlestick pattern indicators.

    Args:
        df: DataFrame with OHLC data
        available: Set of indicator names to calculate
        **kwargs: Additional parameters (unused, for Protocol compliance)

    Returns:
        Dictionary mapping indicator names to pandas Series
    """
    result: dict[str, pd.Series] = {}

    need_ha = any(k in available for k in ["ha_open", "ha_high", "ha_low", "ha_close"])
    if need_ha:
        ha = _heikin_ashi(df)
        for k in ["ha_open", "ha_high", "ha_low", "ha_close"]:
            if k in available:
                result[k] = ha[k]

    if "cdl_doji" in available:
        result["cdl_doji"] = _cdl_doji(df)

    if "cdl_inside" in available:
        result["cdl_inside"] = _cdl_inside(df)

    return result
