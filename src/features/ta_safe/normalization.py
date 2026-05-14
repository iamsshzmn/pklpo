"""
Normalization functions for ta_safe module.

This module provides functions for normalizing indicator names and results
to match the project's naming conventions.
"""

import re

import pandas as pd

from ..schema.name_aliases import NAME_ALIASES


def _auto_rename(col: str) -> str:
    """
    Auto-rename columns using regex patterns.

    Args:
        col: Column name to rename

    Returns:
        Normalized column name
    """
    # MACD
    m = re.fullmatch(r"MACD_(\d+)_(\d+)_(\d+)", col)
    if m:
        return "macd"
    m = re.fullmatch(r"MACDs_(\d+)_(\d+)_(\d+)", col)
    if m:
        return "macd_signal"
    m = re.fullmatch(r"MACDh_(\d+)_(\d+)_(\d+)", col)
    if m:
        return "macd_histogram"
    # BBANDS
    m = re.fullmatch(r"BBL_(\d+)_([0-9.]+)", col)
    if m:
        return "bb_lower"
    m = re.fullmatch(r"BBM_(\d+)_([0-9.]+)", col)
    if m:
        return "bb_middle"
    m = re.fullmatch(r"BBU_(\d+)_([0-9.]+)", col)
    if m:
        return "bb_upper"
    # RSI/ATR/ADX/AROON
    m = re.fullmatch(r"RSI_(\d+)", col)
    if m:
        return f"rsi_{m.group(1)}"
    m = re.fullmatch(r"ATRr?_(\d+)", col)
    if m:
        return f"atr_{m.group(1)}"
    m = re.fullmatch(r"ADX_(\d+)", col)
    if m:
        return f"adx_{m.group(1)}"
    m = re.fullmatch(r"DMP_(\d+)", col)
    if m:
        return "adx_pos_di"
    m = re.fullmatch(r"DMN_(\d+)", col)
    if m:
        return "adx_neg_di"
    m = re.fullmatch(r"AROONU_(\d+)", col)
    if m:
        return "aroon_up"
    m = re.fullmatch(r"AROOND_(\d+)", col)
    if m:
        return "aroon_down"
    # KC: KCL/KCM/KCU_20_2.0 or kcle/kcbe/kcue_20_2.0
    m = re.fullmatch(r"KCL[E]?_(\d+)_([0-9.]+)", col, re.IGNORECASE)
    if m:
        return "kc_lower"
    m = re.fullmatch(r"KCM_(\d+)_([0-9.]+)", col)
    if m:
        return "kc_middle"
    m = re.fullmatch(r"KCBE_(\d+)_([0-9.]+)", col, re.IGNORECASE)
    if m:
        return "kc_middle"
    m = re.fullmatch(r"KCU[E]?_(\d+)_([0-9.]+)", col, re.IGNORECASE)
    if m:
        return "kc_upper"
    # Ichimoku: ISA/ISB/ITS/IKS/ICS/IKH_X
    m = re.fullmatch(r"ISA_(\d+)", col)
    if m:
        return "ichimoku_senkou_a"
    m = re.fullmatch(r"ISB_(\d+)", col)
    if m:
        return "ichimoku_senkou_b"
    m = re.fullmatch(r"ITS_(\d+)", col)
    if m:
        return "ichimoku_tenkan"
    m = re.fullmatch(r"IKS_(\d+)", col)
    if m:
        return "ichimoku_kijun"
    m = re.fullmatch(r"ICS_(\d+)", col)
    if m:
        return "ichimoku_chikou"
    m = re.fullmatch(r"IKH_\w+", col)
    if m:
        return col.lower()
    # Supertrend: SUPERT_*, SUPERTd_*, SUPERTl_*, SUPERTs_*
    m = re.fullmatch(r"SUPERT_(\d+)_([0-9.]+)", col)
    if m:
        return "supertrend"
    m = re.fullmatch(r"SUPERTd_(\d+)_([0-9.]+)", col)
    if m:
        return "supertrend_direction"
    m = re.fullmatch(r"SUPERTl_(\d+)_([0-9.]+)", col)
    if m:
        return "supertrend_long"
    m = re.fullmatch(r"SUPERTs_(\d+)_([0-9.]+)", col)
    if m:
        return "supertrend_short"
    # PSAR: PSARl_*, PSARs_*, PSARaf_*, PSARr_*
    m = re.fullmatch(r"PSARl_([0-9.]+)_([0-9.]+)", col)
    if m:
        return "psar_long"
    m = re.fullmatch(r"PSARs_([0-9.]+)_([0-9.]+)", col)
    if m:
        return "psar_short"
    m = re.fullmatch(r"PSARaf_([0-9.]+)_([0-9.]+)", col)
    if m:
        return "psar_af"
    m = re.fullmatch(r"PSARr_([0-9.]+)_([0-9.]+)", col)
    if m:
        return "psar_reversal"
    # UO and WILLR
    if col.upper() == "UO":
        return "ultosc"
    if col.upper() == "WILLR" or col.upper().startswith("WILLR_"):
        return "willr"
    # default
    return col.lower()


def _rename_like_specs(df_out: pd.DataFrame) -> pd.DataFrame:
    """
    Rename columns to match our specs.

    Args:
        df_out: DataFrame to rename

    Returns:
        DataFrame with renamed columns
    """
    df_out.columns = [NAME_ALIASES.get(c, _auto_rename(c)) for c in df_out.columns]
    return df_out


def _normalize_to_df(
    out: pd.DataFrame | pd.Series | None,
    name: str,
    df: pd.DataFrame,
    **kwargs: dict[str, object],
) -> pd.DataFrame:
    """
    Normalize result to a DataFrame with correct names and index.

    Special handling for BB and Ichimoku unpacking.

    Args:
        out: Calculation result (DataFrame, Series, or None)
        name: Indicator name
        df: Source DataFrame
        **kwargs: Additional parameters

    Returns:
        Normalized DataFrame

    Raises:
        FeatureCalcError: If result length mismatches input or object-dtype columns exist
    """
    import numpy as np

    from .errors import FeatureCalcError

    # If library returned None/empty — return NaN column of correct length
    if out is None or callable(out):
        return pd.Series([np.nan] * len(df), index=df.index).to_frame(name)

    if isinstance(out, pd.Series):
        col = out.name or name
        out = out.to_frame(col)
    elif not isinstance(out, pd.DataFrame):
        return pd.Series([np.nan] * len(df), index=df.index).to_frame(name)

    # Special BB handling: explicit unpack into named columns
    if name == "bbands":
        # If pandas_ta returned DataFrame with non-standard names, rename them
        cols = list(out.columns)
        if len(cols) >= 3:
            # Expected order: lower, middle, upper
            # Or search by prefix
            col_lower = next(
                (c for c in cols if "BBL" in c.upper() or "lower" in c.lower()), None
            )
            col_middle = next(
                (c for c in cols if "BBM" in c.upper() or "middle" in c.lower()), None
            )
            col_upper = next(
                (c for c in cols if "BBU" in c.upper() or "upper" in c.lower()), None
            )

            if col_lower and col_middle and col_upper:
                out = out[[col_lower, col_middle, col_upper]].copy()
                out.columns = ["bb_lower", "bb_middle", "bb_upper"]
            elif len(cols) == 3:
                # If 3 columns with no explicit names, assume order: lower, middle, upper
                out.columns = ["bb_lower", "bb_middle", "bb_upper"]
        else:
            # Fallback: create empty columns
            out = pd.DataFrame(
                {
                    "bb_lower": [np.nan] * len(df),
                    "bb_middle": [np.nan] * len(df),
                    "bb_upper": [np.nan] * len(df),
                },
                index=df.index,
            )

    # Special Ichimoku handling: explicit unpack into 5 components
    elif name == "ichimoku":
        # If pandas_ta returned tuple or list, take first element
        if isinstance(out, list | tuple):
            out = out[0] if len(out) > 0 else pd.DataFrame()

        # If DataFrame returned with non-standard names, rename them
        if isinstance(out, pd.DataFrame):
            cols = list(out.columns)
            # Mapping of possible pandas_ta names to ours
            ichimoku_mapping = {
                "ITS_9": "ichimoku_tenkan",
                "IKS_26": "ichimoku_kijun",
                "ISA_9": "ichimoku_senkou_a",
                "ISB_26": "ichimoku_senkou_b",
                "ICS_26": "ichimoku_chikou",
            }
            # Rename matched columns
            rename_dict = {}
            for col in cols:
                for ta_name, our_name in ichimoku_mapping.items():
                    if ta_name in col or col.startswith(ta_name):
                        rename_dict[col] = our_name
                        break

            if rename_dict:
                out = out.rename(columns=rename_dict)

            # If after renaming some columns are missing, add them
            required_cols = [
                "ichimoku_tenkan",
                "ichimoku_kijun",
                "ichimoku_senkou_a",
                "ichimoku_senkou_b",
                "ichimoku_chikou",
            ]
            missing_cols = set(required_cols) - set(out.columns)
            if missing_cols:
                for col in missing_cols:
                    out[col] = np.nan
            # Keep only required columns in correct order
            out = out[required_cols].copy()
        else:
            # Fallback: create empty columns
            out = pd.DataFrame(
                {
                    "ichimoku_tenkan": [np.nan] * len(df),
                    "ichimoku_kijun": [np.nan] * len(df),
                    "ichimoku_senkou_a": [np.nan] * len(df),
                    "ichimoku_senkou_b": [np.nan] * len(df),
                    "ichimoku_chikou": [np.nan] * len(df),
                },
                index=df.index,
            )

    # Rename to spec names (for remaining indicators)
    if name not in ("bbands", "ichimoku"):
        out = _rename_like_specs(out)

    # If no columns remain after normalization — return NaN column
    if out.shape[1] == 0:
        return pd.Series([np.nan] * len(df), index=df.index).to_frame(name)

    # Index must match input exactly
    if not out.index.equals(df.index):
        out = out.reindex(df.index, fill_value=np.nan)

    # Hard length check after reindex
    if len(out) != len(df):
        raise FeatureCalcError(
            f"result length != input length: {len(out)} != {len(df)}"
        )

    # Numeric types only (do not downcast bool)
    num = out.select_dtypes(include=["number"]).columns.difference(
        out.select_dtypes(include=["bool"]).columns
    )
    # Explicit type cast before assignment to avoid FutureWarning
    # Use pd.to_numeric for safe conversion
    for col in num:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("float64")
    bad = [c for c in out.columns if out[c].dtype == "object"]
    if bad:
        raise FeatureCalcError(f"object-dtype columns not allowed: {bad}")

    return out
