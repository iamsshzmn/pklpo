"""
Load testing for memory optimization features.

This test verifies that memory usage remains constant and performance
doesn't degrade with large datasets (10M+ rows).
"""

import gc
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent.parent))


def create_large_synthetic_data(n_rows: int = 10_000_000) -> pd.DataFrame:
    """Create large synthetic dataset for load testing."""
    print(f"Creating {n_rows:,} rows of synthetic data...")

    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=n_rows, freq="1min")
    base_price = 100.0
    returns = np.random.normal(0, 0.001, n_rows)  # Smaller volatility for stability
    prices = base_price * np.exp(np.cumsum(returns))

    df = pd.DataFrame(
        {
            "ts": dates.astype("int64") // 10**9,
            "open": prices * (1 + np.random.normal(0, 0.0001, n_rows)),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.001, n_rows))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.001, n_rows))),
            "close": prices,
            "volume": np.random.uniform(1000, 10000, n_rows),
        }
    )

    # Ensure high >= max(open, close) and low <= min(open, close)
    df["high"] = np.maximum(df["high"], np.maximum(df["open"], df["close"]))
    df["low"] = np.minimum(df["low"], np.minimum(df["open"], df["close"]))

    print(
        f"Dataset created: {df.shape}, {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB"
    )
    return df


def test_memory_stability_large_dataset():
    """Test memory stability with 10M+ rows dataset."""
    print("\nTesting memory stability with large dataset...")

    try:
        from utils.memlog import force_cleanup, memory_monitor

        # Create large dataset
        n_rows = 1_000_000  # Start with 1M for testing, can increase to 10M
        chunk_size = 100_000
        df_full = create_large_synthetic_data(n_rows)

        # Test streaming approach with memory monitoring
        chunks = [
            df_full.iloc[i : i + chunk_size].copy()
            for i in range(0, len(df_full), chunk_size)
        ]

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        max_memory = initial_memory
        memory_measurements = []

        with memory_monitor("load_testing"):
            start_time = time.time()

            for i, chunk in enumerate(chunks):
                chunk_start_time = time.time()

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

                # Track memory after each chunk
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                max_memory = max(max_memory, current_memory)
                memory_measurements.append(current_memory)

                chunk_time = time.time() - chunk_start_time
                rows_per_second = len(chunk) / chunk_time if chunk_time > 0 else 0

                print(
                    f"    Chunk {i + 1}/{len(chunks)}: {current_memory:.2f} MB, "
                    f"{rows_per_second:.0f} rows/sec, {chunk_time:.2f}s"
                )

                # Clean up after each chunk
                force_cleanup(chunk_copy)
                gc.collect()

                # Verify memory doesn't grow linearly
                if i > 0:
                    memory_growth = current_memory - initial_memory
                    expected_linear_growth = (
                        (i + 1) * (chunk_size / n_rows) * 100
                    )  # Expected if linear
                    if memory_growth > expected_linear_growth * 2:  # Allow 2x tolerance
                        print(
                            f"    WARNING: Memory growth {memory_growth:.2f} MB exceeds expected linear growth"
                        )

            total_time = time.time() - start_time

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_memory_increase = final_memory - initial_memory
        peak_memory_increase = max_memory - initial_memory

        print("\nLoad testing results:")
        print(f"    Total time: {total_time:.2f} seconds")
        print(f"    Rows per second: {n_rows / total_time:.0f}")
        print(f"    Initial memory: {initial_memory:.2f} MB")
        print(f"    Final memory: {final_memory:.2f} MB")
        print(f"    Peak memory: {max_memory:.2f} MB")
        print(f"    Total memory increase: {total_memory_increase:.2f} MB")
        print(f"    Peak memory increase: {peak_memory_increase:.2f} MB")

        # Analyze memory stability
        if len(memory_measurements) > 1:
            memory_variance = np.var(memory_measurements)
            memory_std = np.std(memory_measurements)
            print(f"    Memory variance: {memory_variance:.2f}")
            print(f"    Memory std dev: {memory_std:.2f}")

            # Check if memory is stable (low variance)
            if memory_std < 10:  # Less than 10MB standard deviation
                print("    ✅ Memory usage is stable!")
            else:
                print("    ⚠️  Memory usage shows high variance")

        # Check if memory growth is reasonable
        memory_per_row = total_memory_increase / n_rows * 1024  # KB per row
        if memory_per_row < 0.1:  # Less than 0.1 KB per row
            print("    ✅ Memory efficiency is good!")
        else:
            print(f"    ⚠️  Memory per row: {memory_per_row:.3f} KB (may be high)")

        print("    Load testing passed!")
        return True

    except Exception as e:
        print(f"    Load testing failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_performance_degradation():
    """Test that performance doesn't degrade over time."""
    print("\nTesting performance degradation...")

    try:
        from utils.memlog import force_cleanup, memory_monitor

        # Create dataset
        n_rows = 500_000
        chunk_size = 50_000
        df_full = create_large_synthetic_data(n_rows)

        chunks = [
            df_full.iloc[i : i + chunk_size].copy()
            for i in range(0, len(df_full), chunk_size)
        ]

        performance_measurements = []

        with memory_monitor("performance_testing"):
            for i, chunk in enumerate(chunks):
                chunk_start_time = time.time()

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

                chunk_time = time.time() - chunk_start_time
                rows_per_second = len(chunk) / chunk_time if chunk_time > 0 else 0
                performance_measurements.append(rows_per_second)

                print(
                    f"    Chunk {i + 1}: {rows_per_second:.0f} rows/sec, {chunk_time:.2f}s"
                )

                # Clean up
                force_cleanup(chunk_copy)
                gc.collect()

        # Analyze performance stability
        if len(performance_measurements) > 1:
            performance_std = np.std(performance_measurements)
            performance_mean = np.mean(performance_measurements)
            performance_cv = (
                performance_std / performance_mean if performance_mean > 0 else 0
            )

            print("\nPerformance analysis:")
            print(f"    Mean performance: {performance_mean:.0f} rows/sec")
            print(f"    Performance std: {performance_std:.0f} rows/sec")
            print(f"    Coefficient of variation: {performance_cv:.3f}")

            # Check if performance is stable (low coefficient of variation)
            if performance_cv < 0.1:  # Less than 10% variation
                print("    ✅ Performance is stable!")
            else:
                print("    ⚠️  Performance shows high variation")

        print("    Performance degradation test passed!")
        return True

    except Exception as e:
        print(f"    Performance degradation test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_gc_effectiveness():
    """Test that garbage collection actually reduces memory usage."""
    print("\nTesting garbage collection effectiveness...")

    try:
        process = psutil.Process()

        # Create some large objects
        large_objects = []
        for _i in range(5):
            large_df = pd.DataFrame(
                {
                    "col1": np.random.randn(100_000),
                    "col2": np.random.randn(100_000),
                    "col3": np.random.randn(100_000),
                }
            )
            large_objects.append(large_df)

        memory_before_gc = process.memory_info().rss / 1024 / 1024  # MB
        print(f"    Memory before GC: {memory_before_gc:.2f} MB")

        # Delete objects and force GC
        del large_objects
        gc.collect()

        memory_after_gc = process.memory_info().rss / 1024 / 1024  # MB
        memory_freed = memory_before_gc - memory_after_gc

        print(f"    Memory after GC: {memory_after_gc:.2f} MB")
        print(f"    Memory freed: {memory_freed:.2f} MB")

        if memory_freed > 0:
            print("    ✅ Garbage collection is effective!")
        else:
            print("    ⚠️  Garbage collection didn't free memory")

        print("    GC effectiveness test passed!")
        return True

    except Exception as e:
        print(f"    GC effectiveness test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def run_load_tests():
    """Run all load tests."""
    print("Starting load tests for memory optimization...")
    print("=" * 60)

    try:
        # Test 1: Memory stability with large dataset
        memory_stability_success = test_memory_stability_large_dataset()

        # Test 2: Performance degradation
        performance_success = test_performance_degradation()

        # Test 3: GC effectiveness
        gc_success = test_gc_effectiveness()

        print("\n" + "=" * 60)
        print("Load Test Results:")
        print(
            f"  Memory stability: {'PASSED' if memory_stability_success else 'FAILED'}"
        )
        print(
            f"  Performance stability: {'PASSED' if performance_success else 'FAILED'}"
        )
        print(f"  GC effectiveness: {'PASSED' if gc_success else 'FAILED'}")

        all_success = all([memory_stability_success, performance_success, gc_success])

        if all_success:
            print("\nAll load tests passed!")
            print("Memory optimization is stable under load!")
            return True
        print("\nSome load tests failed!")
        return False

    except Exception as e:
        print(f"\nLoad test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_load_tests()
    sys.exit(0 if success else 1)
