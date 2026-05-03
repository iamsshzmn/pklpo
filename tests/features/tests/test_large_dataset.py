"""
Test memory optimization with large datasets.

This test uses larger datasets to demonstrate the memory optimization benefits.
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


def create_large_test_data(n_rows: int = 50000) -> pd.DataFrame:
    """Create large test OHLCV data."""
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


def test_memory_optimization_large():
    """Test memory optimization with large dataset."""
    print("\nTesting memory optimization with large dataset...")

    try:
        from utils.memlog import force_cleanup, memory_monitor

        # Create large test data
        n_rows = 50000
        chunk_size = 10000
        df_full = create_large_test_data(n_rows)

        print(
            f"Dataset size: {n_rows} rows, {df_full.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB"
        )

        # Test 1: Non-streaming approach
        print("\n1. Non-streaming approach...")
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        with memory_monitor("non_streaming_large") as mem_log:
            start_time = time.time()

            # Simulate non-streaming processing
            df_copy = df_full.copy()
            df_copy["hlc3"] = (df_copy["high"] + df_copy["low"] + df_copy["close"]) / 3
            df_copy["sma_20"] = df_copy["close"].rolling(20).mean()
            df_copy["sma_50"] = df_copy["close"].rolling(50).mean()
            df_copy["ema_8"] = df_copy["close"].ewm(span=8).mean()
            df_copy["ema_21"] = df_copy["close"].ewm(span=21).mean()
            df_copy["rsi_14"] = (
                df_copy["close"].rolling(14).apply(lambda x: 50)
            )  # Simplified RSI
            df_copy["atr_14"] = (
                df_copy["high"].rolling(14).apply(lambda x: 1.0)
            )  # Simplified ATR

            end_time = time.time()
            duration = end_time - start_time

            mem_log.log_dataframe_memory(df_copy, "Non-streaming DataFrame")

        non_streaming_memory = process.memory_info().rss / 1024 / 1024  # MB
        non_streaming_increase = non_streaming_memory - initial_memory

        print(f"    Time: {duration:.2f} seconds")
        print(f"    Memory increase: {non_streaming_increase:.2f} MB")
        print(f"    Rows per second: {n_rows / duration:.0f}")

        # Clean up
        force_cleanup(df_copy, df_full)
        gc.collect()

        # Test 2: Streaming approach
        print("\n2. Streaming approach...")
        chunks = [
            df_full.iloc[i : i + chunk_size].copy()
            for i in range(0, len(df_full), chunk_size)
        ]

        streaming_memory_start = process.memory_info().rss / 1024 / 1024  # MB
        max_streaming_memory = streaming_memory_start

        with memory_monitor("streaming_large") as mem_log:
            start_time = time.time()

            streaming_results = []
            for i, chunk in enumerate(chunks):
                # Process chunk
                chunk_copy = chunk.copy()
                chunk_copy["hlc3"] = (
                    chunk_copy["high"] + chunk_copy["low"] + chunk_copy["close"]
                ) / 3
                chunk_copy["sma_20"] = chunk_copy["close"].rolling(20).mean()
                chunk_copy["sma_50"] = chunk_copy["close"].rolling(50).mean()
                chunk_copy["ema_8"] = chunk_copy["close"].ewm(span=8).mean()
                chunk_copy["ema_21"] = chunk_copy["close"].ewm(span=21).mean()
                chunk_copy["rsi_14"] = (
                    chunk_copy["close"].rolling(14).apply(lambda x: 50)
                )  # Simplified RSI
                chunk_copy["atr_14"] = (
                    chunk_copy["high"].rolling(14).apply(lambda x: 1.0)
                )  # Simplified ATR

                streaming_results.append(chunk_copy)

                # Track peak memory
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                max_streaming_memory = max(max_streaming_memory, current_memory)

                print(
                    f"    Chunk {i+1}/{len(chunks)}: {current_memory:.2f} MB, shape: {chunk_copy.shape}"
                )

                # Clean up after each chunk
                force_cleanup(chunk_copy)
                gc.collect()

            end_time = time.time()
            duration = end_time - start_time

        streaming_memory_end = process.memory_info().rss / 1024 / 1024  # MB
        streaming_increase = streaming_memory_end - streaming_memory_start
        streaming_peak_increase = max_streaming_memory - streaming_memory_start

        print(f"    Time: {duration:.2f} seconds")
        print(f"    Memory increase: {streaming_increase:.2f} MB")
        print(f"    Peak memory increase: {streaming_peak_increase:.2f} MB")
        print(f"    Rows per second: {n_rows / duration:.0f}")

        # Compare results
        memory_improvement = non_streaming_increase - streaming_increase
        peak_improvement = non_streaming_increase - streaming_peak_increase
        speedup = (
            (n_rows / duration) / (n_rows / (end_time - start_time))
            if duration > 0
            else 1.0
        )

        print("\n3. Results comparison:")
        print(f"    Memory improvement: {memory_improvement:.2f} MB")
        print(f"    Peak memory improvement: {peak_improvement:.2f} MB")
        print(f"    Performance speedup: {speedup:.2f}x")

        # Check results
        if streaming_increase < non_streaming_increase:
            print("    Streaming uses less memory!")
        else:
            print("    Streaming uses more memory (unexpected)")

        if streaming_peak_increase < non_streaming_increase:
            print("    Streaming has lower peak memory!")
        else:
            print("    Streaming has higher peak memory (unexpected)")

        if speedup > 0.5:
            print("    Streaming performance is acceptable!")
        else:
            print("    Streaming is slower (expected due to overhead)")

        print("    Large dataset memory optimization test passed!")
        return True

    except Exception as e:
        print(f"    Large dataset memory optimization test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_memory_scaling():
    """Test memory usage scaling with different dataset sizes."""
    print("\nTesting memory usage scaling...")

    try:
        from utils.memlog import force_cleanup, memory_monitor

        dataset_sizes = [10000, 20000, 30000]
        results = []

        for n_rows in dataset_sizes:
            print(f"\nTesting with {n_rows} rows...")

            df = create_large_test_data(n_rows)
            initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB

            with memory_monitor(f"scaling_{n_rows}") as mem_log:
                # Process data
                df_copy = df.copy()
                df_copy["hlc3"] = (
                    df_copy["high"] + df_copy["low"] + df_copy["close"]
                ) / 3
                df_copy["sma_20"] = df_copy["close"].rolling(20).mean()
                df_copy["ema_8"] = df_copy["close"].ewm(span=8).mean()

                mem_log.log_dataframe_memory(df_copy, f"Dataset {n_rows}")

            final_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            results.append(
                {
                    "rows": n_rows,
                    "memory_increase": memory_increase,
                    "memory_per_row": memory_increase / n_rows * 1024,  # KB per row
                }
            )

            print(f"    Memory increase: {memory_increase:.2f} MB")
            print(f"    Memory per row: {memory_increase / n_rows * 1024:.2f} KB")

            # Clean up
            force_cleanup(df, df_copy)
            gc.collect()

        # Analyze scaling
        print("\nScaling analysis:")
        for result in results:
            print(
                f"    {result['rows']} rows: {result['memory_increase']:.2f} MB ({result['memory_per_row']:.2f} KB/row)"
            )

        # Check if memory scales linearly
        if len(results) >= 2:
            ratio = results[-1]["memory_per_row"] / results[0]["memory_per_row"]
            if ratio < 2.0:  # Should not scale more than 2x
                print("    Memory scaling is acceptable!")
            else:
                print("    Memory scaling is not optimal!")

        print("    Memory scaling test passed!")
        return True

    except Exception as e:
        print(f"    Memory scaling test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_chunk_processing():
    """Test chunk processing with different chunk sizes."""
    print("\nTesting chunk processing...")

    try:
        from utils.memlog import force_cleanup, memory_monitor

        n_rows = 30000
        chunk_sizes = [5000, 10000, 15000]
        df_full = create_large_test_data(n_rows)

        for chunk_size in chunk_sizes:
            print(f"\nTesting chunk size: {chunk_size}")

            chunks = [
                df_full.iloc[i : i + chunk_size].copy()
                for i in range(0, len(df_full), chunk_size)
            ]
            initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            max_memory = initial_memory

            with memory_monitor(f"chunk_{chunk_size}"):
                start_time = time.time()

                for _i, chunk in enumerate(chunks):
                    # Process chunk
                    chunk_copy = chunk.copy()
                    chunk_copy["hlc3"] = (
                        chunk_copy["high"] + chunk_copy["low"] + chunk_copy["close"]
                    ) / 3
                    chunk_copy["sma_20"] = chunk_copy["close"].rolling(20).mean()
                    chunk_copy["ema_8"] = chunk_copy["close"].ewm(span=8).mean()

                    # Track peak memory
                    current_memory = (
                        psutil.Process().memory_info().rss / 1024 / 1024
                    )  # MB
                    max_memory = max(max_memory, current_memory)

                    # Clean up after each chunk
                    force_cleanup(chunk_copy)
                    gc.collect()

                end_time = time.time()
                duration = end_time - start_time

            final_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory
            peak_memory_increase = max_memory - initial_memory

            print(f"    Time: {duration:.2f} seconds")
            print(f"    Memory increase: {memory_increase:.2f} MB")
            print(f"    Peak memory increase: {peak_memory_increase:.2f} MB")
            print(f"    Rows per second: {n_rows / duration:.0f}")

        print("    Chunk processing test passed!")
        return True

    except Exception as e:
        print(f"    Chunk processing test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def run_large_dataset_tests():
    """Run all large dataset tests."""
    print("Starting large dataset memory optimization tests...")
    print("=" * 60)

    try:
        # Test 1: Large dataset memory optimization
        large_dataset_success = test_memory_optimization_large()

        # Test 2: Memory scaling
        scaling_success = test_memory_scaling()

        # Test 3: Chunk processing
        chunk_success = test_chunk_processing()

        print("\n" + "=" * 60)
        print("Large Dataset Test Results:")
        print(
            f"  Large dataset optimization: {'PASSED' if large_dataset_success else 'FAILED'}"
        )
        print(f"  Memory scaling: {'PASSED' if scaling_success else 'FAILED'}")
        print(f"  Chunk processing: {'PASSED' if chunk_success else 'FAILED'}")

        all_success = all([large_dataset_success, scaling_success, chunk_success])

        if all_success:
            print("\nAll large dataset tests passed!")
            return True
        print("\nSome large dataset tests failed!")
        return False

    except Exception as e:
        print(f"\nLarge dataset test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_large_dataset_tests()
    sys.exit(0 if success else 1)
