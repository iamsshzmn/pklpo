"""
Quick test script for memory optimization features.

This script provides a simple way to test the memory optimization
features without running the full test suite.
"""

import gc
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

# Import from local modules
from src.features.application.calc import compute_and_dump_parquet, process_chunks
from src.features.config.settings import create_feature_config, create_streaming_config
from src.features.core import compute_features
from src.features.utils.memlog import force_cleanup, memory_monitor


def create_test_data(n_rows: int = 3000) -> pd.DataFrame:
    """Create test OHLCV data."""
    print(f"Creating {n_rows} rows of test data...")

    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=n_rows, freq="1h")
    base_price = 100.0
    returns = np.random.normal(0, 0.02, n_rows)
    prices = base_price * np.exp(np.cumsum(returns))

    df = pd.DataFrame(
        {
            "ts": dates.astype("int64") // 10**9,
            "open": prices * (1 + np.random.normal(0, 0.001, n_rows)),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.01, n_rows))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.01, n_rows))),
            "close": prices,
            "volume": np.random.uniform(1000, 10000, n_rows),
        }
    )

    # Ensure high >= max(open, close) and low <= min(open, close)
    df["high"] = np.maximum(df["high"], np.maximum(df["open"], df["close"]))
    df["low"] = np.minimum(df["low"], np.minimum(df["open"], df["close"]))

    return df


def chunk_dataframe(df: pd.DataFrame, chunk_size: int):
    """Split DataFrame into chunks."""
    chunks = []
    for i in range(0, len(df), chunk_size):
        chunk = df.iloc[i : i + chunk_size].copy()
        chunks.append(chunk)
    return chunks


def test_memory_usage():
    """Test memory usage with streaming vs non-streaming."""
    print("\n🧪 Testing memory usage...")

    # Create test data
    n_rows = 5000
    chunk_size = 1000
    df_full = create_test_data(n_rows)

    available_indicators = {"hlc3", "ema_8", "sma_20", "rsi_14", "atr_14"}
    feature_config = create_feature_config()

    # Test 1: Non-streaming approach
    print("  Testing non-streaming approach...")
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    with memory_monitor("non_streaming") as mem_log:
        baseline_df = compute_features(
            df_full,
            available=available_indicators,
            volatility_normalize=feature_config.ENABLE_VOLATILITY_NORMALIZE,
        )
        mem_log.log_dataframe_memory(baseline_df, "Baseline DataFrame")

    non_streaming_memory = process.memory_info().rss / 1024 / 1024  # MB
    non_streaming_increase = non_streaming_memory - initial_memory

    print(f"    Non-streaming memory increase: {non_streaming_increase:.2f} MB")
    print(f"    Baseline DataFrame shape: {baseline_df.shape}")

    # Clean up
    force_cleanup(baseline_df, df_full)
    gc.collect()

    # Test 2: Streaming approach
    print("  Testing streaming approach...")
    chunks = chunk_dataframe(df_full, chunk_size)

    def chunk_iterator():
        yield from chunks

    streaming_config = create_streaming_config()
    streaming_config.CHUNKSIZE = chunk_size
    streaming_config.MAX_LOOKBACK = 50
    streaming_config.OVERLAP_SIZE = 50
    streaming_config.FORCE_GC_AFTER_CHUNK = True
    streaming_config.CLEAR_INTERMEDIATE_OBJECTS = True
    streaming_config.LOG_MEMORY_USAGE = True

    streaming_memory_start = process.memory_info().rss / 1024 / 1024  # MB
    max_streaming_memory = streaming_memory_start

    with memory_monitor("streaming") as mem_log:
        streaming_results = []
        for i, result_chunk in enumerate(
            process_chunks(
                chunk_iterator(),
                symbol="TEST",
                timeframe="1H",
                available_indicators=available_indicators,
                config=streaming_config,
            )
        ):
            streaming_results.append(result_chunk)

            # Track peak memory
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            max_streaming_memory = max(max_streaming_memory, current_memory)

            print(
                f"    Chunk {i+1}: {current_memory:.2f} MB, shape: {result_chunk.shape}"
            )

            # Clean up after each chunk
            force_cleanup(result_chunk)
            gc.collect()

    streaming_memory_end = process.memory_info().rss / 1024 / 1024  # MB
    streaming_increase = streaming_memory_end - streaming_memory_start
    streaming_peak_increase = max_streaming_memory - streaming_memory_start

    print(f"    Streaming memory increase: {streaming_increase:.2f} MB")
    print(f"    Streaming peak increase: {streaming_peak_increase:.2f} MB")

    # Compare results
    memory_improvement = non_streaming_increase - streaming_increase
    peak_improvement = non_streaming_increase - streaming_peak_increase

    print(f"    Memory improvement: {memory_improvement:.2f} MB")
    print(f"    Peak memory improvement: {peak_improvement:.2f} MB")

    # Check if streaming is better
    if streaming_increase < non_streaming_increase:
        print("    ✅ Streaming uses less memory!")
    else:
        print("    ⚠️  Streaming uses more memory (unexpected)")

    if streaming_peak_increase < non_streaming_increase:
        print("    ✅ Streaming has lower peak memory!")
    else:
        print("    ⚠️  Streaming has higher peak memory (unexpected)")


def test_performance():
    """Test performance with streaming vs non-streaming."""
    print("\n🧪 Testing performance...")

    # Create test data
    n_rows = 3000
    chunk_size = 1000
    df_full = create_test_data(n_rows)

    available_indicators = {"hlc3", "ema_8", "sma_20", "rsi_14", "atr_14"}
    feature_config = create_feature_config()

    # Test 1: Non-streaming timing
    print("  Testing non-streaming timing...")
    start_time = time.time()

    baseline_df = compute_features(
        df_full,
        available=available_indicators,
        volatility_normalize=feature_config.ENABLE_VOLATILITY_NORMALIZE,
    )

    non_streaming_time = time.time() - start_time
    print(f"    Non-streaming time: {non_streaming_time:.2f} seconds")
    print(f"    Rows per second: {n_rows / non_streaming_time:.0f}")

    # Clean up
    force_cleanup(baseline_df, df_full)
    gc.collect()

    # Test 2: Streaming timing
    print("  Testing streaming timing...")
    chunks = chunk_dataframe(df_full, chunk_size)

    def chunk_iterator():
        yield from chunks

    streaming_config = create_streaming_config()
    streaming_config.CHUNKSIZE = chunk_size
    streaming_config.MAX_LOOKBACK = 50
    streaming_config.OVERLAP_SIZE = 50

    start_time = time.time()

    streaming_results = []
    for result_chunk in process_chunks(
        chunk_iterator(),
        symbol="TEST",
        timeframe="1H",
        available_indicators=available_indicators,
        config=streaming_config,
    ):
        streaming_results.append(result_chunk)

    streaming_time = time.time() - start_time
    print(f"    Streaming time: {streaming_time:.2f} seconds")
    print(f"    Rows per second: {n_rows / streaming_time:.0f}")

    # Performance comparison
    speedup = non_streaming_time / streaming_time
    print(f"    Speedup: {speedup:.2f}x")

    if speedup > 1:
        print("    ✅ Streaming is faster!")
    elif speedup > 0.8:
        print("    ✅ Streaming performance is acceptable")
    else:
        print("    ⚠️  Streaming is slower (expected due to overhead)")


def test_parquet_operations():
    """Test parquet file operations."""
    import pytest

    try:
        import pyarrow  # noqa: F401
    except ImportError:
        pytest.skip("pyarrow is not installed, skipping parquet tests")

    print("\n🧪 Testing parquet operations...")

    # Create test data
    df = create_test_data(1000)
    feature_config = create_feature_config()

    # Test parquet save
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp_file:
        parquet_path = tmp_file.name

    try:
        # Test compute and dump
        result = compute_and_dump_parquet(
            df_ohlcv=df,
            symbol="TEST",
            timeframe="1H",
            output_path=parquet_path,
            volatility_normalize=feature_config.ENABLE_VOLATILITY_NORMALIZE,
        )

        print(f"    Parquet file created: {result['output_path']}")
        print(f"    File size: {result['file_size_mb']:.2f} MB")
        print(f"    Rows: {result['result_rows']}")
        print(f"    Features: {result['feature_count']}")

        # Verify file exists and has content
        assert Path(parquet_path).exists(), "Parquet file not created"
        assert Path(parquet_path).stat().st_size > 0, "Parquet file is empty"
        print("    ✅ Parquet file created successfully!")

        # Test parquet validation
        from src.features.application.calc import validate_parquet_file

        validation = validate_parquet_file(parquet_path)

        print(
            f"    Validation: {validation['rows']} rows, {validation['feature_count']} features"
        )

        assert validation["rows"] > 0, "No rows in parquet file"
        assert validation["feature_count"] > 0, "No features in parquet file"
        print("    ✅ Parquet file validation passed!")

    finally:
        # Clean up
        if Path(parquet_path).exists():
            Path(parquet_path).unlink()


def test_configuration():
    """Test configuration management."""
    print("\n🧪 Testing configuration...")

    # Test streaming config
    streaming_config = create_streaming_config()
    print(
        f"    Streaming config: CHUNKSIZE={streaming_config.CHUNKSIZE}, MAX_LOOKBACK={streaming_config.MAX_LOOKBACK}"
    )

    # Test strategy lookbacks
    from src.features.domain.strategy import (
        get_max_lookback_for_strategies,
        max_lookback,
    )

    test_strategies = ["sma_20", "ema_8", "rsi_14", "atr_14", "macd"]
    max_lookback_result = get_max_lookback_for_strategies(test_strategies)
    print(
        f"    Max lookback for {len(test_strategies)} strategies: {max_lookback_result}"
    )

    # Test individual strategies
    for strategy in test_strategies:
        lookback = max_lookback(strategy)
        print(f"    {strategy}: {lookback} periods")

    print("    ✅ Configuration test passed!")


def run_quick_test():
    """Run quick test of memory optimization features."""
    print("🚀 Starting quick memory optimization test...")
    print("=" * 50)

    try:
        # Test 1: Memory usage
        test_memory_usage()

        # Test 2: Performance
        test_performance()

        # Test 3: Parquet operations
        test_parquet_operations()

        # Test 4: Configuration
        test_configuration()

        print("\n" + "=" * 50)
        print("🎉 All quick tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_quick_test()
    sys.exit(0 if success else 1)
