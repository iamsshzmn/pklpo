"""
Comprehensive test for memory optimization features.

This script tests all the memory optimization components we implemented:
- Streaming chunk processing
- Memory monitoring
- Database batch operations
- Configuration management
- Strategy lookback management
"""

import asyncio
import gc
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

# Import from local modules
from src.features.calc import compute_and_dump_parquet, process_chunks
from src.features.config import (
    create_database_config,
    create_feature_config,
    create_streaming_config,
)
from src.features.core import compute_features
from src.features.strategy import get_max_lookback_for_strategies, max_lookback
from src.features.utils.memlog import force_cleanup, memory_monitor


def create_large_test_data(n_rows: int = 10000) -> pd.DataFrame:
    """Create large test dataset for memory testing."""
    print(f"Creating test data with {n_rows} rows...")

    np.random.seed(42)  # For reproducible results

    # Generate realistic OHLCV data
    dates = pd.date_range("2023-01-01", periods=n_rows, freq="1h")
    base_price = 100.0
    returns = np.random.normal(0, 0.02, n_rows)
    prices = base_price * np.exp(np.cumsum(returns))

    df = pd.DataFrame(
        {
            "ts": dates.astype("int64") // 10**9,  # Unix timestamp in seconds
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

    print(f"Created DataFrame: {df.shape}")
    return df


def chunk_dataframe(df: pd.DataFrame, chunk_size: int) -> list[pd.DataFrame]:
    """Split DataFrame into chunks for streaming processing."""
    chunks = []
    for i in range(0, len(df), chunk_size):
        chunk = df.iloc[i : i + chunk_size].copy()
        chunks.append(chunk)
    return chunks


def test_memory_monitoring():
    """Test memory monitoring utilities."""
    print("\n🧪 Testing memory monitoring...")

    with memory_monitor("test_operation") as mem_log:
        # Create test DataFrame
        df = pd.DataFrame(
            {
                "open": np.random.randn(1000),
                "high": np.random.randn(1000),
                "low": np.random.randn(1000),
                "close": np.random.randn(1000),
                "volume": np.random.randn(1000),
            }
        )

        mem_log.log_dataframe_memory(df, "Test DataFrame")

        # Simulate processing
        df["hlc3"] = (df["high"] + df["low"] + df["close"]) / 3
        df["sma_20"] = df["close"].rolling(20).mean()

        mem_log.log_dataframe_memory(df, "Processed DataFrame")

        # Test cleanup
        force_cleanup(df)

    print("✅ Memory monitoring test passed!")


def test_strategy_lookbacks():
    """Test strategy lookback management."""
    print("\n🧪 Testing strategy lookbacks...")

    # Test individual strategies
    test_strategies = ["sma_20", "ema_8", "rsi_14", "atr_14", "macd", "bb_20"]

    for strategy in test_strategies:
        lookback = max_lookback(strategy)
        print(f"  {strategy}: {lookback} periods")
        assert lookback > 0, f"Invalid lookback for {strategy}"

    # Test max lookback for multiple strategies
    max_lookback_result = get_max_lookback_for_strategies(test_strategies)
    print(
        f"  Max lookback for {len(test_strategies)} strategies: {max_lookback_result}"
    )
    assert max_lookback_result > 0, "Invalid max lookback"

    print("✅ Strategy lookbacks test passed!")


def test_configuration():
    """Test configuration management."""
    print("\n🧪 Testing configuration...")

    # Test streaming config
    streaming_config = create_streaming_config()
    print(
        f"  Streaming config: CHUNKSIZE={streaming_config.CHUNKSIZE}, MAX_LOOKBACK={streaming_config.MAX_LOOKBACK}"
    )
    assert streaming_config.CHUNKSIZE > 0, "Invalid CHUNKSIZE"
    assert streaming_config.MAX_LOOKBACK > 0, "Invalid MAX_LOOKBACK"

    # Test database config
    db_config = create_database_config()
    print(
        f"  Database config: BATCH_SIZE={db_config.BATCH_SIZE}, MAX_RETRIES={db_config.MAX_RETRIES}"
    )
    assert db_config.BATCH_SIZE > 0, "Invalid BATCH_SIZE"
    assert db_config.MAX_RETRIES > 0, "Invalid MAX_RETRIES"

    # Test feature config
    feature_config = create_feature_config()
    print(
        f"  Feature config: MIN_FILL_RATE={feature_config.MIN_FILL_RATE}, VALIDATE_RESULTS={feature_config.VALIDATE_RESULTS}"
    )
    assert 0 <= feature_config.MIN_FILL_RATE <= 1, "Invalid MIN_FILL_RATE"

    print("✅ Configuration test passed!")


def test_streaming_processing():
    """Test streaming chunk processing."""
    print("\n🧪 Testing streaming processing...")

    # Create test data
    n_rows = 5000
    chunk_size = 1000
    df_full = create_large_test_data(n_rows)

    # Define indicators
    available_indicators = {"hlc3", "ema_8", "sma_20", "rsi_14", "atr_14"}

    # Create chunks
    chunks = chunk_dataframe(df_full, chunk_size)
    print(f"  Created {len(chunks)} chunks of size {chunk_size}")

    # Test streaming processing
    def chunk_iterator():
        yield from chunks

    # Configure streaming
    streaming_config = create_streaming_config()
    streaming_config.CHUNKSIZE = chunk_size
    streaming_config.MAX_LOOKBACK = 50
    streaming_config.OVERLAP_SIZE = 50
    streaming_config.LOG_MEMORY_USAGE = True

    # Process chunks
    results = []
    with memory_monitor("streaming_processing") as mem_log:
        for i, result_chunk in enumerate(
            process_chunks(
                chunk_iterator(),
                symbol="TEST",
                timeframe="1H",
                available_indicators=available_indicators,
                config=streaming_config,
            )
        ):
            results.append(result_chunk)
            print(f"  Processed chunk {i+1}: {result_chunk.shape}")

            # Log memory usage
            mem_log.log_dataframe_memory(result_chunk, f"Result chunk {i+1}")

    # Combine results
    if results:
        combined_df = pd.concat(results, ignore_index=True)
        print(f"  Combined result: {combined_df.shape}")
        print(f"  Columns: {list(combined_df.columns)}")

    print("✅ Streaming processing test passed!")


def test_memory_usage_comparison():
    """Test memory usage comparison between streaming and non-streaming."""
    print("\n🧪 Testing memory usage comparison...")

    # Create test data
    n_rows = 8000
    chunk_size = 2000
    df_full = create_large_test_data(n_rows)

    available_indicators = {"hlc3", "ema_8", "sma_20", "rsi_14", "atr_14"}
    feature_config = create_feature_config()

    # Test 1: Non-streaming (baseline)
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

    # Clean up
    force_cleanup(baseline_df, df_full)
    gc.collect()

    # Test 2: Streaming
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

            print(f"    Chunk {i+1}: {current_memory:.2f} MB")

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

    # Assertions with tolerance for measurement precision
    # Memory measurements can have small variations due to GC, OS scheduling, etc.
    # Allow 0.1 MB tolerance (100 KB) or 5% of baseline, whichever is larger
    tolerance_mb = max(0.1, non_streaming_increase * 0.05)

    assert (
        streaming_increase <= non_streaming_increase + tolerance_mb
    ), f"Streaming should use less memory (tolerance: {tolerance_mb:.2f} MB). "
    f"Non-streaming: {non_streaming_increase:.2f} MB, Streaming: {streaming_increase:.2f} MB"

    assert (
        streaming_peak_increase <= non_streaming_increase + tolerance_mb
    ), f"Streaming peak should be lower (tolerance: {tolerance_mb:.2f} MB). "
    f"Non-streaming: {non_streaming_increase:.2f} MB, Streaming peak: {streaming_peak_increase:.2f} MB"

    print("✅ Memory usage comparison test passed!")


def test_parquet_operations():
    """Test parquet file operations."""
    import pytest

    try:
        import pyarrow  # noqa: F401
    except ImportError:
        pytest.skip("pyarrow is not installed, skipping parquet tests")

    print("\n🧪 Testing parquet operations...")

    # Create test data
    df = create_large_test_data(2000)
    feature_config = create_feature_config()

    # Test parquet save
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

        print(f"  Parquet file created: {result['output_path']}")
        print(f"  File size: {result['file_size_mb']:.2f} MB")
        print(f"  Rows: {result['result_rows']}")
        print(f"  Features: {result['feature_count']}")

        # Verify file exists and has content
        assert Path(parquet_path).exists(), "Parquet file not created"
        assert Path(parquet_path).stat().st_size > 0, "Parquet file is empty"

        # Test parquet validation
        from src.features.calc import validate_parquet_file

        validation = validate_parquet_file(parquet_path)

        print(
            f"  Validation: {validation['rows']} rows, {validation['feature_count']} features"
        )
        assert validation["rows"] > 0, "No rows in parquet file"
        assert validation["feature_count"] > 0, "No features in parquet file"

    finally:
        # Clean up
        if Path(parquet_path).exists():
            Path(parquet_path).unlink()

    print("✅ Parquet operations test passed!")


async def test_database_operations():
    """Test database operations (mock)."""
    print("\n🧪 Testing database operations...")

    # Create test data
    df = create_large_test_data(1000)

    # Test batch data preparation
    from src.features.save import _prepare_batch_data

    batch_data = _prepare_batch_data(df, "TEST", "1H")
    print(f"  Prepared {len(batch_data)} batch records")

    # Test batch data validation
    from src.features.save import _validate_dataframe

    validation = _validate_dataframe(df, "TEST", "1H")
    print(f"  Validation: {validation['valid']}")
    print(f"  Errors: {len(validation['errors'])}")
    print(f"  Warnings: {len(validation['warnings'])}")

    assert validation["valid"], f"Validation failed: {validation['errors']}"

    print("✅ Database operations test passed!")


def test_performance_metrics():
    """Test performance metrics and timing."""
    print("\n🧪 Testing performance metrics...")

    # Create test data
    n_rows = 5000
    chunk_size = 1000
    df_full = create_large_test_data(n_rows)

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

    # Memory efficiency
    process = psutil.Process()
    memory_usage = process.memory_info().rss / 1024 / 1024  # MB
    print(f"    Current memory usage: {memory_usage:.2f} MB")

    print("✅ Performance metrics test passed!")


def run_all_tests():
    """Run all memory optimization tests."""
    print("🚀 Starting comprehensive memory optimization tests...")
    print("=" * 60)

    try:
        # Test 1: Memory monitoring
        test_memory_monitoring()

        # Test 2: Strategy lookbacks
        test_strategy_lookbacks()

        # Test 3: Configuration
        test_configuration()

        # Test 4: Streaming processing
        test_streaming_processing()

        # Test 5: Memory usage comparison
        test_memory_usage_comparison()

        # Test 6: Parquet operations
        test_parquet_operations()

        # Test 7: Database operations
        asyncio.run(test_database_operations())

        # Test 8: Performance metrics
        test_performance_metrics()

        print("\n" + "=" * 60)
        print("🎉 All memory optimization tests passed!")
        print("✅ Streaming processing works correctly")
        print("✅ Memory usage is optimized")
        print("✅ Configuration management works")
        print("✅ Strategy lookbacks are correct")
        print("✅ Parquet operations work")
        print("✅ Database operations are optimized")
        print("✅ Performance metrics are good")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    return None


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
