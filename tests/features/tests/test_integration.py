"""
Integration tests for the features module.

Tests the complete workflow from OHLCV data to calculated features,
including validation, calculation, and normalization.
"""

import numpy as np
import pandas as pd
import pytest

from ..core import compute_features
from ..utils.utils import (
    assert_frames_close,
    calculate_feature_statistics,
    volatility_normalize_features,
)
from ..validation.feature_validator import validate_data_quality, validate_ohlcv_data


class TestFeaturesIntegration:
    """Test complete integration of the features module."""

    @pytest.fixture
    def sample_ohlcv_data(self):
        """Create comprehensive sample OHLCV data for testing."""
        dates = pd.date_range("2023-01-01", periods=200, freq="1H")
        np.random.seed(42)

        # Generate realistic price data with trends and volatility
        base_price = 100.0
        prices = [base_price]

        # Add some trend and volatility
        for i in range(1, 200):
            # Add trend component
            trend = 0.0001 * i  # Small upward trend

            # Add volatility component
            volatility = 0.02 * (1 + 0.5 * np.sin(i * 0.1))  # Varying volatility

            # Generate return
            ret = np.random.normal(trend, volatility)
            new_price = prices[-1] * (1 + ret)
            prices.append(new_price)

        prices = np.array(prices)

        # Generate OHLCV data
        data = {
            "ts": [int(d.timestamp()) for d in dates],
            "open": prices * (1 + np.random.normal(0, 0.005, 200)),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.01, 200))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.01, 200))),
            "close": prices,
            "volume": np.random.uniform(1000, 10000, 200),
        }

        df = pd.DataFrame(data)

        # Ensure OHLC relationships
        df["high"] = df[["open", "high", "close"]].max(axis=1)
        df["low"] = df[["open", "low", "close"]].min(axis=1)

        return df

    def test_complete_workflow(self, sample_ohlcv_data):
        """Test complete workflow from validation to feature calculation."""
        # Step 1: Validate input data
        validate_ohlcv_data(sample_ohlcv_data)

        # Step 2: Check data quality
        quality_result = validate_data_quality(sample_ohlcv_data)
        assert quality_result.is_valid, f"Data quality issues: {quality_result.errors}"

        # Step 3: Calculate features
        features = compute_features(
            sample_ohlcv_data,
            specs=["rsi_14", "atr_14", "ema_12", "ema_26", "macd", "obv"],
            volatility_normalize=False,
        )

        # Step 4: Validate output
        assert isinstance(features, pd.DataFrame)
        assert len(features) == len(sample_ohlcv_data)

        # Check that all requested features are present
        expected_features = ["rsi_14", "atr_14", "ema_12", "ema_26", "macd", "obv"]
        for feature in expected_features:
            assert feature in features.columns
            assert not features[feature].isna().all()  # Should have some valid values

        # Step 5: Calculate statistics
        stats = calculate_feature_statistics(features)
        assert isinstance(stats, pd.DataFrame)
        assert len(stats) > 0

        # Step 6: Apply normalization
        normalized_features = volatility_normalize_features(
            features, window=20, method="rolling_std"
        )

        assert isinstance(normalized_features, pd.DataFrame)
        assert len(normalized_features) == len(features)

        # Normalized features should be different from original
        for feature in expected_features:
            if feature in normalized_features.columns:
                original_values = features[feature].dropna()
                normalized_values = normalized_features[feature].dropna()

                if len(original_values) > 0 and len(normalized_values) > 0:
                    # Values should be different after normalization
                    min_len = min(len(original_values), len(normalized_values))
                    original_subset = original_values.iloc[-min_len:]
                    normalized_subset = normalized_values.iloc[-min_len:]

                    # Check that values are different (not identical)
                    assert not np.allclose(
                        original_subset.values, normalized_subset.values, rtol=1e-10
                    ), f"Feature {feature} values should be different after normalization"

    def test_phase_2_required_features(self, sample_ohlcv_data):
        """Test that all required features for Phase 2 are available and working."""
        # Required features for Phase 2
        required_features = [
            "atr_14",  # ATR
            "rsi_14",  # RSI
            "ema_12",  # EMA
            "ema_26",  # EMA
            "macd",  # MACD
            "macd_signal",  # MACD Signal
            "macd_histogram",  # MACD Histogram
            "obv",  # OBV
            "parkinson_vol",  # Parkinson Volatility
            "vwap",  # Rolling VWAP
        ]

        # Calculate all required features
        features = compute_features(
            sample_ohlcv_data, specs=required_features, volatility_normalize=False
        )

        # Verify all features are present and have valid values
        for feature in required_features:
            assert feature in features.columns, f"Required feature {feature} not found"

            feature_values = features[feature].dropna()
            assert len(feature_values) > 0, f"Feature {feature} has no valid values"

            # Check for reasonable bounds
            if feature == "rsi_14":
                assert feature_values.min() >= 0, "RSI should be >= 0"
                assert feature_values.max() <= 100, "RSI should be <= 100"
            elif feature in ["atr_14", "parkinson_vol"]:
                assert feature_values.min() >= 0, f"{feature} should be >= 0"
            elif feature in ["ema_12", "ema_26"]:
                assert (
                    feature_values.min() >= 0
                ), f"{feature} should be >= 0 for positive prices"

    def test_online_offline_parity(self, sample_ohlcv_data):
        """Online и офлайн расчёты дают одинаковые результаты в пределах ε."""
        # Simulate online calculation (one bar at a time)
        online_results = []

        for i in range(50, len(sample_ohlcv_data)):
            # Get data up to current point (simulating online scenario)
            online_data = sample_ohlcv_data.iloc[: i + 1].copy()

            # Calculate features
            online_features = compute_features(
                online_data,
                specs=["rsi_14", "atr_14", "ema_12"],
                volatility_normalize=False,
            )

            # Store the last row (current bar)
            online_results.append(online_features.iloc[-1])

        # Simulate offline calculation (all data at once)
        offline_features = compute_features(
            sample_ohlcv_data,
            specs=["rsi_14", "atr_14", "ema_12"],
            volatility_normalize=False,
        )

        # Сравниваем результаты векторно с допуском ε
        offline_subset = offline_features.iloc[
            50 : 50 + len(online_results)
        ].reset_index(drop=True)
        online_df = pd.DataFrame(online_results).reset_index(drop=True)
        assert_frames_close(
            online_df,
            offline_subset,
            columns=["rsi_14", "atr_14", "ema_12"],
            rtol=1e-10,
            atol=1e-12,
        )

    def test_error_handling(self, sample_ohlcv_data):
        """Test error handling in the features module."""
        # Test with invalid data
        invalid_data = sample_ohlcv_data.copy()
        invalid_data.loc[0, "high"] = -1  # Invalid OHLC relationship

        with pytest.raises(Exception):
            compute_features(invalid_data, specs=["rsi_14"])

        # Test with missing required columns
        missing_data = sample_ohlcv_data.drop(columns=["volume"])

        with pytest.raises(Exception):
            compute_features(missing_data, specs=["obv"])  # OBV requires volume

        # Test with non-existent features
        with pytest.raises(Exception):
            compute_features(sample_ohlcv_data, specs=["non_existent_feature"])

    def test_performance_benchmark(self, sample_ohlcv_data):
        """Test performance benchmarks for the features module."""
        import time

        # Benchmark single feature calculation
        start_time = time.time()
        compute_features(
            sample_ohlcv_data, specs=["rsi_14"], volatility_normalize=False
        )
        single_feature_time = time.time() - start_time

        # Benchmark multiple features
        start_time = time.time()
        compute_features(
            sample_ohlcv_data,
            specs=["rsi_14", "atr_14", "ema_12", "ema_26", "macd", "obv"],
            volatility_normalize=False,
        )
        multiple_features_time = time.time() - start_time

        # Benchmark with normalization
        start_time = time.time()
        compute_features(
            sample_ohlcv_data,
            specs=["rsi_14", "atr_14", "ema_12"],
            volatility_normalize=True,
            normalize_window=20,
        )
        normalized_time = time.time() - start_time

        # Performance assertions (adjust thresholds as needed)
        assert (
            single_feature_time < 1.0
        ), f"Single feature calculation too slow: {single_feature_time:.2f}s"
        assert (
            multiple_features_time < 2.0
        ), f"Multiple features calculation too slow: {multiple_features_time:.2f}s"
        assert (
            normalized_time < 2.0
        ), f"Normalized calculation too slow: {normalized_time:.2f}s"

        # Multiple features should not be much slower than single feature
        assert (
            multiple_features_time < single_feature_time * 3
        ), f"Multiple features scaling poorly: {multiple_features_time:.2f}s vs {single_feature_time:.2f}s"

    def test_memory_usage(self, sample_ohlcv_data):
        """Test memory usage of feature calculations."""
        import gc
        import os

        import psutil

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Calculate features
        features = compute_features(
            sample_ohlcv_data,
            specs=["rsi_14", "atr_14", "ema_12", "ema_26", "macd", "obv"],
            volatility_normalize=True,
        )

        # Get final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 100MB for 200 rows)
        assert (
            memory_increase < 100
        ), f"Memory usage too high: {memory_increase:.1f}MB increase"

        # Clean up
        del features
        gc.collect()

        # Check memory cleanup
        cleanup_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_cleanup = final_memory - cleanup_memory

        # RSS can stay flat after object deletion on some platforms/allocators.
        # The important part is that cleanup does not continue growing memory.
        assert memory_cleanup >= -1.0, "Memory increased after cleanup"
