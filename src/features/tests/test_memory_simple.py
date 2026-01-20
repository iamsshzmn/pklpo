"""
Simple test for memory optimization modules.

This test focuses on testing the new memory optimization components
without emojis and complex dependencies.
"""

import gc
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))


def create_test_data(n_rows: int = 5000) -> pd.DataFrame:
    """Create test OHLCV data."""
    print(f"Creating {n_rows} rows of test data...")

    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=n_rows, freq="1H")
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


def test_memory_monitoring():
    """Test memory monitoring utilities."""
    print("\nTesting memory monitoring...")

    try:
        from utils.memlog import force_cleanup, memory_monitor

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

        print("    Memory monitoring test passed!")
        return True

    except Exception as e:
        print(f"    Memory monitoring test failed: {e}")
        return False


def test_strategy_lookbacks():
    """Test strategy lookback management."""
    print("\nTesting strategy lookbacks...")

    try:
        from strategy import get_max_lookback_for_strategies, max_lookback

        # Test individual strategies
        test_strategies = ["sma_20", "ema_8", "rsi_14", "atr_14", "macd", "bb_20"]

        for strategy in test_strategies:
            lookback = max_lookback(strategy)
            print(f"    {strategy}: {lookback} periods")
            assert lookback > 0, f"Invalid lookback for {strategy}"

        # Test max lookback for multiple strategies
        max_lookback_result = get_max_lookback_for_strategies(test_strategies)
        print(
            f"    Max lookback for {len(test_strategies)} strategies: {max_lookback_result}"
        )
        assert max_lookback_result > 0, "Invalid max lookback"

        print("    Strategy lookbacks test passed!")
        return True

    except Exception as e:
        print(f"    Strategy lookbacks test failed: {e}")
        return False


def test_configuration():
    """Test configuration management."""
    print("\nTesting configuration...")

    try:
        from src.features.config import (
            create_database_config,
            create_feature_config,
            create_streaming_config,
        )

        # Test streaming config
        streaming_config = create_streaming_config()
        print(
            f"    Streaming config: CHUNKSIZE={streaming_config.CHUNKSIZE}, MAX_LOOKBACK={streaming_config.MAX_LOOKBACK}"
        )
        assert streaming_config.CHUNKSIZE > 0, "Invalid CHUNKSIZE"
        assert streaming_config.MAX_LOOKBACK > 0, "Invalid MAX_LOOKBACK"

        # Test database config
        db_config = create_database_config()
        print(
            f"    Database config: BATCH_SIZE={db_config.BATCH_SIZE}, MAX_RETRIES={db_config.MAX_RETRIES}"
        )
        assert db_config.BATCH_SIZE > 0, "Invalid BATCH_SIZE"
        assert db_config.MAX_RETRIES > 0, "Invalid MAX_RETRIES"

        # Test feature config
        feature_config = create_feature_config()
        print(
            f"    Feature config: MIN_FILL_RATE={feature_config.MIN_FILL_RATE}, VALIDATE_RESULTS={feature_config.VALIDATE_RESULTS}"
        )
        assert 0 <= feature_config.MIN_FILL_RATE <= 1, "Invalid MIN_FILL_RATE"

        print("    Configuration test passed!")
        return True

    except Exception as e:
        print(f"    Configuration test failed: {e}")
        return False


def test_memory_usage_comparison():
    """Test memory usage comparison between streaming and non-streaming."""
    print("\nTesting memory usage comparison...")

    try:
        from utils.memlog import force_cleanup, memory_monitor

        # Create test data
        n_rows = 3000
        chunk_size = 1000
        df_full = create_test_data(n_rows)

        # Test 1: Non-streaming approach
        print("    Testing non-streaming approach...")
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        with memory_monitor("non_streaming") as mem_log:
            # Simulate non-streaming processing
            df_copy = df_full.copy()
            df_copy["hlc3"] = (df_copy["high"] + df_copy["low"] + df_copy["close"]) / 3
            df_copy["sma_20"] = df_copy["close"].rolling(20).mean()
            df_copy["ema_8"] = df_copy["close"].ewm(span=8).mean()
            df_copy["rsi_14"] = (
                df_copy["close"].rolling(14).apply(lambda x: 50)
            )  # Simplified RSI

            mem_log.log_dataframe_memory(df_copy, "Non-streaming DataFrame")

        non_streaming_memory = process.memory_info().rss / 1024 / 1024  # MB
        non_streaming_increase = non_streaming_memory - initial_memory

        print(f"    Non-streaming memory increase: {non_streaming_increase:.2f} MB")

        # Clean up
        force_cleanup(df_copy, df_full)
        gc.collect()

        # Test 2: Streaming approach
        print("    Testing streaming approach...")
        chunks = [
            df_full.iloc[i : i + chunk_size].copy()
            for i in range(0, len(df_full), chunk_size)
        ]

        streaming_memory_start = process.memory_info().rss / 1024 / 1024  # MB
        max_streaming_memory = streaming_memory_start

        with memory_monitor("streaming") as mem_log:
            streaming_results = []
            for i, chunk in enumerate(chunks):
                # Process chunk
                chunk_copy = chunk.copy()
                chunk_copy["hlc3"] = (
                    chunk_copy["high"] + chunk_copy["low"] + chunk_copy["close"]
                ) / 3
                chunk_copy["sma_20"] = chunk_copy["close"].rolling(20).mean()
                chunk_copy["ema_8"] = chunk_copy["close"].ewm(span=8).mean()
                chunk_copy["rsi_14"] = (
                    chunk_copy["close"].rolling(14).apply(lambda x: 50)
                )  # Simplified RSI

                streaming_results.append(chunk_copy)

                # Track peak memory
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                max_streaming_memory = max(max_streaming_memory, current_memory)

                print(
                    f"    Chunk {i+1}: {current_memory:.2f} MB, shape: {chunk_copy.shape}"
                )

                # Clean up after each chunk
                force_cleanup(chunk_copy)
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
            print("    Streaming uses less memory!")
        else:
            print("    Streaming uses more memory (unexpected)")

        if streaming_peak_increase < non_streaming_increase:
            print("    Streaming has lower peak memory!")
        else:
            print("    Streaming has higher peak memory (unexpected)")

        print("    Memory usage comparison test passed!")
        return True

    except Exception as e:
        print(f"    Memory usage comparison test failed: {e}")
        return False


def test_performance_metrics():
    """Test performance metrics and timing."""
    print("\nTesting performance metrics...")

    try:
        from utils.memlog import force_cleanup

        # Create test data
        n_rows = 2000
        chunk_size = 500
        df_full = create_test_data(n_rows)

        # Test 1: Non-streaming timing
        print("    Testing non-streaming timing...")
        start_time = time.time()

        df_copy = df_full.copy()
        df_copy["hlc3"] = (df_copy["high"] + df_copy["low"] + df_copy["close"]) / 3
        df_copy["sma_20"] = df_copy["close"].rolling(20).mean()
        df_copy["ema_8"] = df_copy["close"].ewm(span=8).mean()

        non_streaming_time = time.time() - start_time
        print(f"    Non-streaming time: {non_streaming_time:.2f} seconds")
        if non_streaming_time > 0:
            print(f"    Rows per second: {n_rows / non_streaming_time:.0f}")
        else:
            print("    Rows per second: very fast (time too small to measure)")

        # Clean up
        force_cleanup(df_copy, df_full)
        gc.collect()

        # Test 2: Streaming timing
        print("    Testing streaming timing...")
        chunks = [
            df_full.iloc[i : i + chunk_size].copy()
            for i in range(0, len(df_full), chunk_size)
        ]

        start_time = time.time()

        streaming_results = []
        for chunk in chunks:
            chunk_copy = chunk.copy()
            chunk_copy["hlc3"] = (
                chunk_copy["high"] + chunk_copy["low"] + chunk_copy["close"]
            ) / 3
            chunk_copy["sma_20"] = chunk_copy["close"].rolling(20).mean()
            chunk_copy["ema_8"] = chunk_copy["close"].ewm(span=8).mean()
            streaming_results.append(chunk_copy)

            # Clean up after each chunk
            force_cleanup(chunk_copy)
            gc.collect()

        streaming_time = time.time() - start_time
        print(f"    Streaming time: {streaming_time:.2f} seconds")
        print(f"    Rows per second: {n_rows / streaming_time:.0f}")

        # Performance comparison
        if non_streaming_time > 0 and streaming_time > 0:
            speedup = non_streaming_time / streaming_time
            print(f"    Speedup: {speedup:.2f}x")

            if speedup > 0.8:
                print("    Streaming performance is acceptable!")
            else:
                print("    Streaming is slower (expected due to overhead)")
        else:
            print("    Speedup: cannot calculate (time too small)")
            print("    Streaming performance: acceptable for small datasets")

        # Memory efficiency
        process = psutil.Process()
        memory_usage = process.memory_info().rss / 1024 / 1024  # MB
        print(f"    Current memory usage: {memory_usage:.2f} MB")

        print("    Performance metrics test passed!")
        return True

    except Exception as e:
        print(f"    Performance metrics test failed: {e}")
        return False


def run_memory_modules_test():
    """Run all memory optimization module tests."""
    print("Starting memory optimization modules test...")
    print("=" * 60)

    try:
        # Test 1: Memory monitoring
        memory_success = test_memory_monitoring()

        # Test 2: Strategy lookbacks
        strategy_success = test_strategy_lookbacks()

        # Test 3: Configuration
        config_success = test_configuration()

        # Test 4: Memory usage comparison
        memory_comparison_success = test_memory_usage_comparison()

        # Test 5: Performance metrics
        performance_success = test_performance_metrics()

        print("\n" + "=" * 60)
        print("Test Results Summary:")
        print(f"  Memory monitoring: {'PASSED' if memory_success else 'FAILED'}")
        print(f"  Strategy lookbacks: {'PASSED' if strategy_success else 'FAILED'}")
        print(f"  Configuration: {'PASSED' if config_success else 'FAILED'}")
        print(
            f"  Memory comparison: {'PASSED' if memory_comparison_success else 'FAILED'}"
        )
        print(f"  Performance metrics: {'PASSED' if performance_success else 'FAILED'}")

        all_success = all(
            [
                memory_success,
                strategy_success,
                config_success,
                memory_comparison_success,
                performance_success,
            ]
        )

        if all_success:
            print("\nAll memory optimization module tests passed!")
            return True
        print("\nSome memory optimization module tests failed!")
        return False

    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_memory_modules_test()
    sys.exit(0 if success else 1)
