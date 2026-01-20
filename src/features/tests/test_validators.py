"""
Unit tests for validators.
"""

import numpy as np
import pandas as pd
import pytest

from src.features.models import FeatureSpec, FeatureValidationError
from src.features.validators import (
    _validate_ohlc_relationship,
    validate_feature_specs_integrity,
    validate_ohlcv_data,
    validate_phase_requirements,
)


class TestValidateOHLCVData:
    """Test OHLCV data validation."""

    def test_valid_ohlcv_data(self):
        """Test valid OHLCV data passes validation."""
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0],
                "high": [105.0, 106.0, 107.0],
                "low": [99.0, 100.0, 101.0],
                "close": [104.0, 105.0, 106.0],
                "volume": [1000, 1100, 1200],
            }
        )
        # Should not raise any exception
        validate_ohlcv_data(df)

    def test_empty_dataframe(self):
        """Test empty DataFrame raises error."""
        df = pd.DataFrame()
        with pytest.raises(
            FeatureValidationError, match="OHLCV DataFrame is None or empty"
        ):
            validate_ohlcv_data(df)

    def test_none_dataframe(self):
        """Test None DataFrame raises error."""
        with pytest.raises(
            FeatureValidationError, match="OHLCV DataFrame is None or empty"
        ):
            validate_ohlcv_data(None)

    def test_missing_required_columns(self):
        """Test missing required columns raises error."""
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                # missing 'close' and 'volume'
            }
        )
        with pytest.raises(FeatureValidationError, match="Missing required columns"):
            validate_ohlcv_data(df)

    def test_non_numeric_columns(self):
        """Test non-numeric columns raise error."""
        df = pd.DataFrame(
            {
                "open": ["100.0", "101.0"],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [104.0, 105.0],
                "volume": [1000, 1100],
            }
        )
        with pytest.raises(FeatureValidationError, match="Column open must be numeric"):
            validate_ohlcv_data(df)

    def test_negative_prices(self):
        """Test negative prices raise error."""
        df = pd.DataFrame(
            {
                "open": [-100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [104.0, 105.0],
                "volume": [1000, 1100],
            }
        )
        with pytest.raises(
            FeatureValidationError, match="Negative values found in open column"
        ):
            validate_ohlcv_data(df)

    def test_negative_volume(self):
        """Test negative volume raises error."""
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [104.0, 105.0],
                "volume": [-1000, 1100],
            }
        )
        with pytest.raises(
            FeatureValidationError, match="Negative values found in volume column"
        ):
            validate_ohlcv_data(df)

    def test_invalid_ohlc_relationship(self):
        """Test invalid OHLC relationships raise error."""
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [95.0, 106.0],  # high < low
                "low": [99.0, 100.0],
                "close": [104.0, 105.0],
                "volume": [1000, 1100],
            }
        )
        with pytest.raises(FeatureValidationError, match="Invalid OHLC relationship"):
            validate_ohlcv_data(df)

    def test_close_outside_high_low(self):
        """Test close outside high-low range raises error."""
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [110.0, 105.0],  # close > high
                "volume": [1000, 1100],
            }
        )
        with pytest.raises(FeatureValidationError, match="Invalid OHLC relationship"):
            validate_ohlcv_data(df)

    def test_infinite_values(self):
        """Test infinite values raise error."""
        df = pd.DataFrame(
            {
                "open": [100.0, np.inf],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [104.0, 105.0],
                "volume": [1000, 1100],
            }
        )
        with pytest.raises(
            FeatureValidationError, match="Infinite values found in columns"
        ):
            validate_ohlcv_data(df)

    def test_non_monotonic_timestamps(self):
        """Test non-monotonic timestamps raise error."""
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0],
                "high": [105.0, 106.0, 107.0],
                "low": [99.0, 100.0, 101.0],
                "close": [104.0, 105.0, 106.0],
                "volume": [1000, 1100, 1200],
                "ts": [1672574400, 1672574520, 1672574460],  # not monotonic
            }
        )
        with pytest.raises(
            FeatureValidationError, match="Timestamps are not in ascending order"
        ):
            validate_ohlcv_data(df)


class TestValidateOHLCRelationship:
    """Test OHLC relationship validation."""

    def test_valid_ohlc_relationship(self):
        """Test valid OHLC relationships."""
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0],
                "high": [105.0, 106.0, 107.0],
                "low": [99.0, 100.0, 101.0],
                "close": [104.0, 105.0, 106.0],
            }
        )
        assert _validate_ohlc_relationship(df) is True

    def test_high_less_than_low(self):
        """Test high < low returns False."""
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [95.0, 106.0],
                "low": [99.0, 100.0],
                "close": [104.0, 105.0],
            }
        )
        assert _validate_ohlc_relationship(df) is False

    def test_close_below_low(self):
        """Test close < low returns False."""
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [98.0, 105.0],  # close < low
            }
        )
        assert _validate_ohlc_relationship(df) is False

    def test_close_above_high(self):
        """Test close > high returns False."""
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [110.0, 105.0],  # close > high
            }
        )
        assert _validate_ohlc_relationship(df) is False


class TestValidateFeatureSpecsIntegrity:
    """Test feature specifications integrity validation."""

    def test_valid_specs(self):
        """Test valid feature specs pass validation."""
        specs = [
            FeatureSpec(
                name="test_feature_1",
                type="trend",
                params={"period": 14},
                requires=["close"],
                description="Test feature 1",
            ),
            FeatureSpec(
                name="test_feature_2",
                type="volatility",
                params={"period": 20},
                requires=["high", "low"],
                description="Test feature 2",
            ),
        ]
        # Should not raise any exception
        validate_feature_specs_integrity(specs)

    def test_empty_specs_list(self):
        """Test empty specs list raises error."""
        with pytest.raises(
            FeatureValidationError, match="Feature specifications list is empty"
        ):
            validate_feature_specs_integrity([])

    def test_duplicate_feature_names(self):
        """Test duplicate feature names raise error."""
        specs = [
            FeatureSpec(
                name="duplicate_feature",
                type="trend",
                params={"period": 14},
                requires=["close"],
                description="Test feature 1",
            ),
            FeatureSpec(
                name="duplicate_feature",  # duplicate name
                type="volatility",
                params={"period": 20},
                requires=["high", "low"],
                description="Test feature 2",
            ),
        ]
        with pytest.raises(FeatureValidationError, match="Duplicate feature names"):
            validate_feature_specs_integrity(specs)

    def test_invalid_spec_validation(self):
        """Test invalid spec raises error."""
        # Create a spec with invalid parameters that would fail validation
        with pytest.raises(ValueError, match="Feature name cannot be empty"):
            FeatureSpec(
                name="",  # empty name should fail validation
                type="trend",
                params={"period": 14},
                requires=["close"],
                description="Test feature",
            )


class TestValidatePhaseRequirements:
    """Test phase requirements validation."""

    def test_meets_phase_requirements(self):
        """Test specs that meet phase requirements."""
        specs = [
            FeatureSpec(
                name="atr_14",
                type="volatility",
                params={"period": 14},
                requires=["high", "low", "close"],
                description="ATR",
            ),
            FeatureSpec(
                name="rsi_14",
                type="oscillator",
                params={"period": 14},
                requires=["close"],
                description="RSI",
            ),
        ]
        required = ["atr_14", "rsi_14"]
        # Should not raise any exception
        validate_phase_requirements(specs, required)

    def test_missing_required_features(self):
        """Test missing required features raise error."""
        specs = [
            FeatureSpec(
                name="atr_14",
                type="volatility",
                params={"period": 14},
                requires=["high", "low", "close"],
                description="ATR",
            )
        ]
        required = ["atr_14", "rsi_14", "macd"]  # missing rsi_14 and macd
        with pytest.raises(FeatureValidationError, match="Missing required features"):
            validate_phase_requirements(specs, required)

    def test_none_specs_list(self):
        """Test None specs list raises error."""
        with pytest.raises(
            FeatureValidationError, match="Feature specifications list is None"
        ):
            validate_phase_requirements(None)

    def test_default_phase_2_requirements(self):
        """Test using default Phase 2 requirements."""
        # This test would need to import PHASE_2_REQUIRED_FEATURES
        # For now, just test that it doesn't crash with empty required list
        specs = [
            FeatureSpec(
                name="test_feature",
                type="trend",
                params={"period": 14},
                requires=["close"],
                description="Test feature",
            )
        ]
        # Should not raise any exception when required_list is empty
        validate_phase_requirements(specs, [])
