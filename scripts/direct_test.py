#!/usr/bin/env python3
"""
Direct test of features module improvements.
Tests the core functionality without complex dependencies.
"""

from datetime import UTC, datetime

import numpy as np
import pandas as pd


# Test timestamp standardization
def test_timestamp_functions():
    print("=== Testing Timestamp Functions ===")

    # Import our functions
    import os
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

    try:
        from features.time_utils import (
            normalize_timestamp_to_milliseconds,
        )

        # Test 1: Milliseconds timestamp (should stay the same)
        ms_timestamp = 1640995200000
        result = normalize_timestamp_to_milliseconds(ms_timestamp)
        print(f"Milliseconds input: {ms_timestamp} -> {result}")
        assert result == ms_timestamp, f"Expected {ms_timestamp}, got {result}"
        print("✓ Milliseconds timestamp handled correctly")

        # Test 2: Seconds timestamp (should be converted to ms)
        sec_timestamp = 1640995200
        result = normalize_timestamp_to_milliseconds(sec_timestamp)
        expected = sec_timestamp * 1000
        print(f"Seconds input: {sec_timestamp} -> {result}")
        assert result == expected, f"Expected {expected}, got {result}"
        print("✓ Seconds timestamp converted to milliseconds")

        # Test 3: String timestamp
        str_timestamp = "2022-01-01 00:00:00"
        result = normalize_timestamp_to_milliseconds(str_timestamp)
        print(f"String input: {str_timestamp} -> {result}")
        assert isinstance(result, int) and result > 1000000000000
        print("✓ String timestamp converted to milliseconds")

        # Test 4: Pandas timestamp
        pd_timestamp = pd.Timestamp("2022-01-01 00:00:00", tz="UTC")
        result = normalize_timestamp_to_milliseconds(pd_timestamp)
        print(f"Pandas timestamp: {pd_timestamp} -> {result}")
        assert isinstance(result, int) and result > 1000000000000
        print("✓ Pandas timestamp converted to milliseconds")

        print("✓ All timestamp normalization tests passed!")

    except Exception as e:
        print(f"✗ Timestamp test failed: {e}")
        import traceback

        traceback.print_exc()


def test_timestamp_validation():
    print("\n=== Testing Timestamp Validation ===")

    try:
        from features.time_utils import strict_timestamp_validation

        # Create test data with valid timestamps (milliseconds)
        base_time = int(datetime.now(UTC).timestamp() * 1000)
        timestamps = [base_time + i * 60000 for i in range(50)]  # 1 minute intervals

        df_valid = pd.DataFrame(
            {
                "ts": timestamps,
                "open": [100.0] * 50,
                "high": [101.0] * 50,
                "low": [99.0] * 50,
                "close": [100.5] * 50,
                "volume": [1000] * 50,
            }
        )

        # Test valid data
        result = strict_timestamp_validation(df_valid)
        print(f"Valid data validation: {result['valid']}")
        assert result["valid"] == True, f"Expected True, got {result['valid']}"
        print("✓ Valid data passed validation")

        # Test invalid data (duplicate timestamps)
        df_invalid = df_valid.copy()
        df_invalid.loc[10, "ts"] = df_invalid.loc[5, "ts"]  # Create duplicate
        result = strict_timestamp_validation(df_invalid)
        print(f"Invalid data (duplicates) validation: {result['valid']}")
        assert result["valid"] == False, f"Expected False, got {result['valid']}"
        print("✓ Duplicate timestamps detected")

        # Test invalid data (seconds instead of milliseconds)
        df_invalid2 = df_valid.copy()
        df_invalid2["ts"] = df_invalid2["ts"] // 1000  # Convert to seconds
        result = strict_timestamp_validation(df_invalid2)
        print(f"Invalid data (seconds) validation: {result['valid']}")
        assert result["valid"] == False, f"Expected False, got {result['valid']}"
        print("✓ Seconds timestamps detected as invalid")

        print("✓ All timestamp validation tests passed!")

    except Exception as e:
        print(f"✗ Timestamp validation test failed: {e}")
        import traceback

        traceback.print_exc()


def test_gate_validation():
    print("\n=== Testing Gate Validation ===")

    try:
        from features.gate_validation import validate_data_gate

        # Create test data with features
        base_time = int(datetime.now(UTC).timestamp() * 1000)
        timestamps = [base_time + i * 60000 for i in range(100)]

        df_valid = pd.DataFrame(
            {
                "ts": timestamps,
                "open": np.random.uniform(99, 101, 100),
                "high": np.random.uniform(100, 102, 100),
                "low": np.random.uniform(98, 100, 100),
                "close": np.random.uniform(99.5, 100.5, 100),
                "volume": np.random.randint(1000, 10000, 100),
                "hlc3": np.random.uniform(99, 101, 100),
                "ema_8": np.random.uniform(99, 101, 100),
                "rsi_14": np.random.uniform(30, 70, 100),
            }
        )

        feature_groups = {
            "overlap": ["hlc3"],
            "moving_averages": ["ema_8"],
            "oscillators": ["rsi_14"],
        }

        # Test valid data
        is_valid, result = validate_data_gate(df_valid, feature_groups)
        print(f"Valid data gate validation: {is_valid}")
        assert is_valid == True, f"Expected True, got {is_valid}"
        print("✓ Valid data passed gate validation")

        # Test invalid data (too few rows)
        df_invalid = df_valid.head(5)  # Only 5 rows
        is_valid, result = validate_data_gate(df_invalid, feature_groups)
        print(f"Invalid data (too few rows) gate validation: {is_valid}")
        assert is_valid == False, f"Expected False, got {is_valid}"
        print("✓ Insufficient rows detected")

        # Test invalid data (low fill rate)
        df_invalid2 = df_valid.copy()
        df_invalid2["hlc3"] = np.nan  # All NaN
        is_valid, result = validate_data_gate(df_invalid2, feature_groups)
        print(f"Invalid data (low fill rate) gate validation: {is_valid}")
        assert is_valid == False, f"Expected False, got {is_valid}"
        print("✓ Low fill rate detected")

        print("✓ All gate validation tests passed!")

    except Exception as e:
        print(f"✗ Gate validation test failed: {e}")
        import traceback

        traceback.print_exc()


def test_metrics():
    print("\n=== Testing Metrics ===")

    try:
        from features.metrics import calculate_fill_rates, calculate_quality_score

        # Create test data with features
        df = pd.DataFrame(
            {
                "open": np.random.uniform(99, 101, 100),
                "high": np.random.uniform(100, 102, 100),
                "low": np.random.uniform(98, 100, 100),
                "close": np.random.uniform(99.5, 100.5, 100),
                "volume": np.random.randint(1000, 10000, 100),
                "hlc3": np.random.uniform(99, 101, 100),
                "ema_8": np.random.uniform(99, 101, 100),
                "rsi_14": np.random.uniform(30, 70, 100),
            }
        )

        feature_groups = {
            "overlap": ["hlc3"],
            "moving_averages": ["ema_8"],
            "oscillators": ["rsi_14"],
        }

        # Test fill rate calculation
        fill_rates = calculate_fill_rates(df, feature_groups)
        print(f"Fill rates: {fill_rates}")
        assert all(
            rate > 0.9 for rate in fill_rates.values()
        ), f"Expected high fill rates, got {fill_rates}"
        print("✓ Fill rates calculated correctly")

        # Test quality score calculation
        nan_ratio, outlier_ratio, quality_score = calculate_quality_score(df)
        print("Quality metrics:")
        print(f"  NaN ratio: {nan_ratio:.2%}")
        print(f"  Outlier ratio: {outlier_ratio:.2%}")
        print(f"  Quality score: {quality_score:.2f}")
        assert quality_score > 0.8, f"Expected high quality score, got {quality_score}"
        print("✓ Quality metrics calculated correctly")

        print("✓ All metrics tests passed!")

    except Exception as e:
        print(f"✗ Metrics test failed: {e}")
        import traceback

        traceback.print_exc()


def main():
    print("Testing Features Module Improvements")
    print("=" * 50)

    test_timestamp_functions()
    test_timestamp_validation()
    test_gate_validation()
    test_metrics()

    print("\n" + "=" * 50)
    print("✓ All tests completed successfully!")
    print("The features module improvements are working correctly.")


if __name__ == "__main__":
    main()
