#!/usr/bin/env python3
"""
Test script for features module improvements.

This script tests the new functionality implemented according to the plan:
- Timestamp standardization (UTC milliseconds)
- Gate validation
- Metrics collection
"""

import os
import sys
from datetime import UTC, datetime

import numpy as np
import pandas as pd

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from src.features.core import compute_features
from src.features.gate_validation import validate_data_gate
from src.features.metrics import (
    calculate_fill_rates,
    calculate_quality_score,
    get_metrics_collector,
)
from src.features.time_utils import (
    get_timestamp_info,
    normalize_timestamp_to_milliseconds,
    strict_timestamp_validation,
)


def create_test_data(rows: int = 100, with_issues: bool = False) -> pd.DataFrame:
    """Create test OHLCV data."""
    # Create timestamps in milliseconds (as required by plan)
    base_time = int(datetime.now(UTC).timestamp() * 1000)
    timestamps = [base_time + i * 60000 for i in range(rows)]  # 1 minute intervals

    # Create OHLCV data
    np.random.seed(42)  # For reproducible results
    base_price = 100.0

    data = []
    for i, ts in enumerate(timestamps):
        # Simulate price movement
        price_change = np.random.normal(0, 0.5)
        base_price += price_change

        # OHLCV
        open_price = base_price
        high_price = base_price + abs(np.random.normal(0, 0.2))
        low_price = base_price - abs(np.random.normal(0, 0.2))
        close_price = base_price + np.random.normal(0, 0.1)
        volume = np.random.randint(1000, 10000)

        # Introduce issues if requested
        if with_issues and i > 50:
            if i % 10 == 0:
                close_price = np.nan  # NaN values
            elif i % 15 == 0:
                close_price = np.inf  # Infinite values

        data.append(
            {
                "ts": ts,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
            }
        )

    return pd.DataFrame(data)


def test_timestamp_standardization():
    """Test timestamp standardization functionality."""
    print("Testing timestamp standardization...")

    # Test various timestamp formats
    test_cases = [
        # (input, expected_type, description)
        (1640995200000, int, "Milliseconds timestamp"),
        (1640995200, int, "Seconds timestamp (should be converted to ms)"),
        ("2022-01-01 00:00:00", int, "String timestamp"),
        (pd.Timestamp("2022-01-01 00:00:00", tz="UTC"), int, "Pandas timestamp"),
    ]

    for input_val, expected_type, description in test_cases:
        try:
            result = normalize_timestamp_to_milliseconds(input_val)
            print(
                f"  OK {description}: {input_val} -> {result} ({type(result).__name__})"
            )

            # Verify it's in milliseconds range
            if isinstance(result, int) and result > 1000000000000:
                print("    OK Timestamp is in milliseconds range")
            else:
                print("    ERROR Timestamp appears to be in wrong format")

        except Exception as e:
            print(f"  ERROR {description}: Error - {e}")

    print()


def test_timestamp_validation():
    """Test strict timestamp validation."""
    print("Testing timestamp validation...")

    # Test valid data
    valid_df = create_test_data(50)
    validation_result = strict_timestamp_validation(valid_df)
    print(f"  OK Valid data: {validation_result['valid']}")
    print(f"    Stats: {validation_result['stats']}")

    # Test invalid data (duplicate timestamps)
    invalid_df = valid_df.copy()
    invalid_df.loc[10, "ts"] = invalid_df.loc[5, "ts"]  # Create duplicate
    validation_result = strict_timestamp_validation(invalid_df)
    print(f"  ERROR Invalid data (duplicates): {validation_result['valid']}")
    print(f"    Errors: {validation_result['errors']}")

    # Test invalid data (seconds instead of milliseconds)
    invalid_df2 = valid_df.copy()
    invalid_df2["ts"] = invalid_df2["ts"] // 1000  # Convert to seconds
    validation_result = strict_timestamp_validation(invalid_df2)
    print(f"  ERROR Invalid data (seconds): {validation_result['valid']}")
    print(f"    Errors: {validation_result['errors']}")

    print()


def test_gate_validation():
    """Test gate validation functionality."""
    print("Testing gate validation...")

    # Test valid data
    valid_df = create_test_data(100)
    # Add some features
    valid_df["hlc3"] = (valid_df["high"] + valid_df["low"] + valid_df["close"]) / 3
    valid_df["ema_8"] = valid_df["close"].ewm(span=8).mean()
    valid_df["rsi_14"] = 50.0  # Mock RSI

    feature_groups = {
        "overlap": ["hlc3"],
        "moving_averages": ["ema_8"],
        "oscillators": ["rsi_14"],
    }

    is_valid, result = validate_data_gate(valid_df, feature_groups)
    print(f"  OK Valid data: {is_valid}")
    print(f"    Overall quality: {result['stats']['overall_quality']}")

    # Test invalid data (too few rows)
    invalid_df = valid_df.head(5)  # Only 5 rows
    is_valid, result = validate_data_gate(invalid_df, feature_groups)
    print(f"  ERROR Invalid data (too few rows): {is_valid}")
    print(f"    Errors: {result['errors']}")

    # Test invalid data (low fill rate)
    invalid_df2 = valid_df.copy()
    invalid_df2["hlc3"] = np.nan  # All NaN
    is_valid, result = validate_data_gate(invalid_df2, feature_groups)
    print(f"  ERROR Invalid data (low fill rate): {is_valid}")
    print(f"    Errors: {result['errors']}")

    print()


def test_metrics_collection():
    """Test metrics collection functionality."""
    print("🧪 Testing metrics collection...")

    # Create test data with features
    df = create_test_data(100)
    df["hlc3"] = (df["high"] + df["low"] + df["close"]) / 3
    df["ema_8"] = df["close"].ewm(span=8).mean()
    df["rsi_14"] = 50.0

    # Test fill rate calculation
    feature_groups = {
        "overlap": ["hlc3"],
        "moving_averages": ["ema_8"],
        "oscillators": ["rsi_14"],
    }

    fill_rates = calculate_fill_rates(df, feature_groups)
    print(f"  ✅ Fill rates: {fill_rates}")

    # Test quality score calculation
    nan_ratio, outlier_ratio, quality_score = calculate_quality_score(df)
    print("  ✅ Quality metrics:")
    print(f"    NaN ratio: {nan_ratio:.2%}")
    print(f"    Outlier ratio: {outlier_ratio:.2%}")
    print(f"    Quality score: {quality_score:.2f}")

    # Test metrics collector
    collector = get_metrics_collector()
    collector.start_calculation("BTC-USDT", "1h", 3)
    collector.record_rows_written(100)
    collector.record_rows_last_24h(24)

    for group_name, fill_rate in fill_rates.items():
        collector.record_fill_rate(group_name, fill_rate)

    collector.record_quality_metrics(nan_ratio, outlier_ratio, quality_score)

    final_metrics = collector.finish_calculation()
    print("  ✅ Final metrics:")
    print(f"    Symbol: {final_metrics.symbol}")
    print(f"    Timeframe: {final_metrics.timeframe}")
    print(f"    Rows written: {final_metrics.rows_written}")
    print(f"    Quality score: {final_metrics.data_quality_score:.2f}")

    print()


def test_integrated_calculation():
    """Test integrated feature calculation with new functionality."""
    print("🧪 Testing integrated calculation...")

    try:
        # Create test data
        df = create_test_data(100)

        # Calculate features
        result_df = compute_features(
            df,
            specs=["hlc3", "ema_8", "rsi_14"],
            symbol="BTC-USDT",
            timeframe="1h",
            volatility_normalize=False,  # Disable for testing
        )

        print("  ✅ Calculation successful!")
        print(f"    Input rows: {len(df)}")
        print(f"    Output rows: {len(result_df)}")
        print(
            f"    Features calculated: {len([col for col in result_df.columns if col not in ['ts', 'open', 'high', 'low', 'close', 'volume']])}"
        )

        # Check timestamp format
        ts_info = get_timestamp_info(result_df)
        print(f"    Timestamp info: {ts_info}")

        # Check if timestamps are in milliseconds
        if ts_info["min"] and ts_info["min"] > 1000000000000:
            print("    ✅ Timestamps are in milliseconds format")
        else:
            print("    ❌ Timestamps are not in milliseconds format")

    except Exception as e:
        print(f"  ❌ Calculation failed: {e}")
        import traceback

        traceback.print_exc()

    print()


def main():
    """Run all tests."""
    print("🚀 Testing Features Module Improvements")
    print("=" * 50)

    test_timestamp_standardization()
    test_timestamp_validation()
    test_gate_validation()
    test_metrics_collection()
    test_integrated_calculation()

    print("✅ All tests completed!")


if __name__ == "__main__":
    main()
