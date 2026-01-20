"""
Time normalization utilities for features module.

This module provides consistent time handling across the features pipeline,
ensuring all timestamps are normalized to UTC milliseconds as per plan requirements.
All timestamps must be in UTC milliseconds - no "sec vs ms" context switching.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def normalize_timestamp_to_milliseconds(
    timestamp: pd.Series | pd.Timestamp | int | float | str | None,
) -> pd.Series | int | None:
    """
    Normalize timestamp to UTC milliseconds (int64).

    STRICT REQUIREMENT: All timestamps must be in UTC milliseconds.
    No "sec vs ms" context switching allowed per plan.

    Handles various input formats:
    - pd.Timestamp: convert to UTC milliseconds
    - int/float: assume milliseconds if > 1e12, otherwise convert seconds to ms
    - str: parse as datetime and convert to UTC milliseconds
    - pd.Series: apply normalization element-wise
    - None: return None

    Args:
        timestamp: Input timestamp in various formats

    Returns:
        Normalized timestamp in UTC milliseconds (int64) or None
    """
    if timestamp is None:
        return None

    if isinstance(timestamp, pd.Series):
        result = timestamp.apply(normalize_timestamp_to_milliseconds)
        # Convert None values to pd.NA for proper nullable integer dtype
        return result.replace({None: pd.NA})

    if isinstance(timestamp, pd.Timestamp):
        # Ensure UTC timezone
        ts: pd.Timestamp = timestamp
        if ts.tz is None:
            ts = ts.tz_localize("UTC")
        elif ts.tz != pd.Timestamp.now(tz="UTC").tz:
            ts = ts.tz_convert("UTC")
        return int(ts.timestamp() * 1000)

    if isinstance(timestamp, str):
        try:
            ts = pd.to_datetime(timestamp)
            if ts.tz is None:
                ts = ts.tz_localize("UTC")
            elif ts.tz != pd.Timestamp.now(tz="UTC").tz:
                ts = ts.tz_convert("UTC")
            return int(ts.timestamp() * 1000)
        except Exception as e:
            logger.warning(f"Failed to parse timestamp string '{timestamp}': {e}")
            return None

    if isinstance(timestamp, int | float | np.integer | np.floating):
        ts_num = float(timestamp)

        # Handle NaN
        if pd.isna(ts_num):
            return None

        # If timestamp > 1e12, assume it's already in milliseconds
        if ts_num > 1e12:
            return int(ts_num)
        # Convert seconds to milliseconds
        return int(ts_num * 1000)

    logger.warning(f"Unsupported timestamp type: {type(timestamp)}")
    return None


def normalize_timestamp_to_seconds(
    timestamp: pd.Series | pd.Timestamp | int | float | str | None,
) -> pd.Series | int | None:
    """Normalize timestamp to UTC seconds."""
    normalized = normalize_timestamp_to_milliseconds(timestamp)
    if normalized is None:
        return None

    if isinstance(normalized, pd.Series):
        return normalized.apply(
            lambda x: int(x // 1000) if pd.notna(x) else pd.NA  # type: ignore[arg-type]
        )

    return int(normalized // 1000)


def ensure_ts_column(
    df: pd.DataFrame, timestamp_col: str = "timestamp"
) -> pd.DataFrame:
    """
    Ensure DataFrame has a 'ts' column in UTC milliseconds.

    STRICT REQUIREMENT: All timestamps must be in UTC milliseconds per plan.

    Args:
        df: Input DataFrame
        timestamp_col: Name of the timestamp column to normalize

    Returns:
        DataFrame with 'ts' column in UTC milliseconds
    """
    result_df = df.copy()

    if "ts" in result_df.columns:
        # Already has ts column, ensure it's in seconds
        result_df["ts"] = normalize_timestamp_to_seconds(result_df["ts"])
        return result_df

    if timestamp_col in result_df.columns:
        # Normalize the timestamp column to ts in seconds
        result_df["ts"] = normalize_timestamp_to_seconds(result_df[timestamp_col])
        return result_df

    if isinstance(result_df.index, pd.DatetimeIndex):
        # Use index as timestamp source - convert DatetimeIndex to Series first
        result_df["ts"] = normalize_timestamp_to_seconds(pd.Series(result_df.index))
        return result_df

    # Fallback: create sequential ts based on index
    logger.warning("No timestamp column found, creating sequential ts from index")
    result_df["ts"] = result_df.index.astype("int64")

    return result_df


def validate_timestamp_consistency(df: pd.DataFrame, ts_col: str = "ts") -> bool:
    """
    Validate that timestamps are consistent, monotonic, and in UTC milliseconds.

    STRICT REQUIREMENT: All timestamps must be in UTC milliseconds per plan.

    Args:
        df: DataFrame to validate
        ts_col: Name of the timestamp column

    Returns:
        True if timestamps are valid, False otherwise
    """
    if ts_col not in df.columns:
        logger.error(f"Timestamp column '{ts_col}' not found")
        return False

    ts_series = df[ts_col]

    # Check for NaN values
    if ts_series.isna().any():
        logger.warning(f"NaN values found in timestamp column '{ts_col}'")
        return False

    # Check for monotonicity
    if not ts_series.is_monotonic_increasing:
        logger.warning(f"Timestamps in '{ts_col}' are not monotonic increasing")
        return False

    # Check for reasonable range (UTC seconds should be > 0 and < year 2100)
    min_ts = ts_series.min()
    max_ts = ts_series.max()

    if min_ts <= 0:
        logger.warning(f"Timestamp values <= 0 found: min={min_ts}")
        return False

    # Year 2100 in UTC seconds
    year_2100_ts = 4102444800
    if max_ts > year_2100_ts:
        logger.warning(f"Timestamp values > year 2100 found: max={max_ts}")
        return False

    return True


def strict_timestamp_validation(df: pd.DataFrame, ts_col: str = "ts") -> dict[str, Any]:
    """
    Strict timestamp validation according to plan requirements.

    Validates:
    - Timestamps are in UTC milliseconds
    - Strict monotonicity per symbol/timeframe
    - Zero duplicate timestamps
    - Reasonable timestamp range

    Args:
        df: DataFrame to validate
        ts_col: Name of the timestamp column

    Returns:
        Dictionary with validation results
    """
    result: dict[str, Any] = {"valid": True, "errors": [], "warnings": [], "stats": {}}

    if ts_col not in df.columns:
        result["valid"] = False
        result["errors"].append(f"Timestamp column '{ts_col}' not found")
        return result

    ts_series = df[ts_col]

    # Basic checks
    if ts_series.isna().any():
        result["valid"] = False
        result["errors"].append("NaN values found in timestamp column")

    if not ts_series.is_monotonic_increasing:
        result["warnings"].append("Timestamps are not strictly monotonic")

    # Check for duplicates
    duplicate_count = ts_series.duplicated().sum()
    if duplicate_count > 0:
        result["valid"] = False
        result["errors"].append(f"Found {duplicate_count} duplicate timestamps")

    # Check timestamp range (UTC seconds)
    min_ts = ts_series.min()
    max_ts = ts_series.max()

    if min_ts <= 0:
        result["valid"] = False
        result["errors"].append(f"Non-positive timestamps found: min={min_ts}")

    # Year 2100 check
    year_2100_ts = 4102444800
    if max_ts > year_2100_ts:
        result["warnings"].append(f"Timestamps beyond year 2100: max={max_ts}")

    # Statistics
    result["stats"] = {
        "count": len(ts_series),
        "min_timestamp": min_ts,
        "max_timestamp": max_ts,
        "duplicate_count": duplicate_count,
        "is_monotonic": ts_series.is_monotonic_increasing,
        "nan_count": ts_series.isna().sum(),
    }

    return result


def get_timestamp_info(df: pd.DataFrame, ts_col: str = "ts") -> dict[str, Any]:
    """
    Get information about timestamp column.

    Args:
        df: DataFrame to analyze
        ts_col: Name of the timestamp column

    Returns:
        Dictionary with timestamp statistics
    """
    if ts_col not in df.columns:
        return {"error": f"Column '{ts_col}' not found"}

    ts_series = df[ts_col]

    info = {
        "count": len(ts_series),
        "non_null_count": ts_series.notna().sum(),
        "null_count": ts_series.isna().sum(),
        "min": ts_series.min() if not ts_series.empty else None,
        "max": ts_series.max() if not ts_series.empty else None,
        "is_monotonic": ts_series.is_monotonic_increasing,
        "dtype": str(ts_series.dtype),
    }

    # Convert to human readable dates if possible
    if info["min"] is not None and info["max"] is not None:
        try:
            # Convert from milliseconds to datetime
            info["min_date"] = pd.to_datetime(info["min"], unit="ms").strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            info["max_date"] = pd.to_datetime(info["max"], unit="ms").strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except Exception:
            info["min_date"] = "invalid"
            info["max_date"] = "invalid"

    return info
