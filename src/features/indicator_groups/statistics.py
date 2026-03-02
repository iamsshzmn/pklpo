import numpy as np
import pandas as pd


def _nan_series(df: pd.DataFrame) -> pd.Series:
    return pd.Series([np.nan] * len(df), index=df.index)


def calc_statistics_indicators(
    df: pd.DataFrame, available: set[str], window: int = 20, **kwargs
) -> dict[str, pd.Series]:
    """
    Calculate statistical indicators.

    Args:
        df: DataFrame with OHLC data
        available: Set of indicator names to calculate
        window: Rolling window size (default: 20)
        **kwargs: Additional parameters (unused, for Protocol compliance)

    Returns:
        Dictionary mapping indicator names to pandas Series
    """
    result: dict[str, pd.Series] = {}
    close = df["close"].astype(float)

    # Only process statistics indicators, not other types
    statistics_indicators = {
        "median_20",
        "mad_20",
        "stdev_20",
        "variance_20",
        "skew_20",
        "kurtosis_20",
        "zscore_20",
        "std_20",
        "var_20",
        "kurt_20",
    }

    # Filter available to only include statistics indicators
    available = available.intersection(statistics_indicators)

    if "median_20" in available:
        result["median_20"] = close.rolling(window).median()

    if "mad_20" in available:
        result["mad_20"] = (
            (close - close.rolling(window).median()).abs().rolling(window).median()
        )

    if "stdev_20" in available:
        result["stdev_20"] = close.rolling(window).std(ddof=0)

    if "variance_20" in available:
        result["variance_20"] = close.rolling(window).var(ddof=0)

    if "skew_20" in available:
        result["skew_20"] = close.rolling(window).skew()

    if "kurtosis_20" in available:
        result["kurtosis_20"] = close.rolling(window).kurt()

    if "zscore_20" in available:
        mean = close.rolling(window).mean()
        std = close.rolling(window).std(ddof=0)
        result["zscore_20"] = (close - mean) / std.replace(0.0, np.nan)

    # Дополнительные статистические индикаторы
    if "std_20" in available:
        result["std_20"] = close.rolling(window).std(ddof=0)

    if "var_20" in available:
        result["var_20"] = close.rolling(window).var(ddof=0)

    if "kurt_20" in available:
        result["kurt_20"] = close.rolling(window).kurt()

    for key in list(available):
        if key not in result:
            result[key] = _nan_series(df)

    return result
