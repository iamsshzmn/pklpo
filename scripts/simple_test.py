#!/usr/bin/env python3
"""
Simple test for features module improvements.
"""

import os
import sys
from datetime import UTC, datetime

import numpy as np
import pandas as pd

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from src.features.gate_validation import validate_data_gate
from src.features.metrics import calculate_fill_rates, calculate_quality_score
from src.features.time_utils import (
    normalize_timestamp_to_milliseconds,
    strict_timestamp_validation,
)


def create_test_data(rows: int = 100) -> pd.DataFrame:
    """Create test OHLCV data."""
    # Create timestamps in milliseconds
    base_time = int(datetime.now(UTC).timestamp() * 1000)
    timestamps = [base_time + i * 60000 for i in range(rows)]  # 1 minute intervals

    # Create OHLCV data
    np.random.seed(42)
    base_price = 100.0

    data = []
    for i, ts in enumerate(timestamps):
        price_change = np.random.normal(0, 0.5)
        base_price += price_change

        open_price = base_price
        high_price = base_price + abs(np.random.normal(0, 0.2))
        low_price = base_price - abs(np.random.normal(0, 0.2))
        close_price = base_price + np.random.normal(0, 0.1)
        volume = np.random.randint(1000, 10000)

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

    # Test milliseconds timestamp
    result = normalize_timestamp_to_milliseconds(1640995200000)
    print(f"  Milliseconds timestamp: {result}")
    assert isinstance(result, int) and result > 1000000000000
    print("  OK: Milliseconds timestamp handled correctly")

    # Test seconds timestamp (should be converted to ms)
    result = normalize_timestamp_to_milliseconds(1640995200)
    print(f"  Seconds timestamp converted: {result}")
    assert isinstance(result, int) and result > 1000000000000
    print("  OK: Seconds timestamp converted to milliseconds")

    print()


def test_timestamp_validation():
    """Test strict timestamp validation."""
    print("Testing timestamp validation...")

    # Test valid data
    valid_df = create_test_data(50)
    validation_result = strict_timestamp_validation(valid_df)
    print(f"  Valid data: {validation_result['valid']}")
    assert validation_result["valid"] == True
    print("  OK: Valid data passed validation")

    # Test invalid data (duplicate timestamps)
    invalid_df = valid_df.copy()
    invalid_df.loc[10, "ts"] = invalid_df.loc[5, "ts"]  # Create duplicate
    validation_result = strict_timestamp_validation(invalid_df)
    print(f"  Invalid data (duplicates): {validation_result['valid']}")
    assert validation_result["valid"] == False
    print("  OK: Duplicate timestamps detected")

    print()


def test_gate_validation():
    """Test gate validation functionality."""
    print("Testing gate validation...")

    # Test valid data
    valid_df = create_test_data(100)
    valid_df["hlc3"] = (valid_df["high"] + valid_df["low"] + valid_df["close"]) / 3
    valid_df["ema_8"] = valid_df["close"].ewm(span=8).mean()
    valid_df["rsi_14"] = 50.0

    feature_groups = {
        "overlap": ["hlc3"],
        "moving_averages": ["ema_8"],
        "oscillators": ["rsi_14"],
    }

    is_valid, result = validate_data_gate(valid_df, feature_groups)
    print(f"  Valid data: {is_valid}")
    assert is_valid == True
    print("  OK: Valid data passed gate validation")

    # Test invalid data (too few rows)
    invalid_df = valid_df.head(5)  # Only 5 rows
    is_valid, result = validate_data_gate(invalid_df, feature_groups)
    print(f"  Invalid data (too few rows): {is_valid}")
    assert is_valid == False
    print("  OK: Insufficient rows detected")

    print()


def test_metrics_collection():
    """Test metrics collection functionality."""
    print("Testing metrics collection...")

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
    print(f"  Fill rates: {fill_rates}")
    assert all(
        rate > 0.9 for rate in fill_rates.values()
    )  # Should be high for good data
    print("  OK: Fill rates calculated correctly")

    # Test quality score calculation
    nan_ratio, outlier_ratio, quality_score = calculate_quality_score(df)
    print("  Quality metrics:")
    print(f"    NaN ratio: {nan_ratio:.2%}")
    print(f"    Outlier ratio: {outlier_ratio:.2%}")
    print(f"    Quality score: {quality_score:.2f}")
    assert quality_score > 0.8  # Should be high for good data
    print("  OK: Quality metrics calculated correctly")

    print()


def main():
    """Run all tests."""
    print("Testing Features Module Improvements")
    print("=" * 50)

    test_timestamp_standardization()
    test_timestamp_validation()
    test_gate_validation()
    test_metrics_collection()

    print("All tests completed successfully!")


if __name__ == "__main__":
    main()
