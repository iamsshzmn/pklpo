"""
Normalization functions for indicator data.
"""

import numpy as np
import pandas as pd

from src.logging import get_logger

logger = get_logger(__name__)


def sanitize_column_names(ind_df: pd.DataFrame) -> pd.DataFrame:
    """
    Sanitize column names: strip, lowercase, replace spaces with underscores.

    Args:
        ind_df: DataFrame with columns to sanitize

    Returns:
        DataFrame with sanitized column names
    """
    ind_df.columns = (
        ind_df.columns.str.strip()
        .str.lower()
        .str.replace(r"\s+", "_", regex=True)
        .str.replace(r"[^a-z0-9_]", "", regex=True)
    )
    return ind_df


def normalize_numeric_columns(ind_df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize numeric columns: replace inf with NaN, convert to float64.

    Args:
        ind_df: DataFrame with numeric columns to normalize

    Returns:
        DataFrame with normalized numeric columns
    """
    numeric_cols = ind_df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 0:
        ind_df[numeric_cols] = (
            ind_df[numeric_cols].replace([np.inf, -np.inf], np.nan).astype("float64")
        )

    if len(ind_df) > 0:
        ind_df = ind_df.replace([np.inf, -np.inf], np.nan)

    if len(ind_df) > 1000:
        logger.info(
            f"Large batch detected ({len(ind_df)} rows), using vectorized processing"
        )
        for col in numeric_cols:
            ind_df[col] = ind_df[col].replace([np.inf, -np.inf], np.nan)

    return ind_df


def normalize_timestamp_column(ind_df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize timestamp column to milliseconds.

    Args:
        ind_df: DataFrame with timestamp column

    Returns:
        DataFrame with normalized timestamp column

    Raises:
        ValueError: If timestamp column is missing
    """

    def _normalize_epoch_series(ts_s: pd.Series) -> pd.Series:
        ts_int = ts_s.astype("int64")
        return pd.Series(
            np.where(ts_int > 10**12, ts_int, ts_int * 1000).astype("int64"),
            index=ts_s.index,
        )

    # `ts` is the canonical pipeline timestamp. If both columns are present,
    # prefer it over a computed `timestamp` feature column.
    if "ts" in ind_df.columns:
        ind_df["timestamp"] = _normalize_epoch_series(ind_df["ts"])
        logger.info("Created 'timestamp' column from canonical 'ts' column")
    elif "timestamp" in ind_df.columns:
        ind_df["timestamp"] = _normalize_epoch_series(ind_df["timestamp"])
        logger.info("Normalized existing 'timestamp' column to milliseconds")
    else:
        raise ValueError("Missing required 'ts' or 'timestamp' column before filtering")

    return ind_df


def add_service_fields(
    ind_df: pd.DataFrame, symbol: str, timeframe: str
) -> pd.DataFrame:
    """
    Add service fields (symbol, timeframe) to DataFrame.

    Args:
        ind_df: DataFrame to add fields to
        symbol: Symbol value
        timeframe: Timeframe value

    Returns:
        DataFrame with added service fields
    """
    ind_df["symbol"] = symbol
    ind_df["timeframe"] = timeframe
    return ind_df


def filter_columns_by_schema(ind_df: pd.DataFrame, db_cols: set[str]) -> pd.DataFrame:
    """
    Filter DataFrame columns to match database schema.

    Args:
        ind_df: DataFrame to filter
        db_cols: Set of database column names

    Returns:
        Filtered DataFrame
    """
    common_cols = [
        c
        for c in ind_df.columns
        if c in db_cols
        or c in ("timestamp", "symbol", "timeframe", "calculated_at", "ts")
    ]
    ind_df = ind_df.reindex(columns=common_cols, fill_value=np.nan)
    logger.info(f"Filtered DataFrame with service fields: {ind_df.shape}")
    logger.info(f"Total columns available: {len(common_cols)}")
    logger.info(
        f"Sample columns: {sorted(common_cols)[:20]}{'...' if len(common_cols) > 20 else ''}"
    )
    return ind_df
