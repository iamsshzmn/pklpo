"""Utility helpers for cleaning indicator input data."""

import numpy as np
import pandas as pd

from src.logging import get_logger

logger = get_logger(__name__)


def _clean_series(series: pd.Series) -> pd.Series:
    """Normalize a series by dropping None, NaN, and infinite values."""
    return series.replace([None, np.nan, float("inf"), float("-inf")], np.nan).dropna()


def _log_insufficient_data(
    symbol_name: str,
    timeframe_name: str,
    min_length: int,
    actual_length: int,
    original_length: int,
):
    """Log that the cleaned input does not meet the minimum length."""
    logger.warning(
        f"Insufficient data after cleaning for {symbol_name} {timeframe_name}: need {min_length}+, got {actual_length} (original: {original_length})"
    )


def clean_ohlcv_data(
    df: pd.DataFrame, min_length: int = 14
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, bool]:
    """
    Clean OHLCV columns by removing None and NaN values.

    Args:
        df: DataFrame with OHLCV columns
        min_length: Minimum required series length

    Returns:
        tuple: (open_clean, high_clean, low_clean, close_clean, has_sufficient_data)
    """
    try:
        open_clean = _clean_series(df["open"])
        high_clean = _clean_series(df["high"])
        low_clean = _clean_series(df["low"])
        close_clean = _clean_series(df["close"])

        # Check the shortest cleaned OHLCV column.
        min_available_length = min(
            len(open_clean), len(high_clean), len(low_clean), len(close_clean)
        )
        has_sufficient_data = min_available_length >= min_length

        if not has_sufficient_data:
            symbol_name = getattr(df, "name", "unknown")
            timeframe_name = getattr(df, "timeframe", "unknown")
            _log_insufficient_data(
                symbol_name, timeframe_name, min_length, min_available_length, len(df)
            )

        return open_clean, high_clean, low_clean, close_clean, has_sufficient_data

    except Exception as e:
        symbol_name = getattr(df, "name", "unknown")
        timeframe_name = getattr(df, "timeframe", "unknown")
        logger.error(
            f"Error cleaning OHLCV data for {symbol_name} {timeframe_name}: {e}"
        )
        return pd.Series(), pd.Series(), pd.Series(), pd.Series(), False


def clean_close_data(df: pd.DataFrame, min_length: int = 14) -> tuple[pd.Series, bool]:
    """
    Clean only the close column for indicators such as RSI and MACD.

    Args:
        df: DataFrame with OHLCV columns
        min_length: Minimum required series length

    Returns:
        tuple: (close_clean, has_sufficient_data)
    """
    try:
        close_clean = _clean_series(df["close"])

        # Keep only valid close values.
        close_clean = close_clean.loc[close_clean.notna()]

        has_sufficient_data = len(close_clean) >= min_length

        if not has_sufficient_data:
            symbol_name = getattr(df, "name", "unknown")
            timeframe_name = getattr(df, "timeframe", "unknown")
            _log_insufficient_data(
                symbol_name, timeframe_name, min_length, len(close_clean), len(df)
            )

        return close_clean, has_sufficient_data

    except Exception as e:
        symbol_name = getattr(df, "name", "unknown")
        timeframe_name = getattr(df, "timeframe", "unknown")
        logger.error(
            f"Error cleaning close data for {symbol_name} {timeframe_name}: {e}"
        )
        return pd.Series(), False


def create_nan_series(df: pd.DataFrame, length: int | None = None) -> pd.Series:
    """
    Create a NaN series aligned with the input DataFrame.

    Args:
        df: Source DataFrame
        length: Optional series length, defaults to len(df)

    Returns:
        pd.Series filled with NaN values
    """
    if length is None:
        length = len(df)
    return pd.Series([np.nan] * length, index=df.index)
