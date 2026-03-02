"""
Utility functions for the features module.

This module provides utility functions for feature calculation, including
volatility normalization, data preprocessing, and helper functions.
"""

import numpy as np
import pandas as pd

from src.logging import get_logger

logger = get_logger(__name__)


def assert_frames_close(
    left: pd.DataFrame,
    right: pd.DataFrame,
    columns: list[str] | None = None,
    rtol: float = 1e-9,
    atol: float = 1e-12,
) -> None:
    """
    Assert that two DataFrames are numerically close within tolerances.

    Args:
        left: First DataFrame
        right: Second DataFrame (aligned by index)
        columns: Specific columns to compare (numeric expected). If None, infer numeric intersection
        rtol: Relative tolerance
        atol: Absolute tolerance
    """
    if columns is None:
        left_num = set(left.select_dtypes(include=[np.number]).columns)
        right_num = set(right.select_dtypes(include=[np.number]).columns)
        columns = sorted(left_num & right_num)

    # Align by index
    common_index = left.index.intersection(right.index)
    left_al = left.loc[common_index]
    right_al = right.loc[common_index]

    for col in columns:
        if col not in left_al.columns or col not in right_al.columns:
            continue
        lvals = left_al[col].to_numpy()
        rvals = right_al[col].to_numpy()
        # NaNs equal
        equal = np.isclose(lvals, rvals, rtol=rtol, atol=atol, equal_nan=True)
        if not np.all(equal):
            # Build a compact error for first few mismatches
            mismatch_idx = np.where(~equal)[0][:5]
            samples = [
                (
                    int(i),
                    float(lvals[i]) if not np.isnan(lvals[i]) else np.nan,
                    float(rvals[i]) if not np.isnan(rvals[i]) else np.nan,
                )
                for i in mismatch_idx
            ]
            raise AssertionError(
                f"Column '{col}' differs beyond tolerances (rtol={rtol}, atol={atol})."
                f" Examples (pos, left, right): {samples}"
            )


def volatility_normalize_features(
    df_features: pd.DataFrame,
    window: int = 20,
    method: str = "rolling_std",
    feature_columns: list[str] | None = None,
    exclude_columns: list[str] | None = None,
) -> pd.DataFrame:
    """
    Normalize features by volatility to stabilize their scale.

    Args:
        df_features: DataFrame with features to normalize
        window: Window size for volatility calculation
        method: Method for volatility normalization ("rolling_std", "ewm_std")
        feature_columns: List of feature columns to normalize (if None, normalize all numeric)
        exclude_columns: List of columns to exclude from normalization

    Returns:
        DataFrame with normalized features
    """
    if df_features is None or df_features.empty:
        return df_features

    # Determine which columns to normalize
    exclude_cols = set(exclude_columns or []) | {
        "open",
        "high",
        "low",
        "close",
        "volume",
        "ts",
    }
    cols = feature_columns or [
        c
        for c in df_features.select_dtypes(include=[np.number]).columns
        if c not in exclude_cols
    ]

    if not cols:
        logger.warning("No feature columns to normalize")
        return df_features

    out = df_features.copy()
    try:
        for col in cols:
            out[col] = _normalize_series_by_volatility(
                out[col], window=window, method=method
            )
    except ValueError as exc:
        logger.warning("Volatility normalization skipped: %s", exc)
        return df_features

    logger.debug("Normalized %d features using %s", len(cols), method)
    return out


def _normalize_series_by_volatility(
    series: pd.Series, window: int = 20, method: str = "rolling_std"
) -> pd.Series:
    """Normalize a single Series by its volatility."""
    if series is None or series.empty:
        return series

    numeric_series = pd.to_numeric(series, errors="coerce")
    if numeric_series.isna().all():
        return series

    if method == "rolling_std":
        volatility = numeric_series.rolling(window=window, min_periods=1).std()
    elif method == "ewm_std":
        volatility = numeric_series.ewm(span=window, min_periods=1).std()
    else:
        raise ValueError(f"Unknown normalization method: {method}")

    volatility = volatility.replace(0, np.nan)
    if volatility.isna().all():
        return series

    normalized = numeric_series / volatility
    normalized = normalized.where(~volatility.isna(), numeric_series)
    normalized = normalized.fillna(numeric_series)
    return normalized.astype("float64")


def zscore_normalize_features(
    df_features: pd.DataFrame,
    feature_columns: list[str] | None = None,
    exclude_columns: list[str] | None = None,
) -> pd.DataFrame:
    """
    Normalize features using Z-score normalization.

    Args:
        df_features: DataFrame with features to normalize
        feature_columns: List of feature columns to normalize
        exclude_columns: List of columns to exclude from normalization

    Returns:
        DataFrame with Z-score normalized features
    """
    if df_features is None or df_features.empty:
        return df_features

    # Determine which columns to normalize
    exclude_cols = set(exclude_columns or []) | {
        "open",
        "high",
        "low",
        "close",
        "volume",
        "ts",
    }
    cols = feature_columns or [
        c
        for c in df_features.select_dtypes(include=[np.number]).columns
        if c not in exclude_cols
    ]

    if not cols:
        logger.warning("No feature columns to normalize")
        return df_features

    out = df_features.copy()
    X = df_features[cols]

    # Vectorized Z-score normalization
    mean_vals = X.mean()
    std_vals = X.std()

    # Only normalize columns with non-zero std
    valid_cols = std_vals > 0
    if valid_cols.any():
        norm = (X - mean_vals) / std_vals
        for col in cols:
            if valid_cols.get(col, False):
                out[col] = norm[col]
        logger.debug("Z-score normalized %d features", int(valid_cols.sum()))

    return out


# --- Small helpers used by indicator groups ---
def _first_col_or_series(
    obj: pd.Series | pd.DataFrame | None, name: str, index: pd.Index
) -> pd.Series:
    """Return a Series from a pandas-ta result that may be Series/DataFrame/None.

    - If Series: rename and reindex to match index.
    - If DataFrame: pick the first column, rename, reindex.
    - If None or empty: return NaN series with provided index and name.
    """
    if isinstance(obj, pd.Series):
        s = obj.copy()
    elif isinstance(obj, pd.DataFrame) and not obj.empty:
        s = obj.iloc[:, 0].copy()
    else:
        return _nan_series(index, name)

    s.name = name
    return s.reindex(index)


def _nan_series(index: pd.Index, name: str) -> pd.Series:
    """Create a float64 NaN-filled Series with the given index and name."""
    return pd.Series([np.nan] * len(index), index=index, name=name, dtype="float64")


# --- Lightweight fallbacks for core MAs (in case pandas_ta returns None/all-NaN) ---
def safe_sma(series: pd.Series, length: int) -> pd.Series:
    """
    Simple Moving Average fallback using pandas. Always returns a Series of same length.
    """
    try:
        s = pd.to_numeric(series, errors="coerce")
        result = s.rolling(window=length, min_periods=length).mean()
        return result.astype("float64").reindex(series.index)
    except Exception:
        return pd.Series([np.nan] * len(series), index=series.index, dtype="float64")


def safe_ema(series: pd.Series, length: int) -> pd.Series:
    """
    Exponential Moving Average fallback using pandas ewm. Always returns a Series of same length.
    """
    try:
        s = pd.to_numeric(series, errors="coerce")
        # Match common EMA definition (span=length, adjust=False)
        result = s.ewm(span=length, adjust=False, min_periods=length).mean()
        return result.astype("float64").reindex(series.index)
    except Exception:
        return pd.Series([np.nan] * len(series), index=series.index, dtype="float64")


def minmax_normalize_features(
    df_features: pd.DataFrame,
    feature_columns: list[str] | None = None,
    exclude_columns: list[str] | None = None,
    feature_range: tuple = (0, 1),
) -> pd.DataFrame:
    """
    Normalize features using min-max normalization.

    Args:
        df_features: DataFrame with features to normalize
        feature_columns: List of feature columns to normalize
        exclude_columns: List of columns to exclude from normalization
        feature_range: Range for normalization (min, max)

    Returns:
        DataFrame with min-max normalized features
    """
    if df_features is None or df_features.empty:
        return df_features

    # Determine which columns to normalize
    if feature_columns is None:
        exclude_cols = set(exclude_columns or [])
        exclude_cols.update(["open", "high", "low", "close", "volume", "ts"])

        numeric_columns = df_features.select_dtypes(include=[np.number]).columns
        feature_columns = [col for col in numeric_columns if col not in exclude_cols]
    else:
        feature_columns = [col for col in feature_columns if col in df_features.columns]

    if not feature_columns:
        logger.warning("No feature columns to normalize")
        return df_features

    result_df = df_features.copy()

    for col in feature_columns:
        series = df_features[col]

        # Skip if all values are NaN or constant
        if series.isna().all() or series.std() == 0:
            continue

        try:
            # Min-max normalization
            min_val = series.min()
            max_val = series.max()

            if max_val > min_val:
                normalized_series = (series - min_val) / (max_val - min_val)
                # Scale to feature_range
                normalized_series = (
                    normalized_series * (feature_range[1] - feature_range[0])
                    + feature_range[0]
                )
                result_df[col] = normalized_series
                logger.debug(f"Min-max normalized feature: {col}")
            else:
                logger.warning(f"Feature {col} has no range, skipping normalization")
        except Exception as e:
            logger.warning(f"Failed to min-max normalize feature {col}: {e!s}")

    return result_df


def fill_missing_values(
    df_features: pd.DataFrame,
    method: str = "forward",
    feature_columns: list[str] | None = None,
) -> pd.DataFrame:
    """
    Fill missing values in features using various methods.

    Args:
        df_features: DataFrame with features
        method: Method for filling missing values ("forward", "backward", "interpolate", "zero")
        feature_columns: List of feature columns to process

    Returns:
        DataFrame with filled missing values
    """
    if df_features is None or df_features.empty:
        return df_features

    if feature_columns is None:
        # Process all numeric columns except OHLCV
        exclude_cols = ["open", "high", "low", "close", "volume", "ts"]
        numeric_columns = df_features.select_dtypes(include=[np.number]).columns
        feature_columns = [col for col in numeric_columns if col not in exclude_cols]
    else:
        feature_columns = [col for col in feature_columns if col in df_features.columns]

    if not feature_columns:
        return df_features

    result_df = df_features.copy()

    for col in feature_columns:
        series = result_df[col]

        if series.isna().any():
            try:
                if method == "forward":
                    filled_series = series.fillna(method="ffill")
                elif method == "backward":
                    filled_series = series.fillna(method="bfill")
                elif method == "interpolate":
                    filled_series = series.interpolate(method="linear")
                elif method == "zero":
                    filled_series = series.fillna(0)
                else:
                    raise ValueError(f"Unknown fill method: {method}")

                result_df[col] = filled_series
                logger.debug(f"Filled missing values in {col} using {method} method")
            except Exception as e:
                logger.warning(f"Failed to fill missing values in {col}: {e!s}")

    return result_df


def detect_outliers(
    df_features: pd.DataFrame,
    method: str = "zscore",
    threshold: float = 3.0,
    feature_columns: list[str] | None = None,
) -> dict[str, list]:
    """
    Detect outliers in features using various methods.

    Args:
        df_features: DataFrame with features
        method: Method for outlier detection ("zscore", "iqr")
        threshold: Threshold for outlier detection
        feature_columns: List of feature columns to check

    Returns:
        Dictionary mapping feature names to lists of outlier index labels
    """
    if df_features is None or df_features.empty:
        return {}

    if feature_columns is None:
        exclude_cols = ["open", "high", "low", "close", "volume", "ts"]
        numeric_columns = df_features.select_dtypes(include=[np.number]).columns
        feature_columns = [col for col in numeric_columns if col not in exclude_cols]
    else:
        feature_columns = [col for col in feature_columns if col in df_features.columns]

    outliers = {}

    for col in feature_columns:
        series = df_features[col].dropna()

        if len(series) == 0:
            continue

        try:
            if method == "zscore":
                # Calculate z-score manually using numpy
                z_scores = np.abs((series - series.mean()) / series.std())
                mask = z_scores > threshold
            elif method == "iqr":
                Q1 = series.quantile(0.25)
                Q3 = series.quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - threshold * IQR
                upper_bound = Q3 + threshold * IQR
                mask = (series < lower_bound) | (series > upper_bound)
            else:
                raise ValueError(f"Unknown outlier detection method: {method}")

            if mask.any():
                outliers[col] = series.index[mask].tolist()
                logger.debug(f"Detected {mask.sum()} outliers in {col}")
        except Exception as e:
            logger.warning(f"Failed to detect outliers in {col}: {e!s}")

    return outliers


def calculate_feature_statistics(
    df_features: pd.DataFrame, feature_columns: list[str] | None = None
) -> pd.DataFrame:
    """
    Calculate basic statistics for features.

    Args:
        df_features: DataFrame with features
        feature_columns: List of feature columns to analyze

    Returns:
        DataFrame with feature statistics
    """
    if df_features is None or df_features.empty:
        return pd.DataFrame()

    if feature_columns is None:
        exclude_cols = ["open", "high", "low", "close", "volume", "ts"]
        numeric_columns = df_features.select_dtypes(include=[np.number]).columns
        feature_columns = [col for col in numeric_columns if col not in exclude_cols]
    else:
        feature_columns = [col for col in feature_columns if col in df_features.columns]

    if not feature_columns:
        return pd.DataFrame()

    # Calculate statistics for each feature
    stats_data = []

    for col in feature_columns:
        series = df_features[col].dropna()

        if len(series) == 0:
            continue

        stats_dict = {
            "feature": col,
            "count": len(series),
            "mean": series.mean(),
            "std": series.std(),
            "min": series.min(),
            "max": series.max(),
            "median": series.median(),
            "skewness": series.skew(),
            "kurtosis": series.kurtosis(),
            "missing_pct": (df_features[col].isna().sum() / len(df_features)) * 100,
        }
        stats_data.append(stats_dict)

    return pd.DataFrame(stats_data)


def ensure_no_lookahead(
    df_features: pd.DataFrame, feature_columns: list[str] | None = None
) -> bool:
    """
    Basic check to ensure no lookahead bias in feature calculation.

    Args:
        df_features: DataFrame with features
        feature_columns: List of feature columns to check

    Returns:
        True if no obvious lookahead bias detected
    """
    if df_features is None or df_features.empty:
        return True

    if feature_columns is None:
        exclude_cols = ["open", "high", "low", "close", "volume", "ts"]
        numeric_columns = df_features.select_dtypes(include=[np.number]).columns
        feature_columns = [col for col in numeric_columns if col not in exclude_cols]
    else:
        feature_columns = [col for col in feature_columns if col in df_features.columns]

    # Check for monotonic timestamps
    if "ts" in df_features.columns and len(df_features) > 1:
        if not df_features["ts"].is_monotonic_increasing:
            logger.warning(
                "Timestamps are not in ascending order - potential lookahead bias"
            )
            return False

    # Check for features that might have lookahead issues
    lookahead_risky_patterns = [
        "bbands_percent",  # Uses future data for normalization
        "natr_14",  # Normalized ATR might use future data
    ]

    risky_features = [
        f
        for f in feature_columns
        if any(pattern in f for pattern in lookahead_risky_patterns)
    ]
    if risky_features:
        logger.warning(f"Features with potential lookahead risk: {risky_features}")

    # Quick smoke test: check if last n values change when truncating the series
    # This helps detect future data leakage
    if len(df_features) > 10:
        for col in feature_columns[:3]:  # Check first 3 features only
            if col in df_features.columns:
                series = df_features[col].dropna()
                if len(series) > 5:
                    # Compare last 3 values with truncated series
                    last_3_orig = series.tail(3).values
                    last_3_trunc = series.iloc[:-1].tail(3).values
                    if np.array_equal(last_3_orig[:-1], last_3_trunc[:-1]):
                        logger.warning(
                            f"Potential lookahead bias detected in {col} - tail values unchanged after truncation"
                        )
                        return False

    return True
