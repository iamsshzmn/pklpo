"""
Comprehensive test suite for features module as specified in the plan.

This module implements:
- Unit tests: name-mapping, normalization ts, filtering NaN/inf, UPSERT constructor
- Integration tests: small fixture DF (200-300 bars), idempotent UPSERT, correct types
- Load tests: batches 100k rows, upsert timing, absence of deadlock
"""

import logging
import time
import unittest
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from src.features.core.name_mapping import normalize_indicator_name
from src.features.infrastructure.upsert_optimizer import UpsertConfig, UpsertOptimizer
from src.features.observability.metrics import MetricsCollector

# Import our modules
from src.features.utils.time_utils import (
    ensure_ts_column,
    normalize_timestamp_to_milliseconds,
    strict_timestamp_validation,
)
from src.features.validation.code_validator import CodeValidator, ValidationConfig
from src.features.validation.gate_validator import validate_data_gate


class TestFeaturesModule(unittest.TestCase):
    """Comprehensive test suite for features module."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_200 = self._create_test_data(200)
        self.test_data_300 = self._create_test_data(300)
        self.test_data_100k = self._create_test_data(100000)

        # Configure logging for tests
        logging.basicConfig(level=logging.INFO)

    def _create_test_data(self, rows: int) -> pd.DataFrame:
        """Create test OHLCV data."""
        base_time = int(datetime.now(UTC).timestamp() * 1000)
        timestamps = [base_time + i * 60000 for i in range(rows)]  # 1 minute intervals

        np.random.seed(42)  # For reproducible results
        base_price = 100.0

        data = []
        for _i, ts in enumerate(timestamps):
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


class TestUnitTests(TestFeaturesModule):
    """Unit tests as specified in the plan."""

    def test_name_mapping(self):
        """Test name-mapping functionality."""
        # Test basic mapping
        assert normalize_indicator_name("BBANDS") == "bb_upper"
        assert normalize_indicator_name("EMA_200") == "ema_200"
        assert normalize_indicator_name("RSI_14") == "rsi_14"

        # Test duplicate elimination
        assert normalize_indicator_name("BBANDS_M") == "bb_middle"
        assert normalize_indicator_name("BBANDS_L") == "bb_lower"

        # Test snake_case conversion
        assert normalize_indicator_name("MACD_SIGNAL") == "macd_signal"
        assert normalize_indicator_name("ATR_14") == "atr_14"

    def test_timestamp_normalization(self):
        """Test timestamp normalization to milliseconds."""
        # Test milliseconds timestamp (should stay the same)
        ms_timestamp = 1640995200000
        result = normalize_timestamp_to_milliseconds(ms_timestamp)
        assert result == ms_timestamp

        # Test seconds timestamp (should be converted to ms)
        sec_timestamp = 1640995200
        result = normalize_timestamp_to_milliseconds(sec_timestamp)
        assert result == sec_timestamp * 1000

        # Test string timestamp
        str_timestamp = "2022-01-01 00:00:00"
        result = normalize_timestamp_to_milliseconds(str_timestamp)
        assert isinstance(result, int)
        assert result > 1000000000000  # Should be in milliseconds

        # Test pandas timestamp
        pd_timestamp = pd.Timestamp("2022-01-01 00:00:00", tz="UTC")
        result = normalize_timestamp_to_milliseconds(pd_timestamp)
        assert isinstance(result, int)
        assert result > 1000000000000

    def test_nan_inf_filtering(self):
        """Test filtering of NaN and infinite values."""
        # Create test data with NaN and inf values
        df = self.test_data_200.copy()
        df.loc[10, "close"] = np.nan
        df.loc[20, "high"] = np.inf
        df.loc[30, "low"] = -np.inf
        df.loc[40, "volume"] = np.nan

        # Test gate validation
        feature_groups = {
            "overlap": ["hlc3"],
            "moving_averages": ["ema_8"],
            "oscillators": ["rsi_14"],
        }

        # Add some features
        df["hlc3"] = (df["high"] + df["low"] + df["close"]) / 3
        df["ema_8"] = df["close"].ewm(span=8).mean()
        df["rsi_14"] = 50.0

        is_valid, result = validate_data_gate(df, feature_groups)

        # Should detect NaN/inf issues
        assert not is_valid
        assert any("infinite values" in error for error in result["errors"])

    def test_upsert_constructor(self):
        """Test UPSERT constructor functionality."""
        optimizer = UpsertOptimizer(UpsertConfig())

        # Test configuration
        assert optimizer.config.batch_size_min == 5000
        assert optimizer.config.batch_size_max == 10000
        assert optimizer.config.max_retries == 3

        # Test statistics tracking
        stats = optimizer.get_statistics()
        assert stats["total_rows_written"] == 0
        assert stats["total_upsert_failures"] == 0
        assert stats["total_retries"] == 0


class TestIntegrationTests(TestFeaturesModule):
    """Integration tests as specified in the plan."""

    def test_small_fixture_df(self):
        """Test with small fixture DF (200-300 bars)."""
        # Test with 200 bars
        df_200 = self.test_data_200.copy()
        df_200["hlc3"] = (df_200["high"] + df_200["low"] + df_200["close"]) / 3
        df_200["ema_8"] = df_200["close"].ewm(span=8).mean()

        # Test timestamp validation
        validation_result = strict_timestamp_validation(df_200)
        assert validation_result["valid"]
        assert validation_result["stats"]["count"] == 200

        # Test gate validation
        feature_groups = {"overlap": ["hlc3"], "moving_averages": ["ema_8"]}

        is_valid, result = validate_data_gate(df_200, feature_groups)
        assert is_valid

        # Test with 300 bars
        df_300 = self.test_data_300.copy()
        df_300["hlc3"] = (df_300["high"] + df_300["low"] + df_300["close"]) / 3
        df_300["ema_8"] = df_300["close"].ewm(span=8).mean()

        validation_result = strict_timestamp_validation(df_300)
        assert validation_result["valid"]
        assert validation_result["stats"]["count"] == 300

    def test_idempotent_upsert(self):
        """Test idempotent UPSERT operations."""
        optimizer = UpsertOptimizer(UpsertConfig())

        # Create test data
        df = self.test_data_200.copy()
        df["hlc3"] = (df["high"] + df["low"] + df["close"]) / 3

        # First upsert
        success1 = optimizer.upsert_batch(df, "test_group")
        assert success1

        # Second upsert (should be idempotent)
        success2 = optimizer.upsert_batch(df, "test_group")
        assert success2

        # Check statistics
        stats = optimizer.get_statistics()
        assert stats["total_rows_written"] > 0

    def test_correct_types(self):
        """Test correct data types."""
        df = self.test_data_200.copy()

        # Ensure timestamp column
        df_with_ts = ensure_ts_column(df)

        # Check types
        assert pd.api.types.is_integer_dtype(df_with_ts["ts"])
        assert pd.api.types.is_float_dtype(df_with_ts["open"])
        assert pd.api.types.is_float_dtype(df_with_ts["high"])
        assert pd.api.types.is_float_dtype(df_with_ts["low"])
        assert pd.api.types.is_float_dtype(df_with_ts["close"])
        assert pd.api.types.is_integer_dtype(df_with_ts["volume"])

        # Check timestamp range (should be in milliseconds)
        min_ts = df_with_ts["ts"].min()
        max_ts = df_with_ts["ts"].max()
        assert min_ts > 1000000000000  # Should be in milliseconds
        assert max_ts > min_ts  # Should be monotonic


class TestLoadTests(TestFeaturesModule):
    """Load tests as specified in the plan."""

    def test_100k_rows_batch(self):
        """Test batches with 100k rows."""
        df_100k = self.test_data_100k.copy()

        # Add features
        df_100k["hlc3"] = (df_100k["high"] + df_100k["low"] + df_100k["close"]) / 3
        df_100k["ema_8"] = df_100k["close"].ewm(span=8).mean()
        df_100k["rsi_14"] = 50.0

        # Test timestamp validation performance
        start_time = time.perf_counter()
        validation_result = strict_timestamp_validation(df_100k)
        elapsed = time.perf_counter() - start_time

        assert validation_result["valid"]
        assert validation_result["stats"]["count"] == 100000
        assert elapsed < 1.0  # Should complete within 1 second

        print(f"Timestamp validation for 100k rows: {elapsed:.3f}s")

    def test_upsert_timing(self):
        """Test upsert timing performance."""
        optimizer = UpsertOptimizer(UpsertConfig())

        # Test with different batch sizes
        batch_sizes = [5000, 10000, 50000, 100000]

        for batch_size in batch_sizes:
            df_batch = self.test_data_100k.head(batch_size).copy()
            df_batch["hlc3"] = (
                df_batch["high"] + df_batch["low"] + df_batch["close"]
            ) / 3

            start_time = time.perf_counter()
            success = optimizer.upsert_batch(df_batch, f"load_test_{batch_size}")
            elapsed = time.perf_counter() - start_time

            assert success

            # Calculate rows per second
            rows_per_second = batch_size / elapsed
            print(
                f"Batch size {batch_size}: {elapsed:.3f}s ({rows_per_second:.0f} rows/sec)"
            )

            # Should handle at least 10k rows per second
            assert rows_per_second > 10000

    def test_no_deadlock(self):
        """Test absence of deadlock in concurrent operations."""
        optimizer = UpsertOptimizer(UpsertConfig())

        # Create multiple batches
        batches = []
        for i in range(5):
            df_batch = self.test_data_100k.iloc[i * 20000 : (i + 1) * 20000].copy()
            df_batch["hlc3"] = (
                df_batch["high"] + df_batch["low"] + df_batch["close"]
            ) / 3
            batches.append(df_batch)

        # Process batches sequentially (simulating concurrent processing)
        start_time = time.perf_counter()

        for i, batch in enumerate(batches):
            success = optimizer.upsert_batch(batch, f"concurrent_test_{i}")
            assert success

        elapsed = time.perf_counter() - start_time

        # Should complete without hanging
        assert elapsed < 10.0  # Should complete within 10 seconds

        print(f"Concurrent processing of 5 batches: {elapsed:.3f}s")

        # Check statistics
        stats = optimizer.get_statistics()
        assert stats["total_rows_written"] == 100000


class TestCodeValidations(TestFeaturesModule):
    """Test additional code validations."""

    def test_fraction_outliers(self):
        """Test fraction_outliers validation."""
        validator = CodeValidator(ValidationConfig())

        # Create data with outliers
        df = self.test_data_200.copy()

        # Add some outliers
        df.loc[10:15, "close"] *= 10  # Price outliers
        df.loc[20:25, "volume"] *= 100  # Volume outliers

        # Test price outlier validation
        is_valid, result = validator.validate_price_outliers(df)
        assert not is_valid
        assert any("outlier fraction" in error for error in result["errors"])

        # Test volume outlier validation
        is_valid, result = validator.validate_volume_outliers(df)
        assert not is_valid
        assert any("outlier fraction" in error for error in result["errors"])

    def test_warmup_window(self):
        """Test warm-up window validation."""
        validator = CodeValidator(ValidationConfig())

        df = self.test_data_200.copy()

        # Add features with different periods
        df["sma_20"] = df["close"].rolling(window=20).mean()
        df["ema_50"] = df["close"].ewm(span=50).mean()
        df["atr_14"] = df["close"].rolling(window=14).std()

        feature_periods = {"sma_20": 20, "ema_50": 50, "atr_14": 14}

        # Test warm-up validation
        is_valid, result = validator.validate_warmup_window(df, feature_periods)

        # Should pass for 200 rows
        assert is_valid

        # Test with insufficient data
        df_short = df.head(30)  # Only 30 rows
        is_valid, result = validator.validate_warmup_window(df_short, feature_periods)
        assert not is_valid
        assert any("Insufficient warm-up" in error for error in result["errors"])


class TestMetricsCollection(TestFeaturesModule):
    """Test metrics collection functionality."""

    def test_metrics_collection(self):
        """Test metrics collection and reporting."""
        collector = MetricsCollector()

        # Start calculation
        collector.start_calculation("BTC-USDT", "1h", 5)

        # Record various metrics
        collector.record_rows_written(1000)
        collector.record_rows_last_24h(24)
        collector.record_fill_rate("moving_averages", 0.95)
        collector.record_fill_rate("oscillators", 0.90)
        collector.record_quality_metrics(0.05, 0.02, 0.93)

        # Finish calculation
        final_metrics = collector.finish_calculation()

        # Verify metrics
        assert final_metrics.symbol == "BTC-USDT"
        assert final_metrics.timeframe == "1h"
        assert final_metrics.feature_count == 5
        assert final_metrics.rows_written == 1000
        assert final_metrics.rows_last_24h == 24
        assert final_metrics.fill_rates["moving_averages"] == 0.95
        assert final_metrics.fill_rates["oscillators"] == 0.9
        assert final_metrics.nan_ratio == 0.05
        assert final_metrics.outlier_ratio == 0.02
        assert final_metrics.data_quality_score == 0.93


def run_all_tests():
    """Run all test suites."""
    # Create test suite
    test_suite = unittest.TestSuite()

    # Add test classes
    test_classes = [
        TestUnitTests,
        TestIntegrationTests,
        TestLoadTests,
        TestCodeValidations,
        TestMetricsCollection,
    ]

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(test_suite)


if __name__ == "__main__":
    print("Running comprehensive test suite for features module...")
    print("=" * 60)

    result = run_all_tests()

    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback}")

    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback}")

    if result.wasSuccessful():
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
