"""Pytest-benchmark tests for the features calculation pipeline.

Run with:
    pytest tests/features/benchmarks/bench_pipeline.py -q --benchmark-json=benchmarks/results/pytest_benchmark.json --no-cov
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

BENCH_ROWS = int(os.environ.get("FEATURES_BENCH_ROWS", "500"))


def _make_ohlcv(rows: int, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 + rng.normal(0, 0.5, rows).cumsum()
    open_ = close + rng.normal(0, 0.2, rows)
    high = np.maximum(open_, close) + abs(rng.normal(0, 0.3, rows))
    low = np.minimum(open_, close) - abs(rng.normal(0, 0.3, rows))
    volume = rng.integers(1000, 5000, rows).astype(float)
    return pd.DataFrame(
        {
            "ts": (np.arange(rows) + 1_700_000_000),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


@pytest.fixture(scope="module")
def ohlcv_df():
    return _make_ohlcv(BENCH_ROWS)


def test_bench_compute_features_single_group(benchmark, ohlcv_df):
    """Benchmark a single indicator group (overlap) as baseline."""
    from src.features.core.group_calculator import GroupFeatureCalculator

    calculator = GroupFeatureCalculator()
    df = ohlcv_df.copy()

    result = benchmark(calculator.calculate_group, df, "overlap", available={"hl2"})
    assert result is not None


def test_bench_compute_features_ma_group(benchmark, ohlcv_df):
    """Benchmark the MA group (heaviest single group by column count)."""
    from src.features.core.group_calculator import GroupFeatureCalculator

    calculator = GroupFeatureCalculator()
    df = ohlcv_df.copy()

    result = benchmark(
        calculator.calculate_group, df, "ma", available={"ema_21", "sma_20"}
    )
    assert result is not None


def test_bench_compute_features_rsi(benchmark, ohlcv_df):
    """Benchmark oscillators group."""
    from src.features.core.group_calculator import GroupFeatureCalculator

    calculator = GroupFeatureCalculator()
    df = ohlcv_df.copy()

    result = benchmark(
        calculator.calculate_group, df, "oscillators", available={"rsi_14"}
    )
    assert result is not None
