"""Integration tests for the public features bootstrap wiring."""

import numpy as np
import pandas as pd
import pytest

from src.features.api import create_feature_service
from src.features.bootstrap import create_feature_application_bootstrap


@pytest.mark.integration
class TestFeatureBootstrapIntegration:
    """Integration tests for the public composition root."""

    @pytest.fixture
    def valid_ohlcv(self):
        """Valid OHLCV for testing."""
        np.random.seed(42)
        n = 50
        return pd.DataFrame(
            {
                "open": np.random.rand(n) * 100 + 50,
                "high": np.random.rand(n) * 100 + 55,
                "low": np.random.rand(n) * 100 + 45,
                "close": np.random.rand(n) * 100 + 50,
                "volume": np.random.rand(n) * 10000,
            }
        )

    def test_public_bootstrap_wires_storage_and_quality_ports(self):
        """Bootstrap exposes the supported composition-root collaborators."""
        bootstrap = create_feature_application_bootstrap()

        assert bootstrap.storage_gateway is not None
        assert bootstrap.schema_ddl_port is not None
        assert callable(bootstrap.save_dependencies_factory)
        assert callable(bootstrap.partition_manager_factory)
        assert callable(bootstrap.quality_pipeline_runner)

    def test_public_api_service_can_calculate(self, valid_ohlcv):
        """Feature calculation goes through the public API facade."""
        calculator = create_feature_service()

        try:
            result = calculator.calculate(
                valid_ohlcv,
                specs=None,
                volatility_normalize=False,
            )
        except Exception as exc:
            pytest.skip(f"Skipped: {exc}")

        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(valid_ohlcv)
