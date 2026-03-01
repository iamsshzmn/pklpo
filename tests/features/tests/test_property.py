"""
Property tests for the features module.

These tests verify important properties of feature calculations,
especially the absence of look-ahead bias and consistency between
online and offline modes.
"""

import numpy as np
import pandas as pd
import pytest

from ..core import compute_features
from ..utils.utils import ensure_no_lookahead


class TestNoLookaheadProperty:
    """Test that feature calculations don't have look-ahead bias."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for look-ahead testing."""
        dates = pd.date_range("2023-01-01", periods=50, freq="1H")
        np.random.seed(42)

        # Generate realistic price data
        base_price = 100.0
        returns = np.random.normal(0, 0.02, 50)
        prices = [base_price]

        for ret in returns[1:]:
            new_price = prices[-1] * (1 + ret)
            prices.append(new_price)

        prices = np.array(prices)

        data = {
            "ts": [int(d.timestamp()) for d in dates],
            "open": prices * (1 + np.random.normal(0, 0.005, 50)),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.01, 50))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.01, 50))),
            "close": prices,
            "volume": np.random.uniform(1000, 10000, 50),
        }

        df = pd.DataFrame(data)
        df["high"] = df[["open", "high", "close"]].max(axis=1)
        df["low"] = df[["open", "low", "close"]].min(axis=1)

        return df

    def test_no_lookahead_shift_property(self, sample_data):
        """
        Property test: shifting data by 1 bar should change metrics predictably,
        without any look-ahead bias.
        """
        # Calculate features on original data
        original_features = compute_features(
            sample_data,
            specs=["rsi_14", "atr_14", "ema_12", "macd"],
            volatility_normalize=False,
        )

        # Shift data by 1 bar (add new data point at the end)
        shifted_data = sample_data.copy()
        last_row = shifted_data.iloc[-1].copy()

        # Create new row with slightly different values
        new_row = last_row.copy()
        new_row["ts"] = last_row["ts"] + 3600  # 1 hour later
        new_row["open"] = last_row["close"] * 1.01
        new_row["high"] = last_row["close"] * 1.02
        new_row["low"] = last_row["close"] * 0.99
        new_row["close"] = last_row["close"] * 1.01
        new_row["volume"] = last_row["volume"] * 1.1

        shifted_data = pd.concat(
            [shifted_data, pd.DataFrame([new_row])], ignore_index=True
        )

        # Calculate features on shifted data
        shifted_features = compute_features(
            shifted_data,
            specs=["rsi_14", "atr_14", "ema_12", "macd"],
            volatility_normalize=False,
        )

        # Compare original data features with shifted data features (excluding the new row)
        feature_columns = ["rsi_14", "atr_14", "ema_12", "macd"]

        for feature in feature_columns:
            original_values = original_features[feature].dropna()
            shifted_values = (
                shifted_features[feature].iloc[:-1].dropna()
            )  # Exclude new row

            # Only compare where we have data in both
            min_len = min(len(original_values), len(shifted_values))
            if min_len > 0:
                original_subset = original_values.iloc[-min_len:]
                shifted_subset = shifted_values.iloc[-min_len:]

                # Values should be identical (within numerical precision)
                np.testing.assert_array_almost_equal(
                    original_subset.values,
                    shifted_subset.values,
                    decimal=10,
                    err_msg=f"Look-ahead bias detected in {feature}",
                )

    def test_no_lookahead_reverse_property(self, sample_data):
        """
        Property test: reversing the order of data should not produce
        the same feature values (which would indicate look-ahead bias).
        """
        # Calculate features on original data
        original_features = compute_features(
            sample_data,
            specs=["rsi_14", "atr_14", "ema_12"],
            volatility_normalize=False,
        )

        # Reverse the data order
        reversed_data = sample_data.iloc[::-1].reset_index(drop=True)

        # Calculate features on reversed data
        reversed_features = compute_features(
            reversed_data,
            specs=["rsi_14", "atr_14", "ema_12"],
            volatility_normalize=False,
        )

        # For features without look-ahead, the values should be different
        # when data order is reversed
        feature_columns = ["rsi_14", "atr_14", "ema_12"]

        for feature in feature_columns:
            original_values = original_features[feature].dropna()
            reversed_values = reversed_features[feature].dropna()

            if len(original_values) > 0 and len(reversed_values) > 0:
                # Values should be different (not identical)
                # Use correlation to check for similarity
                min_len = min(len(original_values), len(reversed_values))
                original_subset = original_values.iloc[-min_len:]
                reversed_subset = reversed_values.iloc[-min_len:]

                # For most features, correlation should not be 1.0
                # (except for some simple moving averages)
                if feature not in ["ema_12"]:  # EMA might be similar
                    correlation = np.corrcoef(
                        original_subset.values, reversed_subset.values
                    )[0, 1]
                    assert not np.isclose(
                        correlation, 1.0, atol=1e-6
                    ), f"Feature {feature} shows suspicious similarity when data is reversed"

    def test_monotonicity_property(self, sample_data):
        """
        Property test: adding new data should not change historical feature values.
        """
        # Use first 30 rows for initial calculation
        initial_data = sample_data.iloc[:30].copy()

        initial_features = compute_features(
            initial_data,
            specs=["rsi_14", "atr_14", "ema_12"],
            volatility_normalize=False,
        )

        # Add more data and recalculate
        extended_data = sample_data.iloc[:40].copy()

        extended_features = compute_features(
            extended_data,
            specs=["rsi_14", "atr_14", "ema_12"],
            volatility_normalize=False,
        )

        # Historical values should be identical
        feature_columns = ["rsi_14", "atr_14", "ema_12"]

        for feature in feature_columns:
            initial_values = initial_features[feature].dropna()
            extended_values = extended_features[feature].iloc[:30].dropna()

            min_len = min(len(initial_values), len(extended_values))
            if min_len > 0:
                initial_subset = initial_values.iloc[-min_len:]
                extended_subset = extended_values.iloc[-min_len:]

                np.testing.assert_array_almost_equal(
                    initial_subset.values,
                    extended_subset.values,
                    decimal=10,
                    err_msg=f"Historical values changed for {feature} when adding new data",
                )

    def test_timestamp_monotonicity(self, sample_data):
        """
        Property test: ensure timestamps are monotonic and features respect this.
        """
        # Check that timestamps are monotonic
        assert sample_data[
            "ts"
        ].is_monotonic_increasing, "Timestamps should be monotonic"

        # Calculate features
        features = compute_features(
            sample_data,
            specs=["rsi_14", "atr_14", "ema_12"],
            volatility_normalize=False,
        )

        # Check that features respect timestamp ordering
        assert features[
            "ts"
        ].is_monotonic_increasing, "Feature timestamps should be monotonic"

        # Check look-ahead safety
        assert ensure_no_lookahead(features), "Look-ahead safety check should pass"


class TestConsistencyProperties:
    """Test consistency properties of feature calculations."""

    @pytest.fixture
    def test_data(self):
        """Create test data for consistency checks."""
        dates = pd.date_range("2023-01-01", periods=100, freq="1H")
        np.random.seed(42)

        # Generate deterministic price data
        base_price = 100.0
        returns = np.random.normal(0, 0.02, 100)
        prices = [base_price]

        for ret in returns[1:]:
            new_price = prices[-1] * (1 + ret)
            prices.append(new_price)

        prices = np.array(prices)

        data = {
            "ts": [int(d.timestamp()) for d in dates],
            "open": prices * (1 + np.random.normal(0, 0.005, 100)),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.01, 100))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.01, 100))),
            "close": prices,
            "volume": np.random.uniform(1000, 10000, 100),
        }

        df = pd.DataFrame(data)
        df["high"] = df[["open", "high", "close"]].max(axis=1)
        df["low"] = df[["open", "low", "close"]].min(axis=1)

        return df

    def test_deterministic_property(self, test_data):
        """
        Property test: feature calculations should be deterministic
        (same input should produce same output).
        """
        # Calculate features twice with same input
        features1 = compute_features(
            test_data,
            specs=["rsi_14", "atr_14", "ema_12", "macd"],
            volatility_normalize=False,
        )

        features2 = compute_features(
            test_data,
            specs=["rsi_14", "atr_14", "ema_12", "macd"],
            volatility_normalize=False,
        )

        # Results should be identical
        pd.testing.assert_frame_equal(
            features1, features2, check_dtype=False, check_names=False
        )

    def test_normalization_consistency(self, test_data):
        """
        Property test: normalization should be consistent and reversible.
        """
        # Calculate features without normalization
        features_no_norm = compute_features(
            test_data, specs=["rsi_14", "atr_14"], volatility_normalize=False
        )

        # Calculate features with normalization
        features_with_norm = compute_features(
            test_data,
            specs=["rsi_14", "atr_14"],
            volatility_normalize=True,
            normalize_window=20,
        )

        # OHLCV data should be identical
        ohlcv_columns = ["open", "high", "low", "close", "volume", "ts"]
        for col in ohlcv_columns:
            pd.testing.assert_series_equal(
                features_no_norm[col], features_with_norm[col], check_names=False
            )

        # Feature values should be different (normalized vs non-normalized)
        feature_columns = ["rsi_14", "atr_14"]
        for feature in feature_columns:
            no_norm_values = features_no_norm[feature].dropna()
            with_norm_values = features_with_norm[feature].dropna()

            if len(no_norm_values) > 0 and len(with_norm_values) > 0:
                # Values should be different after normalization
                min_len = min(len(no_norm_values), len(with_norm_values))
                no_norm_subset = no_norm_values.iloc[-min_len:]
                with_norm_subset = with_norm_values.iloc[-min_len:]

                # Check that values are different (not identical)
                assert not np.allclose(
                    no_norm_subset.values, with_norm_subset.values, rtol=1e-10
                ), f"Feature {feature} values should be different after normalization"

    def test_feature_bounds_property(self, test_data):
        """
        Property test: features should have reasonable bounds.
        """
        features = compute_features(
            test_data,
            specs=["rsi_14", "atr_14", "ema_12", "macd"],
            volatility_normalize=False,
        )

        # RSI should be between 0 and 100
        rsi_values = features["rsi_14"].dropna()
        if len(rsi_values) > 0:
            assert rsi_values.min() >= 0, "RSI should be >= 0"
            assert rsi_values.max() <= 100, "RSI should be <= 100"

        # ATR should be positive
        atr_values = features["atr_14"].dropna()
        if len(atr_values) > 0:
            assert atr_values.min() >= 0, "ATR should be >= 0"

        # EMA should be positive (for positive prices)
        ema_values = features["ema_12"].dropna()
        if len(ema_values) > 0:
            assert ema_values.min() >= 0, "EMA should be >= 0 for positive prices"


class TestPerformanceProperties:
    """Test performance properties of feature calculations."""

    @pytest.fixture
    def large_data(self):
        """Create large dataset for performance testing."""
        dates = pd.date_range("2023-01-01", periods=1000, freq="1H")
        np.random.seed(42)

        # Generate large price dataset
        base_price = 100.0
        returns = np.random.normal(0, 0.02, 1000)
        prices = [base_price]

        for ret in returns[1:]:
            new_price = prices[-1] * (1 + ret)
            prices.append(new_price)

        prices = np.array(prices)

        data = {
            "ts": [int(d.timestamp()) for d in dates],
            "open": prices * (1 + np.random.normal(0, 0.005, 1000)),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.01, 1000))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.01, 1000))),
            "close": prices,
            "volume": np.random.uniform(1000, 10000, 1000),
        }

        df = pd.DataFrame(data)
        df["high"] = df[["open", "high", "close"]].max(axis=1)
        df["low"] = df[["open", "low", "close"]].min(axis=1)

        return df

    def test_scalability_property(self, large_data):
        """
        Property test: feature calculation should scale reasonably with data size.
        """
        import time

        # Test with subset of data
        small_data = large_data.iloc[:100]

        start_time = time.time()
        small_features = compute_features(
            small_data,
            specs=["rsi_14", "atr_14", "ema_12", "macd"],
            volatility_normalize=False,
        )
        small_time = time.time() - start_time

        # Test with full data
        start_time = time.time()
        large_features = compute_features(
            large_data,
            specs=["rsi_14", "atr_14", "ema_12", "macd"],
            volatility_normalize=False,
        )
        large_time = time.time() - start_time

        # Time should scale roughly linearly (allow some overhead)
        expected_ratio = len(large_data) / len(small_data)  # 10x
        actual_ratio = large_time / small_time

        # Should not scale worse than quadratic
        assert (
            actual_ratio <= expected_ratio * 2
        ), f"Performance scaling is poor: {actual_ratio:.2f}x vs expected ~{expected_ratio}x"

        # Both calculations should complete successfully
        assert isinstance(small_features, pd.DataFrame)
        assert isinstance(large_features, pd.DataFrame)
        assert len(small_features) == len(small_data)
        assert len(large_features) == len(large_data)
