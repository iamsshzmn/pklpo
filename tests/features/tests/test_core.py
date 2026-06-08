"""
Unit tests for the core module.

Tests the main feature calculation interface and related functions.
"""

import os

import numpy as np
import pandas as pd
import pytest

import src.features.core.calculation as calculation_module

from ..core import (
    compute_features,
    get_available_features,
    get_feature_info,
    validate_feature_compatibility,
)
from ..domain.models import FeatureError
from ..specs import FEATURE_SPECS


class TestCoreFunctions:
    """Test core functions of the features module."""

    @pytest.fixture
    def sample_ohlcv_data(self):
        """Create sample OHLCV data for testing."""
        dates = pd.date_range("2023-01-01", periods=100, freq="1H")
        np.random.seed(42)

        # Generate realistic price data
        base_price = 100.0
        returns = np.random.normal(0, 0.02, 100)  # 2% daily volatility
        prices = [base_price]

        for ret in returns[1:]:
            new_price = prices[-1] * (1 + ret)
            prices.append(new_price)

        prices = np.array(prices)

        # Generate OHLCV data
        data = {
            "ts": [int(d.timestamp()) for d in dates],
            "open": prices * (1 + np.random.normal(0, 0.005, 100)),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.01, 100))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.01, 100))),
            "close": prices,
            "volume": np.random.uniform(1000, 10000, 100),
        }

        df = pd.DataFrame(data)

        # Ensure OHLC relationships
        df["high"] = df[["open", "high", "close"]].max(axis=1)
        df["low"] = df[["open", "low", "close"]].min(axis=1)

        return df

    def test_get_available_features(self):
        """Test getting list of available features."""
        features = get_available_features()

        assert isinstance(features, list)
        assert len(features) > 0
        assert all(isinstance(f, str) for f in features)

        # Check that required features for Phase 2 are available
        required_features = ["atr_14", "rsi_14", "ema_12", "macd", "obv"]
        for feature in required_features:
            assert feature in features

    def test_get_feature_info(self):
        """Test getting feature information."""
        # Test existing feature
        info = get_feature_info("rsi_14")
        assert info is not None
        assert info.name == "rsi_14"
        assert info.type == "trend"
        assert "period" in info.params

        # Test non-existing feature
        info = get_feature_info("non_existent_feature")
        assert info is None

    def test_validate_feature_compatibility(self, sample_ohlcv_data):
        """Test feature compatibility validation."""
        # Test with valid features
        missing_cols = validate_feature_compatibility(
            sample_ohlcv_data, ["rsi_14", "atr_14"], FEATURE_SPECS
        )
        assert len(missing_cols) == 0

        # Test with missing required columns
        df_missing = sample_ohlcv_data.drop(columns=["volume"])
        missing_cols = validate_feature_compatibility(
            df_missing, ["obv"], FEATURE_SPECS
        )
        assert "volume" in missing_cols

    def test_compute_features_basic(self, sample_ohlcv_data):
        """Test basic feature computation."""
        # Test with single feature
        result = compute_features(
            sample_ohlcv_data, specs=["rsi_14"], volatility_normalize=False
        )

        assert isinstance(result, pd.DataFrame)
        assert "rsi_14" in result.columns
        assert len(result) == len(sample_ohlcv_data)
        assert not result["rsi_14"].isna().all()

        # Check that OHLCV data is preserved
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in result.columns
            pd.testing.assert_series_equal(
                result[col], sample_ohlcv_data[col], check_names=False
            )

    def test_compute_features_multiple(self, sample_ohlcv_data):
        """Test computing multiple features."""
        features = ["rsi_14", "atr_14", "ema_12"]
        result = compute_features(
            sample_ohlcv_data, specs=features, volatility_normalize=False
        )

        assert isinstance(result, pd.DataFrame)
        for feature in features:
            assert feature in result.columns
            assert not result[feature].isna().all()

    def test_compute_features_all(self, sample_ohlcv_data):
        """Test computing all available features."""
        result = compute_features(
            sample_ohlcv_data,
            specs=None,
            volatility_normalize=False,  # All features
        )

        assert isinstance(result, pd.DataFrame)
        assert len(result.columns) > 5  # More than just OHLCV

        # Check that all required features for Phase 2 are present
        required_features = ["atr_14", "rsi_14", "ema_12", "ema_26", "macd", "obv"]
        for feature in required_features:
            assert feature in result.columns

    def test_compute_features_with_normalization(self, sample_ohlcv_data):
        """Test feature computation with volatility normalization."""
        result = compute_features(
            sample_ohlcv_data,
            specs=["rsi_14", "atr_14"],
            volatility_normalize=True,
            normalize_window=10,
        )

        assert isinstance(result, pd.DataFrame)
        assert "rsi_14" in result.columns
        assert "atr_14" in result.columns

    def test_compute_features_debug_does_not_mutate_env(
        self,
        sample_ohlcv_data,
        monkeypatch,
    ):
        monkeypatch.delenv("FEATURES_DEBUG", raising=False)
        monkeypatch.delenv("FEATURES_VERBOSE", raising=False)

        result = compute_features(
            sample_ohlcv_data,
            specs=["rsi_14"],
            volatility_normalize=False,
            debug=True,
        )

        assert isinstance(result, pd.DataFrame)
        assert "FEATURES_DEBUG" not in os.environ
        assert "FEATURES_VERBOSE" not in os.environ

    def test_compute_features_accepts_custom_critical_indicators(
        self,
        sample_ohlcv_data,
        monkeypatch,
    ):
        captured = {}

        def _fake_internal(
            result_df,
            feature_specs,
            ctx,
            *,
            critical_indicators=None,
            **kwargs,
        ):
            captured["critical_indicators"] = critical_indicators
            captured["ctx_debug"] = ctx.debug
            return result_df

        monkeypatch.setattr(
            calculation_module,
            "_calculate_features_internal",
            _fake_internal,
        )
        monkeypatch.setattr(
            calculation_module,
            "run_post_calculation",
            lambda result_df, ctx: result_df,
        )

        result = compute_features(
            sample_ohlcv_data,
            specs=["rsi_14"],
            volatility_normalize=False,
            critical_indicators=["ema_21"],
        )

        assert isinstance(result, pd.DataFrame)
        assert captured["critical_indicators"] == ["ema_21"]
        assert captured["ctx_debug"] is False

    def test_compute_features_invalid_data(self):
        """Test feature computation with invalid data."""
        # Test with None
        with pytest.raises(FeatureError):
            compute_features(None)

        # Test with empty DataFrame
        with pytest.raises(FeatureError):
            compute_features(pd.DataFrame())

        # Test with missing columns
        invalid_df = pd.DataFrame({"open": [100, 101, 102], "close": [101, 102, 103]})
        with pytest.raises(FeatureError):
            compute_features(invalid_df)

    def test_compute_features_invalid_specs(self, sample_ohlcv_data):
        """Test feature computation with invalid specifications."""
        # Test with non-existent feature
        with pytest.raises(FeatureError):
            compute_features(sample_ohlcv_data, specs=["non_existent_feature"])

        # Test with invalid spec type
        with pytest.raises(FeatureError):
            compute_features(sample_ohlcv_data, specs=[123])

    def test_compute_features_performance(self, sample_ohlcv_data):
        """Test performance of feature computation."""
        import time

        start_time = time.time()
        result = compute_features(
            sample_ohlcv_data,
            specs=["rsi_14", "atr_14", "ema_12", "macd", "obv"],
            volatility_normalize=False,
        )
        end_time = time.time()

        computation_time = end_time - start_time

        # Should complete within reasonable time (adjust threshold as needed)
        assert computation_time < 5.0  # 5 seconds for 100 bars

        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(sample_ohlcv_data)


class TestFeatureCalculationEdgeCases:
    """Test edge cases in feature calculation."""

    @pytest.fixture
    def minimal_data(self):
        """Create minimal valid OHLCV data."""
        return pd.DataFrame(
            {
                "ts": [1640995200, 1640998800, 1641002400],  # 3 timestamps
                "open": [100.0, 101.0, 102.0],
                "high": [102.0, 103.0, 104.0],
                "low": [99.0, 100.0, 101.0],
                "close": [101.0, 102.0, 103.0],
                "volume": [1000, 1100, 1200],
            }
        )

    def test_minimal_data(self, minimal_data):
        """Test feature calculation with minimal data."""
        result = compute_features(
            minimal_data, specs=["rsi_14"], volatility_normalize=False
        )

        assert isinstance(result, pd.DataFrame)
        assert "rsi_14" in result.columns
        # RSI needs more data for meaningful calculation, so expect some NaN
        assert result["rsi_14"].isna().any()

    def test_constant_price_data(self):
        """Test feature calculation with constant price data."""
        constant_data = pd.DataFrame(
            {
                "ts": [1640995200, 1640998800, 1641002400],
                "open": [100.0, 100.0, 100.0],
                "high": [100.0, 100.0, 100.0],
                "low": [100.0, 100.0, 100.0],
                "close": [100.0, 100.0, 100.0],
                "volume": [1000, 1000, 1000],
            }
        )

        result = compute_features(
            constant_data, specs=["rsi_14", "atr_14"], volatility_normalize=False
        )

        assert isinstance(result, pd.DataFrame)
        # Some features may have NaN or constant values with constant data
        assert "rsi_14" in result.columns
        assert "atr_14" in result.columns
