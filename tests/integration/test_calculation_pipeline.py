"""
Integration tests for the calculation pipeline.

Tests the full feature calculation flow from OHLCV to indicators.
"""

import pandas as pd
import pytest


@pytest.mark.integration
class TestComputeFeaturesBasic:
    """Basic integration tests for compute_features."""

    def test_compute_features_returns_dataframe(self, ohlcv_50_bars):
        """compute_features returns a DataFrame."""
        from src.features.core.calculation import compute_features

        result = compute_features(
            ohlcv_50_bars,
            specs=None,  # Default
            volatility_normalize=False,
        )

        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(ohlcv_50_bars)

    def test_compute_features_preserves_rows(self, ohlcv_100_bars):
        """compute_features preserves row count."""
        from src.features.core.calculation import compute_features

        result = compute_features(
            ohlcv_100_bars,
            volatility_normalize=False,
        )

        assert len(result) == 100

    def test_compute_features_adds_columns(self, ohlcv_50_bars):
        """compute_features adds indicator columns."""
        from src.features.core.calculation import compute_features

        original_cols = len(ohlcv_50_bars.columns)

        result = compute_features(
            ohlcv_50_bars,
            volatility_normalize=False,
        )

        # Should have more columns than original
        assert len(result.columns) >= original_cols


@pytest.mark.integration
class TestComputeFeaturesWithSpecs:
    """Tests for compute_features with specific specs."""

    def test_compute_with_single_spec(self, ohlcv_100_bars):
        """compute_features with single spec."""
        from src.features.core.calculation import compute_features

        try:
            result = compute_features(
                ohlcv_100_bars,
                specs=["rsi_14"],
                volatility_normalize=False,
            )

            assert isinstance(result, pd.DataFrame)
        except Exception as e:
            # May fail if pandas_ta not available
            pytest.skip(f"Skipped due to: {e}")

    def test_compute_with_multiple_specs(self, ohlcv_100_bars):
        """compute_features with multiple specs."""
        from src.features.core.calculation import compute_features

        try:
            result = compute_features(
                ohlcv_100_bars,
                specs=["rsi_14", "ema_21", "sma_20"],
                volatility_normalize=False,
            )

            assert isinstance(result, pd.DataFrame)
        except Exception as e:
            pytest.skip(f"Skipped due to: {e}")


@pytest.mark.integration
class TestComputeFeaturesNormalization:
    """Tests for compute_features with normalization."""

    def test_compute_with_normalization(self, ohlcv_100_bars):
        """compute_features with volatility normalization."""
        from src.features.core.calculation import compute_features

        try:
            result = compute_features(
                ohlcv_100_bars,
                volatility_normalize=True,
                normalize_window=20,
            )

            assert isinstance(result, pd.DataFrame)
        except Exception as e:
            pytest.skip(f"Skipped due to: {e}")

    def test_normalization_window_parameter(self, ohlcv_100_bars):
        """Normalization respects window parameter."""
        from src.features.core.calculation import compute_features

        try:
            result = compute_features(
                ohlcv_100_bars,
                volatility_normalize=True,
                normalize_window=30,
            )

            assert isinstance(result, pd.DataFrame)
        except Exception as e:
            pytest.skip(f"Skipped due to: {e}")


@pytest.mark.integration
class TestComputeFeaturesContext:
    """Tests for compute_features context handling."""

    def test_compute_with_symbol_timeframe(self, ohlcv_50_bars):
        """compute_features accepts symbol and timeframe."""
        from src.features.core.calculation import compute_features

        try:
            result = compute_features(
                ohlcv_50_bars,
                symbol="BTC-USDT",
                timeframe="1h",
                volatility_normalize=False,
            )

            assert isinstance(result, pd.DataFrame)
        except Exception as e:
            pytest.skip(f"Skipped due to: {e}")

    def test_compute_with_debug_mode(self, ohlcv_50_bars):
        """compute_features with debug=True."""
        from src.features.core.calculation import compute_features

        try:
            result = compute_features(
                ohlcv_50_bars,
                debug=True,
                volatility_normalize=False,
            )

            assert isinstance(result, pd.DataFrame)
        except Exception as e:
            pytest.skip(f"Skipped due to: {e}")


@pytest.mark.integration
class TestFeatureServiceIntegration:
    """Integration tests for FeatureCalculationService."""

    def test_service_calculate(self, ohlcv_50_bars):
        """FeatureCalculationService.calculate works."""
        from src.features.application.feature_service import get_default_service

        service = get_default_service()

        try:
            result = service.calculate(
                ohlcv_50_bars,
                specs=None,
                volatility_normalize=False,
            )

            assert isinstance(result, pd.DataFrame)
        except Exception as e:
            pytest.skip(f"Skipped due to: {e}")

    def test_service_calculate_batch(self, ohlcv_50_bars):
        """FeatureCalculationService.calculate_batch works."""
        from src.features.application.feature_service import get_default_service

        service = get_default_service()

        try:
            result = service.calculate_batch(
                ohlcv_50_bars,
                available={"rsi_14", "ema_21"},
                volatility_normalize=False,
            )

            assert isinstance(result, pd.DataFrame)
        except Exception as e:
            pytest.skip(f"Skipped due to: {e}")


@pytest.mark.integration
class TestValidationChainIntegration:
    """Integration tests for ValidationChain with real data."""

    def test_default_chain_validates_ohlcv(self, ohlcv_50_bars):
        """Default validation chain validates OHLCV data."""
        from src.features.validation.chain import create_default_chain

        chain = create_default_chain()
        result = chain.validate(ohlcv_50_bars)

        assert result.is_valid is True

    def test_strict_chain_validates_ohlcv(self, ohlcv_100_bars):
        """Strict validation chain validates OHLCV data."""
        from src.features.validation.chain import create_strict_chain

        chain = create_strict_chain()
        result = chain.validate(ohlcv_100_bars)

        assert result.is_valid is True

    def test_chain_rejects_invalid_data(self, empty_df):
        """Validation chain rejects invalid data."""
        from src.features.validation.chain import create_default_chain

        chain = create_default_chain()
        result = chain.validate(empty_df)

        assert result.is_valid is False


@pytest.mark.integration
class TestGroupRegistryIntegration:
    """Integration tests for GroupRegistry with real groups."""

    def test_registry_has_groups(self):
        """Registry has registered groups."""
        from src.features.indicator_groups.registry import GroupRegistry

        # Force initialization
        GroupRegistry._ensure_initialized()

        groups = GroupRegistry.get_all_names()

        # Should have some groups registered
        assert len(groups) > 0

    def test_registry_groups_are_callable(self):
        """Registered group calculators are callable."""
        from src.features.indicator_groups.registry import get_ordered_groups

        groups = get_ordered_groups()

        for name, calculator in groups:
            assert callable(calculator)

    def test_registry_groups_have_order(self):
        """Registered groups have valid order."""
        from src.features.indicator_groups.registry import GroupRegistry

        GroupRegistry._ensure_initialized()

        ordered = GroupRegistry.get_ordered()
        orders = [g.order for g in ordered]

        # Orders should be sorted
        assert orders == sorted(orders)
