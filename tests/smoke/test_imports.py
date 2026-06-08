"""Smoke tests for the public features boundary."""

import pytest


@pytest.mark.smoke
class TestPublicApiImports:
    """Test public API imports."""

    def test_import_main_package(self):
        """Import main features package."""
        from src import features

        assert features is not None

    def test_import_compute_features(self):
        """Import compute_features from the public API."""
        from src.features.api import compute_features

        assert callable(compute_features)

    def test_import_public_api(self):
        """Import the external API facade."""
        from src.features.api import create_feature_service

        assert callable(create_feature_service)

    def test_import_public_bootstrap(self):
        """Import the public composition root."""
        from src.features.bootstrap import create_feature_application_bootstrap

        assert callable(create_feature_application_bootstrap)


class TestFeatureServiceImports:
    """Test service-related symbols available through the public API."""

    def test_import_feature_calculation_service(self):
        """Import FeatureCalculationService from the public API."""
        from src.features.api import FeatureCalculationService

        assert FeatureCalculationService is not None

    def test_import_default_ohlcv_validator(self):
        """Import DefaultOHLCVValidator from the public API."""
        from src.features.api import DefaultOHLCVValidator

        assert DefaultOHLCVValidator is not None

    def test_import_default_feature_normalizer(self):
        """Import DefaultFeatureNormalizer from the public API."""
        from src.features.api import DefaultFeatureNormalizer

        assert DefaultFeatureNormalizer is not None

    def test_import_create_feature_service(self):
        """Import create_feature_service from the public API."""
        from src.features.api import create_feature_service

        assert callable(create_feature_service)


@pytest.mark.smoke
class TestBootstrapImports:
    """Test public bootstrap helpers."""

    def test_import_bootstrap_bundle(self):
        """Import FeatureApplicationBootstrap from bootstrap."""
        from src.features.bootstrap import FeatureApplicationBootstrap

        assert FeatureApplicationBootstrap is not None

    def test_import_bootstrap_factory(self):
        """Import create_feature_application_bootstrap from bootstrap."""
        from src.features.bootstrap import create_feature_application_bootstrap

        assert callable(create_feature_application_bootstrap)

    def test_import_airflow_callbacks_factory(self):
        """Import create_feature_airflow_callbacks from bootstrap."""
        from src.features.bootstrap import create_feature_airflow_callbacks

        assert callable(create_feature_airflow_callbacks)
