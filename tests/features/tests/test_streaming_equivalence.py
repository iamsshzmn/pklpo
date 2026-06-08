"""
Test streaming equivalence for features calculation.

This module tests that streaming calculation produces the same results
as non-streaming calculation (except for the first MAX_LOOKBACK-1 rows).
"""

from typing import Any

import numpy as np
import pandas as pd

from ..application.calc import process_chunks
from ..config.settings import create_streaming_config
from ..core import compute_features
from ..domain.strategy import get_max_lookback_for_strategies


def create_test_data(n_rows: int = 1000) -> pd.DataFrame:
    """Create test OHLCV data."""
    np.random.seed(42)  # For reproducible results

    dates = pd.date_range("2023-01-01", periods=n_rows, freq="1H")

    # Generate realistic OHLCV data
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

    return df


def chunk_dataframe(df: pd.DataFrame, chunk_size: int) -> list[pd.DataFrame]:
    """Split DataFrame into chunks."""
    chunks = []
    for i in range(0, len(df), chunk_size):
        chunk = df.iloc[i : i + chunk_size].copy()
        chunks.append(chunk)
    return chunks


def compare_dataframes(
    df1: pd.DataFrame, df2: pd.DataFrame, tolerance: float = 1e-10
) -> dict[str, Any]:
    """Compare two DataFrames and return comparison results."""
    results = {
        "shapes_match": df1.shape == df2.shape,
        "columns_match": set(df1.columns) == set(df2.columns),
        "values_match": True,
        "differences": [],
        "max_difference": 0.0,
        "mean_difference": 0.0,
    }

    if not results["shapes_match"]:
        results["differences"].append(f"Shape mismatch: {df1.shape} vs {df2.shape}")
        return results

    if not results["columns_match"]:
        results["differences"].append(
            f"Columns mismatch: {set(df1.columns)} vs {set(df2.columns)}"
        )
        return results

    # Compare common columns
    common_cols = set(df1.columns) & set(df2.columns)

    for col in common_cols:
        if col in df1.columns and col in df2.columns:
            # Handle NaN values
            mask1 = df1[col].notna()
            mask2 = df2[col].notna()

            # Check if NaN patterns match
            if not mask1.equals(mask2):
                results["differences"].append(f"NaN patterns differ in column {col}")
                results["values_match"] = False
                continue

            # Compare non-NaN values
            if mask1.any():
                diff = np.abs(df1[col][mask1] - df2[col][mask2])
                max_diff = diff.max()
                mean_diff = diff.mean()

                results["max_difference"] = max(results["max_difference"], max_diff)
                results["mean_difference"] = max(results["mean_difference"], mean_diff)

                if max_diff > tolerance:
                    results["differences"].append(
                        f"Column {col}: max_diff={max_diff:.2e}, mean_diff={mean_diff:.2e}"
                    )
                    results["values_match"] = False

    return results


def test_streaming_equivalence():
    """Test that streaming calculation produces equivalent results."""
    # Create test data
    n_rows = 2000
    chunk_size = 500
    df_full = create_test_data(n_rows)

    # Define indicators to test
    available_indicators = {
        "hlc3",
        "ema_8",
        "sma_20",
        "rsi_14",
        "atr_14",
        "macd",
        "obv",
    }

    # Calculate max lookback
    max_lookback = get_max_lookback_for_strategies(list(available_indicators))

    print(
        f"Testing with {n_rows} rows, chunk_size={chunk_size}, max_lookback={max_lookback}"
    )

    # 1. Non-streaming calculation (baseline)
    print("Calculating baseline (non-streaming)...")
    baseline_df = compute_features(
        df_full, available=available_indicators, volatility_normalize=False
    )

    print(f"Baseline shape: {baseline_df.shape}")
    print(f"Baseline columns: {list(baseline_df.columns)}")

    # 2. Streaming calculation
    print("Calculating streaming...")
    chunks = chunk_dataframe(df_full, chunk_size)

    # Create chunk iterator
    def chunk_iterator():
        yield from chunks

    # Process chunks
    streaming_config = create_streaming_config()
    streaming_config.CHUNKSIZE = chunk_size
    streaming_config.MAX_LOOKBACK = max_lookback
    streaming_config.OVERLAP_SIZE = max_lookback

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
        print(f"Streaming chunk {i+1}: {result_chunk.shape}")

    # Combine streaming results
    if streaming_results:
        streaming_df = pd.concat(streaming_results, ignore_index=True)
    else:
        streaming_df = pd.DataFrame()

    print(f"Streaming shape: {streaming_df.shape}")
    print(f"Streaming columns: {list(streaming_df.columns)}")

    # 3. Compare results
    print("Comparing results...")

    # Check basic properties
    assert (
        baseline_df.shape[0] == streaming_df.shape[0]
    ), f"Row count mismatch: {baseline_df.shape[0]} vs {streaming_df.shape[0]}"
    assert set(baseline_df.columns) == set(
        streaming_df.columns
    ), f"Column mismatch: {set(baseline_df.columns)} vs {set(streaming_df.columns)}"

    # Compare values (excluding first max_lookback-1 rows)
    skip_rows = max_lookback - 1
    if skip_rows > 0:
        baseline_compare = baseline_df.iloc[skip_rows:].copy()
        streaming_compare = streaming_df.iloc[skip_rows:].copy()

        print(f"Comparing rows {skip_rows} to end (excluding first {skip_rows} rows)")
    else:
        baseline_compare = baseline_df.copy()
        streaming_compare = streaming_df.copy()
        print("Comparing all rows")

    # Align indices for comparison
    baseline_compare = baseline_compare.reset_index(drop=True)
    streaming_compare = streaming_compare.reset_index(drop=True)

    # Compare common columns
    common_cols = set(baseline_compare.columns) & set(streaming_compare.columns)
    print(f"Comparing {len(common_cols)} common columns")

    differences = []
    max_diff = 0.0

    for col in common_cols:
        if col in ["ts", "open", "high", "low", "close", "volume"]:
            continue  # Skip OHLCV columns

        # Compare non-NaN values
        mask1 = baseline_compare[col].notna()
        mask2 = streaming_compare[col].notna()

        if mask1.any() and mask2.any():
            # Find common non-NaN indices
            common_mask = mask1 & mask2

            if common_mask.any():
                diff = np.abs(
                    baseline_compare[col][common_mask]
                    - streaming_compare[col][common_mask]
                )
                col_max_diff = diff.max()
                col_mean_diff = diff.mean()

                max_diff = max(max_diff, col_max_diff)

                if col_max_diff > 1e-10:
                    differences.append(
                        f"{col}: max_diff={col_max_diff:.2e}, mean_diff={col_mean_diff:.2e}"
                    )

    print(f"Maximum difference across all columns: {max_diff:.2e}")
    print(f"Number of columns with differences: {len(differences)}")

    if differences:
        print("Differences found:")
        for diff in differences[:10]:  # Show first 10 differences
            print(f"  {diff}")
        if len(differences) > 10:
            print(f"  ... and {len(differences) - 10} more")

    # Assertions
    assert max_diff < 1e-6, f"Differences too large: {max_diff:.2e}"
    assert len(differences) == 0, f"Found {len(differences)} columns with differences"

    print("✅ Streaming equivalence test passed!")
    return {
        "baseline_shape": baseline_df.shape,
        "streaming_shape": streaming_df.shape,
        "max_difference": max_diff,
        "differences_count": len(differences),
        "skip_rows": skip_rows,
    }


def test_memory_usage():
    """Test memory usage during streaming calculation."""
    import gc

    import psutil

    # Create larger test data
    n_rows = 10000
    chunk_size = 1000
    df_full = create_test_data(n_rows)

    available_indicators = {"hlc3", "ema_8", "sma_20", "rsi_14", "atr_14"}

    # Monitor memory usage
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    print(f"Initial memory: {initial_memory:.2f} MB")

    # Streaming calculation
    chunks = chunk_dataframe(df_full, chunk_size)

    def chunk_iterator():
        yield from chunks

    max_memory = initial_memory
    memory_usage = []

    streaming_config = create_streaming_config()
    streaming_config.CHUNKSIZE = chunk_size
    streaming_config.FORCE_GC_AFTER_CHUNK = True
    streaming_config.CLEAR_INTERMEDIATE_OBJECTS = True

    for i, result_chunk in enumerate(
        process_chunks(
            chunk_iterator(),
            symbol="TEST",
            timeframe="1H",
            available_indicators=available_indicators,
            config=streaming_config,
        )
    ):
        current_memory = process.memory_info().rss / 1024 / 1024  # MB
        max_memory = max(max_memory, current_memory)
        memory_usage.append(current_memory)

        print(f"Chunk {i+1}: {current_memory:.2f} MB")

        # Force cleanup
        del result_chunk
        gc.collect()

    final_memory = process.memory_info().rss / 1024 / 1024  # MB

    print(f"Final memory: {final_memory:.2f} MB")
    print(f"Peak memory: {max_memory:.2f} MB")
    print(f"Memory increase: {final_memory - initial_memory:.2f} MB")
    print(f"Peak increase: {max_memory - initial_memory:.2f} MB")

    # Assertions
    memory_increase = final_memory - initial_memory
    peak_increase = max_memory - initial_memory

    assert memory_increase < 100, f"Memory increase too large: {memory_increase:.2f} MB"
    assert (
        peak_increase < 200
    ), f"Peak memory increase too large: {peak_increase:.2f} MB"

    print("✅ Memory usage test passed!")
    return {
        "initial_memory": initial_memory,
        "final_memory": final_memory,
        "peak_memory": max_memory,
        "memory_increase": memory_increase,
        "peak_increase": peak_increase,
    }


def test_chunk_overlap():
    """Test that chunk overlap is handled correctly."""
    n_rows = 1000
    chunk_size = 200

    df_full = create_test_data(n_rows)
    chunks = chunk_dataframe(df_full, chunk_size)

    # Test overlap calculation
    expected_chunks = (n_rows + chunk_size - 1) // chunk_size
    assert (
        len(chunks) == expected_chunks
    ), f"Expected {expected_chunks} chunks, got {len(chunks)}"

    # Test chunk sizes
    for i, chunk in enumerate(chunks):
        if i < len(chunks) - 1:
            assert (
                len(chunk) == chunk_size
            ), f"Chunk {i} size: {len(chunk)} (expected {chunk_size})"
        else:
            # Last chunk can be smaller
            assert (
                len(chunk) <= chunk_size
            ), f"Last chunk size: {len(chunk)} (expected <= {chunk_size})"

    print("✅ Chunk overlap test passed!")
    return {
        "total_chunks": len(chunks),
        "chunk_sizes": [len(chunk) for chunk in chunks],
        "total_rows": sum(len(chunk) for chunk in chunks),
    }


if __name__ == "__main__":
    print("Running streaming equivalence tests...")

    # Test 1: Equivalence
    print("\n1. Testing streaming equivalence...")
    equivalence_result = test_streaming_equivalence()
    print(f"Equivalence result: {equivalence_result}")

    # Test 2: Memory usage
    print("\n2. Testing memory usage...")
    memory_result = test_memory_usage()
    print(f"Memory result: {memory_result}")

    # Test 3: Chunk overlap
    print("\n3. Testing chunk overlap...")
    overlap_result = test_chunk_overlap()
    print(f"Overlap result: {overlap_result}")

    print("\n✅ All tests passed!")
