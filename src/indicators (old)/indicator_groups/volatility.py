import numpy as np
import pandas as pd
import pandas_ta as ta


def calc_volatility_indicators(df: pd.DataFrame, available: set) -> dict:
    result = {}
    # Bollinger Bands
    if "bb_upper" in available or "bb_middle" in available or "bb_lower" in available:
        bb = ta.bbands(df["close"], length=20, std=2)
        if bb is not None:
            if "bb_upper" in available and "BBU_20_2.0" in bb:
                result["bb_upper"] = bb["BBU_20_2.0"]
            if "bb_middle" in available and "BBM_20_2.0" in bb:
                result["bb_middle"] = bb["BBM_20_2.0"]
            if "bb_lower" in available and "BBL_20_2.0" in bb:
                result["bb_lower"] = bb["BBL_20_2.0"]
        else:
            if "bb_upper" in available:
                result["bb_upper"] = pd.Series([np.nan] * len(df), index=df.index)
            if "bb_middle" in available:
                result["bb_middle"] = pd.Series([np.nan] * len(df), index=df.index)
            if "bb_lower" in available:
                result["bb_lower"] = pd.Series([np.nan] * len(df), index=df.index)
    # Keltner Channel
    if "kc_upper" in available or "kc_middle" in available or "kc_lower" in available:
        kc = ta.kc(df["high"], df["low"], df["close"], length=20, scalar=2)
        if kc is not None:
            if "kc_upper" in available and "KCUe_20_2.0" in kc:
                result["kc_upper"] = kc["KCUe_20_2.0"]
            if "kc_middle" in available and "KCBe_20_2.0" in kc:
                result["kc_middle"] = kc["KCBe_20_2.0"]
            if "kc_lower" in available and "KCLe_20_2.0" in kc:
                result["kc_lower"] = kc["KCLe_20_2.0"]
        else:
            if "kc_upper" in available:
                result["kc_upper"] = pd.Series([np.nan] * len(df), index=df.index)
            if "kc_middle" in available:
                result["kc_middle"] = pd.Series([np.nan] * len(df), index=df.index)
            if "kc_lower" in available:
                result["kc_lower"] = pd.Series([np.nan] * len(df), index=df.index)
    # ATR
    if "atr14" in available:
        atr_series = ta.atr(df["high"], df["low"], df["close"], length=14)
        result["atr14"] = (
            atr_series
            if atr_series is not None
            else pd.Series([np.nan] * len(df), index=df.index)
        )
    return result
