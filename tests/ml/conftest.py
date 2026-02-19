"""
Общие фикстуры для тестов ml-модуля.

Все фикстуры работают без подключения к БД.
"""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from src.core.run_context import RunContext


@pytest.fixture
def run_ctx() -> RunContext:
    """Детерминированный RunContext для тестов (фиксированный run_id)."""
    return RunContext(
        run_id="00000000-0000-0000-0000-000000000001",
        algo_version="test",
        params_hash="a" * 64,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def synthetic_ohlcv() -> pd.DataFrame:
    """
    Синтетический OHLCV DataFrame для тестов (без БД).

    Генерирует 1000 строк 1-минутных баров с реалистичными
    крипто-ценами (случайное блуждание вокруг 50 000 USD).

    Returns:
        DataFrame с колонками open, high, low, close, volume.
        Индекс — pd.DatetimeIndex с timezone UTC.
    """
    rng = np.random.default_rng(seed=42)
    n = 1000
    timestamps = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")

    returns = rng.normal(0.0001, 0.002, n)
    close = 50_000.0 * np.exp(np.cumsum(returns))
    high = close * (1 + rng.uniform(0.0005, 0.005, n))
    low = close * (1 - rng.uniform(0.0005, 0.005, n))
    open_ = close * (1 + rng.normal(0, 0.001, n))
    volume = rng.uniform(0.1, 10.0, n)

    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=timestamps,
    )


@pytest.fixture
def synthetic_ohlcv_large() -> pd.DataFrame:
    """
    Большой синтетический OHLCV DataFrame (10 000 строк) для
    тестов производительности triple-barrier и CPCV.
    """
    rng = np.random.default_rng(seed=123)
    n = 10_000
    timestamps = pd.date_range("2025-01-01", periods=n, freq="1min", tz="UTC")

    returns = rng.normal(0.00005, 0.001, n)
    close = 50_000.0 * np.exp(np.cumsum(returns))
    high = close * (1 + rng.uniform(0.0002, 0.003, n))
    low = close * (1 - rng.uniform(0.0002, 0.003, n))
    open_ = close * (1 + rng.normal(0, 0.0005, n))
    volume = rng.uniform(0.5, 20.0, n)

    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=timestamps,
    )
