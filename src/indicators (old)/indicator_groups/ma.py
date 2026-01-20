import numpy as np
import pandas as pd
import pandas_ta as ta


def calc_ma_indicators(df: pd.DataFrame, available: set) -> dict:
    result = {}

    # EMA индикаторы
    for period in [12, 21, 26, 50, 200]:
        key = f"ema{period}"
        if key in available:
            ema_series = ta.ema(df["close"], length=period)
            result[key] = (
                ema_series
                if ema_series is not None
                else pd.Series([np.nan] * len(df), index=df.index)
            )

    # EMA21 (отдельно для совместимости с правилами сигналов)
    if "ema21" in available:
        ema_series = ta.ema(df["close"], length=21)
        result["ema21"] = (
            ema_series
            if ema_series is not None
            else pd.Series([np.nan] * len(df), index=df.index)
        )

    # EMA-Ribbon
    for period in [8, 13, 21, 34, 55, 89, 144, 233]:
        key = f"ema_{period}"
        if key in available:
            ema_series = ta.ema(df["close"], length=period)
            result[key] = (
                ema_series
                if ema_series is not None
                else pd.Series([np.nan] * len(df), index=df.index)
            )

    # SMA индикаторы
    for period in [34, 50, 200]:
        key = f"sma{period}"
        if key in available:
            sma_series = ta.sma(df["close"], length=period)
            result[key] = (
                sma_series
                if sma_series is not None
                else pd.Series([np.nan] * len(df), index=df.index)
            )

    return result
