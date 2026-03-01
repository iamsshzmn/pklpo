"""
Simple test runner for features module.

This script can be run to verify the basic functionality
without complex dependencies.
"""

import os
import sys
from datetime import UTC, datetime

import numpy as np
import pandas as pd

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def test_basic_functionality():
    """Test basic functionality of our modules."""
    print("Testing basic functionality...")

    try:
        # Test timestamp normalization
        from src.features.time_utils import normalize_timestamp_to_milliseconds

        # Test milliseconds timestamp
        result = normalize_timestamp_to_milliseconds(1640995200000)
        assert result == 1640995200000
        print("✅ Timestamp normalization: OK")

        # Test seconds timestamp
        result = normalize_timestamp_to_milliseconds(1640995200)
        assert result == 1640995200 * 1000
        print("✅ Seconds to milliseconds conversion: OK")

        # Test name mapping
        from src.features.name_mapping import normalize_indicator_name

        result = normalize_indicator_name("BBANDS")
        assert result == "bb_upper"
        print("✅ Name mapping: OK")

        # Test gate validation
        from src.features.gate_validation import validate_data_gate

        # Create test data
        df = pd.DataFrame(
            {
                "ts": [1640995200000, 1640995260000, 1640995320000],
                "open": [100.0, 101.0, 102.0],
                "high": [102.0, 103.0, 104.0],
                "low": [99.0, 100.0, 101.0],
                "close": [101.0, 102.0, 103.0],
                "volume": [1000, 1100, 1200],
                "hlc3": [100.7, 101.7, 102.7],
                "ema_8": [100.5, 101.5, 102.5],
            }
        )

        feature_groups = {"overlap": ["hlc3"], "moving_averages": ["ema_8"]}

        is_valid, result = validate_data_gate(df, feature_groups)
        assert is_valid == True
        print("✅ Gate validation: OK")

        # Test UPSERT optimizer
        from src.features.upsert_optimizer import UpsertConfig, UpsertOptimizer

        config = UpsertConfig()
        optimizer = UpsertOptimizer(config)

        assert config.batch_size_min == 5000
        assert config.max_retries == 3
        print("✅ UPSERT optimizer: OK")

        # Test code validations
        from src.features.code_validations import CodeValidator, ValidationConfig

        validator = CodeValidator(ValidationConfig())

        # Test price outlier validation
        is_valid, result = validator.validate_price_outliers(df)
        assert is_valid == True
        print("✅ Code validations: OK")

        # Test metrics
        from src.features.metrics import MetricsCollector

        collector = MetricsCollector()
        collector.start_calculation("BTC-USDT", "1h", 3)
        collector.record_rows_written(100)
        final_metrics = collector.finish_calculation()

        assert final_metrics.symbol == "BTC-USDT"
        assert final_metrics.rows_written == 100
        print("✅ Metrics collection: OK")

        print("\n🎉 All basic tests passed!")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_performance():
    """Test performance with larger datasets."""
    print("\nTesting performance...")

    try:
        from src.features.time_utils import strict_timestamp_validation

        # Create larger dataset
        base_time = int(datetime.now(UTC).timestamp() * 1000)
        timestamps = [base_time + i * 60000 for i in range(10000)]

        df_large = pd.DataFrame(
            {
                "ts": timestamps,
                "open": np.random.uniform(99, 101, 10000),
                "high": np.random.uniform(100, 102, 10000),
                "low": np.random.uniform(98, 100, 10000),
                "close": np.random.uniform(99.5, 100.5, 10000),
                "volume": np.random.randint(1000, 10000, 10000),
            }
        )

        # Test timestamp validation performance
        import time

        start_time = time.perf_counter()
        validation_result = strict_timestamp_validation(df_large)
        elapsed = time.perf_counter() - start_time

        assert validation_result["valid"] == True
        assert elapsed < 1.0  # Should complete within 1 second

        print(f"✅ Performance test: {elapsed:.3f}s for 10k rows")
        return True

    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("Features Module Test Suite")
    print("=" * 40)

    # Run basic functionality tests
    basic_success = test_basic_functionality()

    # Run performance tests
    perf_success = test_performance()

    print("\n" + "=" * 40)
    if basic_success and perf_success:
        print("🎉 All tests passed successfully!")
        print("The features module is working correctly.")
    else:
        print("❌ Some tests failed!")
        print("Please check the error messages above.")

    return basic_success and perf_success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
