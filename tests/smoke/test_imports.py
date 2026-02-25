"""
Smoke tests for features module imports.

These tests verify that all modules can be imported without errors.
Run first to catch import/dependency issues.
"""

import pytest


@pytest.mark.smoke
class TestCoreImports:
    """Test core module imports."""

    def test_import_main_package(self):
        """Import main features package."""
        from src import features
        assert features is not None

    def test_import_compute_features(self):
        """Import compute_features function."""
        from src.features.core.calculation import compute_features
        assert callable(compute_features)


@pytest.mark.smoke
class TestContainerImports:
    """Test container module imports."""

    def test_import_container_class(self):
        """Import Container class."""
        from src.features.container import Container
        assert Container is not None

    def test_import_get_container(self):
        """Import get_container function."""
        from src.features.container import get_container
        assert callable(get_container)

    def test_import_reset_container(self):
        """Import reset_container function."""
        from src.features.container import reset_container
        assert callable(reset_container)


@pytest.mark.smoke
class TestValidationChainImports:
    """Test validation chain module imports."""

    def test_import_validation_result(self):
        """Import ValidationResult class."""
        from src.features.validation.chain import ValidationResult
        assert ValidationResult is not None

    def test_import_validator(self):
        """Import Validator ABC."""
        from src.features.validation.chain import Validator
        assert Validator is not None

    def test_import_validation_chain(self):
        """Import ValidationChain class."""
        from src.features.validation.chain import ValidationChain
        assert ValidationChain is not None

    def test_import_ohlcv_validator(self):
        """Import OHLCVValidator class."""
        from src.features.validation.chain import OHLCVValidator
        assert OHLCVValidator is not None

    def test_import_min_rows_validator(self):
        """Import MinRowsValidator class."""
        from src.features.validation.chain import MinRowsValidator
        assert MinRowsValidator is not None

    def test_import_timestamp_validator(self):
        """Import TimestampValidator class."""
        from src.features.validation.chain import TimestampValidator
        assert TimestampValidator is not None

    def test_import_nan_ratio_validator(self):
        """Import NaNRatioValidator class."""
        from src.features.validation.chain import NaNRatioValidator
        assert NaNRatioValidator is not None

    def test_import_create_default_chain(self):
        """Import create_default_chain function."""
        from src.features.validation.chain import create_default_chain
        assert callable(create_default_chain)

    def test_import_create_strict_chain(self):
        """Import create_strict_chain function."""
        from src.features.validation.chain import create_strict_chain
        assert callable(create_strict_chain)


@pytest.mark.smoke
class TestGroupRegistryImports:
    """Test group registry module imports."""

    def test_import_group_registry(self):
        """Import GroupRegistry class."""
        from src.features.indicator_groups.registry import GroupRegistry
        assert GroupRegistry is not None

    def test_import_group_entry(self):
        """Import GroupEntry class."""
        from src.features.indicator_groups.registry import GroupEntry
        assert GroupEntry is not None

    def test_import_get_ordered_groups(self):
        """Import get_ordered_groups function."""
        from src.features.indicator_groups.registry import get_ordered_groups
        assert callable(get_ordered_groups)

    def test_import_get_group_calculator(self):
        """Import get_group_calculator function."""
        from src.features.indicator_groups.registry import get_group_calculator
        assert callable(get_group_calculator)


@pytest.mark.smoke
class TestProtocolsImports:
    """Test protocols module imports."""

    def test_import_indicator_calculator(self):
        """Import IndicatorCalculator protocol."""
        from src.features.domain.protocols import IndicatorCalculator
        assert IndicatorCalculator is not None

    def test_import_batch_indicator_calculator(self):
        """Import BatchIndicatorCalculator protocol."""
        from src.features.domain.protocols import BatchIndicatorCalculator
        assert BatchIndicatorCalculator is not None

    def test_import_feature_calculator(self):
        """Import FeatureCalculator protocol."""
        from src.features.domain.protocols import FeatureCalculator
        assert FeatureCalculator is not None

    def test_import_ohlcv_validator_protocol(self):
        """Import OHLCVValidator protocol."""
        from src.features.domain.protocols import OHLCVValidator
        assert OHLCVValidator is not None

    def test_import_feature_normalizer(self):
        """Import FeatureNormalizer protocol."""
        from src.features.domain.protocols import FeatureNormalizer
        assert FeatureNormalizer is not None


@pytest.mark.smoke
class TestFeatureServiceImports:
    """Test feature service module imports."""

    def test_import_feature_calculation_service(self):
        """Import FeatureCalculationService class."""
        from src.features.application.feature_service import FeatureCalculationService
        assert FeatureCalculationService is not None

    def test_import_default_ohlcv_validator(self):
        """Import DefaultOHLCVValidator class."""
        from src.features.application.feature_service import DefaultOHLCVValidator
        assert DefaultOHLCVValidator is not None

    def test_import_default_feature_normalizer(self):
        """Import DefaultFeatureNormalizer class."""
        from src.features.application.feature_service import DefaultFeatureNormalizer
        assert DefaultFeatureNormalizer is not None

    def test_import_create_feature_service(self):
        """Import create_feature_service function."""
        from src.features.application.feature_service import create_feature_service
        assert callable(create_feature_service)

    def test_import_get_default_service(self):
        """Import get_default_service function."""
        from src.features.application.feature_service import get_default_service
        assert callable(get_default_service)


@pytest.mark.smoke
class TestPipelineImports:
    """Test pipeline module imports."""

    def test_import_base_context(self):
        """Import BaseContext class."""
        from src.features.core.pipeline import BaseContext
        assert BaseContext is not None

    def test_import_group_calculation_context(self):
        """Import GroupCalculationContext class."""
        from src.features.core.pipeline import GroupCalculationContext
        assert GroupCalculationContext is not None

    def test_import_pipeline_context(self):
        """Import PipelineContext alias."""
        from src.features.core.pipeline import PipelineContext
        assert PipelineContext is not None


@pytest.mark.smoke
class TestAlertsImports:
    """Test alerts module imports."""

    def test_import_alert_level(self):
        """Import AlertLevel enum."""
        from src.features.infrastructure.alerts import AlertLevel
        assert AlertLevel is not None

    def test_import_alert_context(self):
        """Import AlertContext class."""
        from src.features.infrastructure.alerts import AlertContext
        assert AlertContext is not None

    def test_import_alert_observer(self):
        """Import AlertObserver class."""
        from src.features.infrastructure.alerts import AlertObserver
        assert AlertObserver is not None

    def test_import_alert_dispatcher(self):
        """Import AlertDispatcher class."""
        from src.features.infrastructure.alerts import AlertDispatcher
        assert AlertDispatcher is not None

    def test_import_get_alert_dispatcher(self):
        """Import get_alert_dispatcher function."""
        from src.features.infrastructure.alerts import get_alert_dispatcher
        assert callable(get_alert_dispatcher)
