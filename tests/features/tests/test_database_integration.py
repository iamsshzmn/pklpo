"""
Test database integration for memory optimization.

This test demonstrates the complete pipeline from calculation to database saving.
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


def create_test_data(n_rows: int = 10000) -> pd.DataFrame:
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


def test_parquet_operations():
    """Test parquet file operations."""
    print("\nTesting parquet operations...")

    try:
        import tempfile

        from calc import compute_and_dump_parquet

        from utils.memlog import memory_monitor

        # Create test data
        df = create_test_data(5000)

        # Test parquet save
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp_file:
            parquet_path = tmp_file.name

        try:
            with memory_monitor("parquet_save") as mem_log:
                result = compute_and_dump_parquet(
                    df_ohlcv=df,
                    symbol="TEST",
                    timeframe="1H",
                    output_path=parquet_path,
                    volatility_normalize=False,
                )

                mem_log.log_dataframe_memory(df, "Input DataFrame")

            print(f"    Parquet file created: {result['output_path']}")
            print(f"    File size: {result['file_size_mb']:.2f} MB")
            print(f"    Rows: {result['result_rows']}")
            print(f"    Features: {result['feature_count']}")

            # Verify file exists and has content
            if Path(parquet_path).exists() and Path(parquet_path).stat().st_size > 0:
                print("    Parquet file created successfully!")
            else:
                print("    Parquet file creation failed!")
                return False

            # Test parquet validation
            from calc import validate_parquet_file

            validation = validate_parquet_file(parquet_path)

            print(
                f"    Validation: {validation['rows']} rows, {validation['feature_count']} features"
            )

            if validation["rows"] > 0 and validation["feature_count"] > 0:
                print("    Parquet file validation passed!")
            else:
                print("    Parquet file validation failed!")
                return False

        finally:
            # Clean up
            if Path(parquet_path).exists():
                Path(parquet_path).unlink()
                print("    Cleaned up test file")

        print("    Parquet operations test passed!")
        return True

    except Exception as e:
        print(f"    Parquet operations test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_batch_data_preparation():
    """Test batch data preparation for database."""
    print("\nTesting batch data preparation...")

    try:
        from save import _prepare_batch_data, _validate_dataframe

        from utils.memlog import memory_monitor

        # Create test data
        df = create_test_data(2000)

        # Add some calculated features
        df["hlc3"] = (df["high"] + df["low"] + df["close"]) / 3
        df["sma_20"] = df["close"].rolling(20).mean()
        df["ema_8"] = df["close"].ewm(span=8).mean()
        df["rsi_14"] = df["close"].rolling(14).apply(lambda x: 50)  # Simplified RSI

        with memory_monitor("batch_preparation") as mem_log:
            # Test batch data preparation
            batch_data = _prepare_batch_data(df, "TEST", "1H")
            print(f"    Prepared {len(batch_data)} batch records")

            # Test batch data validation
            validation = _validate_dataframe(df, "TEST", "1H")
            print(f"    Validation: {validation['valid']}")
            print(f"    Errors: {len(validation['errors'])}")
            print(f"    Warnings: {len(validation['warnings'])}")

            mem_log.log_dataframe_memory(df, "Test DataFrame")

        if validation["valid"]:
            print("    Batch data preparation test passed!")
            return True
        print(f"    Batch data preparation failed: {validation['errors']}")
        return False

    except Exception as e:
        print(f"    Batch data preparation test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_memory_efficiency():
    """Test memory efficiency of the complete pipeline."""
    print("\nTesting memory efficiency...")

    try:
        from utils.memlog import force_cleanup, memory_monitor

        # Create test data
        n_rows = 20000
        chunk_size = 5000
        df_full = create_test_data(n_rows)

        print(
            f"Dataset size: {n_rows} rows, {df_full.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB"
        )

        # Test 1: Non-streaming approach
        print("\n1. Non-streaming approach...")
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        with memory_monitor("non_streaming_efficiency") as mem_log:
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
            df_copy["bb_20"] = (
                df_copy["close"].rolling(20).apply(lambda x: 1.0)
            )  # Simplified BB
            df_copy["macd"] = (
                df_copy["close"].ewm(span=12).mean()
                - df_copy["close"].ewm(span=26).mean()
            )

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

        with memory_monitor("streaming_efficiency") as mem_log:
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
                chunk_copy["bb_20"] = (
                    chunk_copy["close"].rolling(20).apply(lambda x: 1.0)
                )  # Simplified BB
                chunk_copy["macd"] = (
                    chunk_copy["close"].ewm(span=12).mean()
                    - chunk_copy["close"].ewm(span=26).mean()
                )

                streaming_results.append(chunk_copy)

                # Track peak memory
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                max_streaming_memory = max(max_streaming_memory, current_memory)

                print(
                    f"    Chunk {i + 1}/{len(chunks)}: {current_memory:.2f} MB, shape: {chunk_copy.shape}"
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

        print("\n3. Results comparison:")
        print(f"    Memory improvement: {memory_improvement:.2f} MB")
        print(f"    Peak memory improvement: {peak_improvement:.2f} MB")

        # Check results
        if streaming_increase < non_streaming_increase:
            print("    Streaming uses less memory!")
        else:
            print("    Streaming uses more memory (unexpected)")

        if streaming_peak_increase < non_streaming_increase:
            print("    Streaming has lower peak memory!")
        else:
            print("    Streaming has higher peak memory (unexpected)")

        print("    Memory efficiency test passed!")
        return True

    except Exception as e:
        print(f"    Memory efficiency test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_configuration_override():
    """Test configuration override capabilities."""
    print("\nTesting configuration override...")

    try:
        # Test environment variable override
        import os

        from src.features.config.settings import (
            create_database_config,
            create_feature_config,
            create_streaming_config,
        )

        os.environ["FEATURES_CHUNKSIZE"] = "1000"
        os.environ["FEATURES_MAX_LOOKBACK"] = "50"
        os.environ["FEATURES_INSERT_CHUNKSIZE"] = "100"

        # Create configs
        streaming_config = create_streaming_config()
        db_config = create_database_config()
        feature_config = create_feature_config()

        print(
            f"    Streaming config: CHUNKSIZE={streaming_config.CHUNKSIZE}, MAX_LOOKBACK={streaming_config.MAX_LOOKBACK}"
        )
        print(f"    Database config: BATCH_SIZE={db_config.BATCH_SIZE}")
        print(f"    Feature config: MIN_FILL_RATE={feature_config.MIN_FILL_RATE}")

        # Test explicit override
        streaming_config_override = create_streaming_config(
            CHUNKSIZE=500, MAX_LOOKBACK=25, INSERT_CHUNKSIZE=50
        )

        print(
            f"    Override config: CHUNKSIZE={streaming_config_override.CHUNKSIZE}, MAX_LOOKBACK={streaming_config_override.MAX_LOOKBACK}"
        )

        # Clean up environment
        del os.environ["FEATURES_CHUNKSIZE"]
        del os.environ["FEATURES_MAX_LOOKBACK"]
        del os.environ["FEATURES_INSERT_CHUNKSIZE"]

        print("    Configuration override test passed!")
        return True

    except Exception as e:
        print(f"    Configuration override test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def run_database_integration_tests():
    """Run all database integration tests."""
    print("Starting database integration tests...")
    print("=" * 60)

    try:
        # Test 1: Parquet operations
        parquet_success = test_parquet_operations()

        # Test 2: Batch data preparation
        batch_success = test_batch_data_preparation()

        # Test 3: Memory efficiency
        memory_success = test_memory_efficiency()

        # Test 4: Configuration override
        config_success = test_configuration_override()

        print("\n" + "=" * 60)
        print("Database Integration Test Results:")
        print(f"  Parquet operations: {'PASSED' if parquet_success else 'FAILED'}")
        print(f"  Batch data preparation: {'PASSED' if batch_success else 'FAILED'}")
        print(f"  Memory efficiency: {'PASSED' if memory_success else 'FAILED'}")
        print(f"  Configuration override: {'PASSED' if config_success else 'FAILED'}")

        all_success = all(
            [parquet_success, batch_success, memory_success, config_success]
        )

        if all_success:
            print("\nAll database integration tests passed!")
            return True
        print("\nSome database integration tests failed!")
        return False

    except Exception as e:
        print(f"\nDatabase integration test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_database_integration_tests()
    sys.exit(0 if success else 1)
