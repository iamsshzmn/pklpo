"""
Shared pytest fixtures for features module tests.
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def ohlcv_basic():
    """Basic OHLCV DataFrame with 3 rows."""
    return pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [99.0, 100.0, 101.0],
            "close": [104.0, 105.0, 106.0],
            "volume": [1000.0, 1100.0, 1200.0],
        }
    )


@pytest.fixture
def ohlcv_with_ts():
    """OHLCV DataFrame with timestamp column."""
    base_ts = int(datetime(2026, 1, 1).timestamp() * 1000)
    return pd.DataFrame(
        {
            "ts": [base_ts, base_ts + 60000, base_ts + 120000],
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [99.0, 100.0, 101.0],
            "close": [104.0, 105.0, 106.0],
            "volume": [1000.0, 1100.0, 1200.0],
        }
    )


@pytest.fixture
def ohlcv_50_bars():
    """50 bars of OHLCV data for indicator calculation."""
    np.random.seed(42)
    n = 50
    base_price = 100.0
    close = base_price + np.cumsum(np.random.randn(n) * 0.5)
    base_ts = int(datetime(2026, 1, 1).timestamp() * 1000)

    # Generate valid OHLC: high >= max(open, close), low <= min(open, close)
    open_prices = close + np.random.randn(n) * 0.3
    high = np.maximum(open_prices, close) + np.abs(np.random.randn(n)) * 0.5
    low = np.minimum(open_prices, close) - np.abs(np.random.randn(n)) * 0.5

    return pd.DataFrame(
        {
            "ts": [base_ts + i * 60000 for i in range(n)],
            "open": open_prices,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.random.randint(1000, 10000, n).astype(float),
        }
    )


@pytest.fixture
def ohlcv_100_bars():
    """100 bars of OHLCV data for indicator calculation."""
    np.random.seed(42)
    n = 100
    base_price = 100.0
    close = base_price + np.cumsum(np.random.randn(n) * 0.5)
    base_ts = int(datetime(2026, 1, 1).timestamp() * 1000)

    # Generate valid OHLC: high >= max(open, close), low <= min(open, close)
    open_prices = close + np.random.randn(n) * 0.3
    high = np.maximum(open_prices, close) + np.abs(np.random.randn(n)) * 0.5
    low = np.minimum(open_prices, close) - np.abs(np.random.randn(n)) * 0.5

    return pd.DataFrame(
        {
            "ts": [base_ts + i * 60000 for i in range(n)],
            "open": open_prices,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.random.randint(1000, 10000, n).astype(float),
        }
    )


@pytest.fixture
def ohlcv_with_nans():
    """OHLCV DataFrame with some NaN values."""
    return pd.DataFrame(
        {
            "ts": [1000, 2000, 3000, 4000, 5000],
            "open": [100.0, np.nan, 102.0, 103.0, 104.0],
            "high": [105.0, 106.0, np.nan, 108.0, 109.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [104.0, 105.0, 106.0, np.nan, 108.0],
            "volume": [1000.0, 1100.0, 1200.0, 1300.0, 1400.0],
        }
    )


@pytest.fixture
def empty_df():
    """Empty DataFrame."""
    return pd.DataFrame()


@pytest.fixture
def ohlcv_missing_columns():
    """OHLCV DataFrame missing some required columns."""
    return pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [99.0, 100.0, 101.0],
            # Missing 'close' and 'volume'
        }
    )


# Reset container before each test to ensure isolation
@pytest.fixture(autouse=True)
def reset_di_container():
    """Reset DI container before each test."""
    try:
        from src.features.container import reset_container

        reset_container()
    except ImportError:
        pass
    yield
    try:
        from src.features.container import reset_container

        reset_container()
    except ImportError:
        pass
