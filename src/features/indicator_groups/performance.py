import numpy as np
import pandas as pd


def _nan_series(df: pd.DataFrame) -> pd.Series:
    return pd.Series([np.nan] * len(df), index=df.index)


def calc_performance_indicators(
    df: pd.DataFrame, available: set[str], window: int = 20, **kwargs
) -> dict[str, pd.Series]:
    """
    Calculate performance indicators.

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

    # Only process performance indicators, not other types
    performance_indicators = {
        "log_return",
        "percent_return",
        "trend_return_20",
        "drawdown",
        "returns_20",
        "volatility_20",
        "sharpe_20",
        "max_drawdown_20",
    }

    # Filter available to only include performance indicators
    available = available.intersection(performance_indicators)

    if "log_return" in available:
        result["log_return"] = np.log(close).diff()

    if "percent_return" in available:
        result["percent_return"] = close.pct_change()

    if "trend_return_20" in available:
        # Rolling cumulative percent return over window
        pct = close.pct_change().fillna(0.0)
        # cumulative product of (1+pct) over window minus 1
        cum = (1.0 + pct).rolling(window).apply(lambda x: np.prod(x) - 1.0, raw=True)
        result["trend_return_20"] = cum

    if "drawdown" in available:
        running_max = close.cummax()
        result["drawdown"] = (close - running_max) / running_max.replace(0.0, np.nan)

    for key in list(available):
        if key not in result:
            result[key] = _nan_series(df)

    return result
