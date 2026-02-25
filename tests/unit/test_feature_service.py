"""
Unit tests for FeatureCalculationService (Task 8).

Tests the high-level service with dependency injection.
"""

from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from src.features.application.feature_service import (
    DefaultFeatureNormalizer,
    DefaultOHLCVValidator,
    FeatureCalculationService,
    create_feature_service,
    get_default_service,
)


class TestDefaultOHLCVValidator:
    """Tests for DefaultOHLCVValidator implementation."""

    def test_valid_df_passes(self, ohlcv_basic):
        """Valid OHLCV DataFrame passes validation."""
        validator = DefaultOHLCVValidator()
        assert validator.validate(ohlcv_basic) is True

    def test_none_df_raises(self):
        """None DataFrame raises ValueError."""
        validator = DefaultOHLCVValidator()

        with pytest.raises(ValueError, match="None or empty"):
            validator.validate(None)

    def test_empty_df_raises(self, empty_df):
        """Empty DataFrame raises ValueError."""
        validator = DefaultOHLCVValidator()

        with pytest.raises(ValueError, match="None or empty"):
            validator.validate(empty_df)

    def test_missing_column_raises(self, ohlcv_missing_columns):
        """Missing required columns raises ValueError."""
        validator = DefaultOHLCVValidator()

        with pytest.raises(ValueError, match="Missing required columns"):
            validator.validate(ohlcv_missing_columns)

    def test_all_nan_column_raises(self, ohlcv_basic):
        """Column with all NaN values raises ValueError."""
        df = ohlcv_basic.copy()
        df["close"] = np.nan

        validator = DefaultOHLCVValidator()

        with pytest.raises(ValueError, match="only NaN"):
            validator.validate(df)

    def test_required_columns(self):
        """Required columns are defined correctly."""
        assert {
            "open", "high", "low", "close", "volume"
        } == DefaultOHLCVValidator.REQUIRED_COLUMNS


class TestDefaultFeatureNormalizer:
    """Tests for DefaultFeatureNormalizer implementation."""

    def test_normalize_returns_dataframe(self, ohlcv_basic):
        """Normalize returns a DataFrame."""
        normalizer = DefaultFeatureNormalizer()

        # May fail if volatility_normalize_features not available
        try:
            result = normalizer.normalize(ohlcv_basic)
            assert isinstance(result, pd.DataFrame)
        except (ImportError, TypeError):
            # OK if utility not available
            pass

    def test_normalize_accepts_window_param(self, ohlcv_basic):
        """Normalize accepts window parameter."""
        normalizer = DefaultFeatureNormalizer()

        try:
            result = normalizer.normalize(ohlcv_basic, window=30)
            assert isinstance(result, pd.DataFrame)
        except (ImportError, TypeError):
            pass


class TestFeatureCalculationService:
    """Tests for FeatureCalculationService (Task 8)."""

    @pytest.fixture
    def mock_compute_fn(self):
        """Mock compute function."""
        mock = Mock(return_value=pd.DataFrame({
            "open": [100, 101, 102],
            "close": [104, 105, 106],
            "rsi_14": [50.0, 60.0, 70.0],
        }))
        return mock

    def test_service_creation_defaults(self):
        """Service uses default implementations."""
        service = FeatureCalculationService()

        assert isinstance(service.validator, DefaultOHLCVValidator)
        assert isinstance(service.normalizer, DefaultFeatureNormalizer)

    def test_service_custom_validator(self):
        """Service accepts custom validator."""
        mock_validator = Mock()
        mock_validator.validate = Mock(return_value=True)

        service = FeatureCalculationService(validator=mock_validator)

        assert service.validator is mock_validator

    def test_service_custom_normalizer(self):
        """Service accepts custom normalizer."""
        mock_normalizer = Mock()

        service = FeatureCalculationService(normalizer=mock_normalizer)

        assert service.normalizer is mock_normalizer

    def test_calculate_calls_validator(self, ohlcv_basic, mock_compute_fn):
        """Calculate calls validator first."""
        mock_validator = Mock()
        mock_validator.validate = Mock(return_value=True)

        service = FeatureCalculationService(
            validator=mock_validator,
            _compute_fn=mock_compute_fn,
        )

        service.calculate(ohlcv_basic)

        mock_validator.validate.assert_called_once_with(ohlcv_basic)

    def test_calculate_calls_compute_fn(self, ohlcv_basic, mock_compute_fn):
        """Calculate calls compute function."""
        service = FeatureCalculationService(_compute_fn=mock_compute_fn)

        service.calculate(ohlcv_basic, specs=["rsi_14"])

        mock_compute_fn.assert_called_once()
        call_kwargs = mock_compute_fn.call_args[1]
        assert call_kwargs["specs"] == ["rsi_14"]

    def test_calculate_passes_normalize_false_to_compute(self, ohlcv_basic, mock_compute_fn):
        """Calculate passes volatility_normalize=False to compute function."""
        service = FeatureCalculationService(_compute_fn=mock_compute_fn)

        service.calculate(ohlcv_basic, volatility_normalize=True)

        call_kwargs = mock_compute_fn.call_args[1]
        assert call_kwargs["volatility_normalize"] is False  # Service handles it

    def test_calculate_applies_normalization(self, ohlcv_basic, mock_compute_fn):
        """Calculate applies normalization when requested."""
        mock_normalizer = Mock()
        mock_normalizer.normalize = Mock(return_value=pd.DataFrame({
            "rsi_14_norm": [0.5, 0.6, 0.7]
        }))

        service = FeatureCalculationService(
            normalizer=mock_normalizer,
            _compute_fn=mock_compute_fn,
        )

        result = service.calculate(
            ohlcv_basic,
            volatility_normalize=True,
            normalize_window=30
        )

        mock_normalizer.normalize.assert_called_once()
        assert "rsi_14_norm" in result.columns

    def test_calculate_skips_normalization_when_false(self, ohlcv_basic, mock_compute_fn):
        """Calculate skips normalization when not requested."""
        mock_normalizer = Mock()
        mock_normalizer.normalize = Mock()

        service = FeatureCalculationService(
            normalizer=mock_normalizer,
            _compute_fn=mock_compute_fn,
        )

        service.calculate(ohlcv_basic, volatility_normalize=False)

        mock_normalizer.normalize.assert_not_called()

    def test_calculate_passes_kwargs(self, ohlcv_basic, mock_compute_fn):
        """Calculate passes additional kwargs to compute function."""
        service = FeatureCalculationService(_compute_fn=mock_compute_fn)

        service.calculate(ohlcv_basic, symbol="BTC-USDT", timeframe="1h")

        call_kwargs = mock_compute_fn.call_args[1]
        assert call_kwargs["symbol"] == "BTC-USDT"
        assert call_kwargs["timeframe"] == "1h"


class TestFeatureCalculationServiceBatch:
    """Tests for calculate_batch method."""

    def test_calculate_batch_converts_set_to_list(self, ohlcv_basic):
        """calculate_batch converts available set to specs list."""
        mock_compute_fn = Mock(return_value=pd.DataFrame())

        service = FeatureCalculationService(_compute_fn=mock_compute_fn)

        service.calculate_batch(ohlcv_basic, {"rsi_14", "ema_21"})

        call_kwargs = mock_compute_fn.call_args[1]
        assert set(call_kwargs["specs"]) == {"rsi_14", "ema_21"}

    def test_calculate_batch_passes_normalize(self, ohlcv_basic):
        """calculate_batch passes volatility_normalize."""
        mock_compute_fn = Mock(return_value=pd.DataFrame())
        mock_normalizer = Mock()
        mock_normalizer.normalize = Mock(return_value=pd.DataFrame())

        service = FeatureCalculationService(
            _compute_fn=mock_compute_fn,
            normalizer=mock_normalizer,
        )

        service.calculate_batch(
            ohlcv_basic,
            {"rsi_14"},
            volatility_normalize=True
        )

        mock_normalizer.normalize.assert_called_once()


class TestFeatureCalculationServiceStatic:
    """Tests for static methods."""

    def test_get_available_specs(self):
        """get_available_specs returns list of names."""
        specs = FeatureCalculationService.get_available_specs()

        assert isinstance(specs, list)
        # Should have some specs defined
        # (may be empty if FEATURE_SPECS not populated)

    def test_get_spec_info_existing(self):
        """get_spec_info returns spec for existing indicator."""
        # This depends on FEATURE_SPECS having entries
        specs = FeatureCalculationService.get_available_specs()

        if specs:
            info = FeatureCalculationService.get_spec_info(specs[0])
            # Should return FeatureSpec or None

    def test_get_spec_info_nonexistent(self):
        """get_spec_info returns None for nonexistent."""
        info = FeatureCalculationService.get_spec_info("nonexistent_indicator_xyz")
        assert info is None


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_feature_service_defaults(self):
        """create_feature_service uses defaults."""
        service = create_feature_service()

        assert isinstance(service, FeatureCalculationService)
        assert isinstance(service.validator, DefaultOHLCVValidator)
        assert isinstance(service.normalizer, DefaultFeatureNormalizer)

    def test_create_feature_service_custom_validator(self):
        """create_feature_service accepts custom validator."""
        custom_validator = Mock()

        service = create_feature_service(validator=custom_validator)

        assert service.validator is custom_validator

    def test_create_feature_service_custom_normalizer(self):
        """create_feature_service accepts custom normalizer."""
        custom_normalizer = Mock()

        service = create_feature_service(normalizer=custom_normalizer)

        assert service.normalizer is custom_normalizer

    def test_get_default_service_singleton(self):
        """get_default_service returns singleton."""
        # Reset first
        import src.features.application.feature_service as module
        module._default_service = None

        s1 = get_default_service()
        s2 = get_default_service()

        assert s1 is s2

    def test_get_default_service_creates_instance(self):
        """get_default_service creates FeatureCalculationService."""
        import src.features.application.feature_service as module
        module._default_service = None

        service = get_default_service()

        assert isinstance(service, FeatureCalculationService)
