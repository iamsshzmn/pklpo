"""
Demo script for memory optimization features.

This script demonstrates the memory optimization features in action.
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

# Import from local modules
from calc import compute_and_dump_parquet, process_chunks
from core import compute_features
from strategy import get_max_lookback_for_strategies
from utils.memlog import force_cleanup, memory_monitor

from src.features.config import create_streaming_config


def create_demo_data(n_rows: int = 10000) -> pd.DataFrame:
    """Create demo OHLCV data."""
    print(f"📊 Creating {n_rows} rows of demo data...")

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


def chunk_dataframe(df: pd.DataFrame, chunk_size: int):
    """Split DataFrame into chunks."""
    chunks = []
    for i in range(0, len(df), chunk_size):
        chunk = df.iloc[i : i + chunk_size].copy()
        chunks.append(chunk)
    return chunks


def demo_memory_optimization():
    """Demonstrate memory optimization features."""
    print("🚀 Memory Optimization Demo")
    print("=" * 50)

    # Create demo data
    n_rows = 15000
    chunk_size = 3000
    df_full = create_demo_data(n_rows)

    available_indicators = {
        "hlc3",
        "ema_8",
        "sma_20",
        "rsi_14",
        "atr_14",
        "macd",
        "bb_20",
        "obv",
    }

    print(f"📈 Data: {n_rows} rows, {len(available_indicators)} indicators")
    print(f"🔧 Chunk size: {chunk_size} rows")

    # Demo 1: Non-streaming approach
    print("\n1️⃣ Non-streaming approach (baseline)...")
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    with memory_monitor("non_streaming") as mem_log:
        start_time = time.time()

        baseline_df = compute_features(
            df_full, available=available_indicators, volatility_normalize=False
        )

        end_time = time.time()
        duration = end_time - start_time

        mem_log.log_dataframe_memory(baseline_df, "Baseline DataFrame")

    non_streaming_memory = process.memory_info().rss / 1024 / 1024  # MB
    non_streaming_increase = non_streaming_memory - initial_memory

    print(f"   ⏱️  Time: {duration:.2f} seconds")
    print(f"   💾 Memory increase: {non_streaming_increase:.2f} MB")
    print(f"   📊 Result shape: {baseline_df.shape}")
    print(f"   🚀 Rows/second: {n_rows / duration:.0f}")

    # Clean up
    force_cleanup(baseline_df, df_full)
    gc.collect()

    # Demo 2: Streaming approach
    print("\n2️⃣ Streaming approach (optimized)...")
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
        start_time = time.time()

        streaming_results = []
        for i, result_chunk in enumerate(
            process_chunks(
                chunk_iterator(),
                symbol="DEMO",
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
                f"   📦 Chunk {i+1}: {current_memory:.2f} MB, shape: {result_chunk.shape}"
            )

            # Clean up after each chunk
            force_cleanup(result_chunk)
            gc.collect()

        end_time = time.time()
        duration = end_time - start_time

    streaming_memory_end = process.memory_info().rss / 1024 / 1024  # MB
    streaming_increase = streaming_memory_end - streaming_memory_start
    streaming_peak_increase = max_streaming_memory - streaming_memory_start

    print(f"   ⏱️  Time: {duration:.2f} seconds")
    print(f"   💾 Memory increase: {streaming_increase:.2f} MB")
    print(f"   📈 Peak memory increase: {streaming_peak_increase:.2f} MB")
    print(f"   🚀 Rows/second: {n_rows / duration:.0f}")

    # Demo 3: Results comparison
    print("\n3️⃣ Results comparison...")

    # Combine streaming results
    if streaming_results:
        combined_df = pd.concat(streaming_results, ignore_index=True)
        print(f"   📊 Combined result shape: {combined_df.shape}")
        print(f"   📋 Columns: {list(combined_df.columns)}")

        # Show sample data
        print("   🔍 Sample data (first 3 rows):")
        sample_cols = ["hlc3", "ema_8", "sma_20", "rsi_14"]
        available_sample_cols = [
            col for col in sample_cols if col in combined_df.columns
        ]
        if available_sample_cols:
            print(combined_df[available_sample_cols].head(3).to_string())

    # Demo 4: Performance metrics
    print("\n4️⃣ Performance metrics...")

    memory_improvement = non_streaming_increase - streaming_increase
    peak_improvement = non_streaming_increase - streaming_peak_increase
    speedup = (n_rows / duration) / (n_rows / (end_time - start_time))

    print(f"   💾 Memory improvement: {memory_improvement:.2f} MB")
    print(f"   📈 Peak memory improvement: {peak_improvement:.2f} MB")
    print(f"   🚀 Performance speedup: {speedup:.2f}x")

    # Demo 5: Memory efficiency
    print("\n5️⃣ Memory efficiency...")

    if streaming_increase < non_streaming_increase:
        print("   ✅ Streaming uses less memory!")
    else:
        print("   ⚠️  Streaming uses more memory (unexpected)")

    if streaming_peak_increase < non_streaming_increase:
        print("   ✅ Streaming has lower peak memory!")
    else:
        print("   ⚠️  Streaming has higher peak memory (unexpected)")

    if speedup > 0.8:
        print("   ✅ Streaming performance is acceptable!")
    else:
        print("   ⚠️  Streaming is slower (expected due to overhead)")

    # Demo 6: Configuration
    print("\n6️⃣ Configuration...")

    print(f"   🔧 Chunk size: {streaming_config.CHUNKSIZE}")
    print(f"   📏 Max lookback: {streaming_config.MAX_LOOKBACK}")
    print(f"   🔄 Overlap size: {streaming_config.OVERLAP_SIZE}")
    print(f"   🗑️  Force GC after chunk: {streaming_config.FORCE_GC_AFTER_CHUNK}")
    print(
        f"   🧹 Clear intermediate objects: {streaming_config.CLEAR_INTERMEDIATE_OBJECTS}"
    )

    # Demo 7: Strategy lookbacks
    print("\n7️⃣ Strategy lookbacks...")

    max_lookback = get_max_lookback_for_strategies(list(available_indicators))
    print(
        f"   📏 Max lookback for {len(available_indicators)} strategies: {max_lookback}"
    )

    for strategy in sorted(available_indicators):
        from src.features.strategy import max_lookback as get_lookback

        lookback = get_lookback(strategy)
        print(f"   📊 {strategy}: {lookback} periods")

    print("\n🎉 Demo completed successfully!")
    print("=" * 50)

    return {
        "non_streaming_increase": non_streaming_increase,
        "streaming_increase": streaming_increase,
        "streaming_peak_increase": streaming_peak_increase,
        "memory_improvement": memory_improvement,
        "peak_improvement": peak_improvement,
        "speedup": speedup,
    }


def demo_parquet_operations():
    """Demonstrate parquet file operations."""
    print("\n📁 Parquet Operations Demo")
    print("=" * 40)

    # Create demo data
    df = create_demo_data(2000)

    # Demo parquet save
    print("💾 Saving to parquet file...")

    with memory_monitor("parquet_save") as mem_log:
        result = compute_and_dump_parquet(
            df_ohlcv=df,
            symbol="DEMO",
            timeframe="1H",
            output_path="demo_output.parquet",
            volatility_normalize=False,
        )

        mem_log.log_dataframe_memory(df, "Input DataFrame")

    print(f"   📄 File: {result['output_path']}")
    print(f"   📊 Size: {result['file_size_mb']:.2f} MB")
    print(f"   📈 Rows: {result['result_rows']}")
    print(f"   🔧 Features: {result['feature_count']}")

    # Demo parquet validation
    print("\n🔍 Validating parquet file...")

    from src.features.calc import validate_parquet_file

    validation = validate_parquet_file("demo_output.parquet")

    print(f"   ✅ Rows: {validation['rows']}")
    print(f"   ✅ Features: {validation['feature_count']}")
    print(f"   ✅ File size: {validation['file_size_mb']:.2f} MB")

    # Clean up
    if Path("demo_output.parquet").exists():
        Path("demo_output.parquet").unlink()
        print("   🗑️  Cleaned up demo file")

    print("✅ Parquet operations demo completed!")


def main():
    """Main demo function."""
    print("🎬 Memory Optimization Features Demo")
    print("=" * 60)

    try:
        # Demo 1: Memory optimization
        results = demo_memory_optimization()

        # Demo 2: Parquet operations
        demo_parquet_operations()

        # Summary
        print("\n📊 Demo Summary:")
        print(f"   💾 Memory improvement: {results['memory_improvement']:.2f} MB")
        print(f"   📈 Peak memory improvement: {results['peak_improvement']:.2f} MB")
        print(f"   🚀 Performance speedup: {results['speedup']:.2f}x")

        print("\n🎉 All demos completed successfully!")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
