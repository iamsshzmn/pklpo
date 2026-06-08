"""
Smoke tests for all modules in the features package.

These tests ensure that each module can be imported without syntax errors,
import errors, or basic dependency issues.
"""

import importlib
from datetime import UTC
from pathlib import Path

import pytest

# Get the features directory
FEATURES_DIR = Path(__file__).parent.parent
FEATURES_MODULES = [
    # Core modules
    "core",
    "specs",
    "utils",
    "validators",
    "time_utils",
    "name_mapping",
    "models",
    # New modules (Stage 5 & 6)
    "logging_config",
    "metrics",
    "smoke_validation",
    "versioning",
    "database_indexes",
    "backfill",
    # Infrastructure modules
    "infrastructure.database",
    "infrastructure.indicator_registry",
    # Registry modules
    "registry.ma",
    "registry.oscillators",
    "registry.overlap",
    "registry.volatility",
    "registry.volume",
    "registry.trend",
    "registry.statistics",
    "registry.performance",
    "registry.squeeze",
    "registry.candles",
    # Indicator groups
    "indicator_groups.ma",
    "indicator_groups.oscillators",
    "indicator_groups.overlap",
    "indicator_groups.volatility",
    "indicator_groups.volume",
    "indicator_groups.trend",
    "indicator_groups.statistics",
    "indicator_groups.performance",
    "indicator_groups.squeeze",
    "indicator_groups.candles",
    "indicator_groups.data_cleaner",
    # Legacy modules
    "calc_indicators",
    "indicators_logging",
    "indicator_utils",
    # Audit modules
    "audit_simple",
    "audit_cli",
]


class TestSmokeImports:
    """Test that all modules can be imported without errors."""

    @pytest.mark.parametrize("module_name", FEATURES_MODULES)
    def test_import_module(self, module_name: str):
        """Test that a module can be imported without errors."""
        try:
            # Import the module
            module = importlib.import_module(f"src.features.{module_name}")

            # Basic checks
            assert module is not None
            assert hasattr(module, "__file__")

            # Check if module has expected attributes (basic smoke test)
            if hasattr(module, "__all__"):
                # Try to access some attributes from __all__
                for attr_name in module.__all__[:3]:  # Test first 3 attributes
                    if hasattr(module, attr_name):
                        attr = getattr(module, attr_name)
                        assert attr is not None

        except ImportError as e:
            pytest.fail(f"Failed to import {module_name}: {e}")
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {module_name}: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error importing {module_name}: {e}")

    def test_import_features_package(self):
        """Test that the main features package can be imported."""
        try:
            import src.features

            assert src.features is not None
            assert hasattr(src.features, "__version__") or hasattr(
                src.features, "__file__"
            )
        except ImportError as e:
            pytest.fail(f"Failed to import features package: {e}")

    def test_import_features_init(self):
        """Test that features __init__.py works correctly."""
        try:
            from src.features import (
                FEATURE_SPECS,
                FeatureResult,
                FeatureSpec,
                compute_features,
                validate_feature_specs_integrity,
                validate_ohlcv_data,
            )

            # Basic smoke test - check that functions are callable
            assert callable(compute_features)
            assert callable(validate_ohlcv_data)
            assert callable(validate_feature_specs_integrity)

            # Check that constants are accessible
            assert FEATURE_SPECS is not None
            assert len(FEATURE_SPECS) > 0

        except ImportError as e:
            pytest.fail(f"Failed to import from features __init__: {e}")


class TestSmokeCoreFunctionality:
    """Test basic functionality of core modules."""

    def test_core_compute_features_signature(self):
        """Test that compute_features has the expected signature."""
        import inspect

        from src.features.core import compute_features

        sig = inspect.signature(compute_features)
        params = list(sig.parameters.keys())

        # Should have basic parameters (check actual parameters from core.py)
        expected_params = ["df_ohlcv", "specs"]  # Based on actual function signature
        for param in expected_params:
            assert param in params, f"Missing parameter: {param}"

    def test_specs_feature_specs_loaded(self):
        """Test that FEATURE_SPECS is loaded and accessible."""
        from src.features.specs import FEATURE_SPECS

        assert FEATURE_SPECS is not None
        assert len(FEATURE_SPECS) > 0, "FEATURE_SPECS should not be empty"

        # Check that we can iterate over specs
        spec_count = 0
        for _spec in FEATURE_SPECS:
            spec_count += 1
            if spec_count > 5:  # Just test first few
                break

        assert spec_count > 0, "Should be able to iterate over FEATURE_SPECS"

    def test_logging_config_basic_functionality(self):
        """Test basic logging configuration functionality."""
        from src.logging import (
            get_features_logger,
            setup_features_logging,
        )

        # Test logger creation
        logger = get_features_logger("test")
        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

        # Test setup (should not raise errors)
        setup_features_logging(level="INFO", verbose=False)

    def test_metrics_collector_basic_functionality(self):
        """Test basic metrics collector functionality."""
        import pandas as pd

        from src.features.observability.metrics import FeaturesMetricsCollector

        collector = FeaturesMetricsCollector()
        assert collector is not None

        # Test with simple data
        df = pd.DataFrame(
            {
                "test_feature": [1, 2, 3, None, 5],
                "another_feature": [10, 20, 30, 40, 50],
            }
        )

        # Should not raise errors
        metrics = collector.collect_feature_quality(df, "test_feature")
        assert metrics is not None
        assert hasattr(metrics, "fill_rate")
        assert hasattr(metrics, "non_null_count")

    def test_versioning_basic_functionality(self):
        """Test basic versioning functionality."""
        from src.features.infrastructure.versioning import (
            FeaturesVersionManager,
            get_current_version,
        )

        # Test version manager
        manager = FeaturesVersionManager()
        assert manager is not None

        # Test getting versions (should not raise errors)
        schema_version = manager.get_schema_version()
        algo_version = manager.get_algorithm_version()
        params_hash = manager.get_params_hash()

        assert schema_version is not None
        assert algo_version is not None
        assert params_hash is not None

        # Test getting current version
        version_info = get_current_version()
        assert version_info is not None
        assert hasattr(version_info, "schema_version")
        assert hasattr(version_info, "algo_version")
        assert hasattr(version_info, "params_hash")

    def test_database_indexes_basic_functionality(self):
        """Test basic database indexes functionality."""
        from src.features.infrastructure.database_indexes import FeaturesIndexManager

        manager = FeaturesIndexManager()
        assert manager is not None

        # Test that methods exist and are callable
        assert hasattr(manager, "create_core_indexes")
        assert hasattr(manager, "create_feature_specific_indexes")
        assert hasattr(manager, "create_covering_indexes")
        assert hasattr(manager, "analyze_index_usage")
        assert hasattr(manager, "optimize_indexes")

        assert callable(manager.create_core_indexes)
        assert callable(manager.create_feature_specific_indexes)
        assert callable(manager.create_covering_indexes)

    def test_backfill_basic_functionality(self):
        """Test basic backfill functionality."""
        from datetime import datetime, timedelta

        from src.features.application.backfill import (
            BackfillConfig,
            FeaturesBackfillManager,
        )

        manager = FeaturesBackfillManager()
        assert manager is not None

        # Test feature flags
        flags = manager.get_feature_flags()
        assert isinstance(flags, dict)
        assert "volatility_normalize" in flags
        assert "fallback_insert" in flags

        # Test backfill config creation
        start_date = datetime.now(UTC) - timedelta(days=1)
        end_date = datetime.now(UTC)

        config = BackfillConfig(
            start_date=start_date,
            end_date=end_date,
            symbols=["BTC-USDT-SWAP"],
            timeframes=["1H"],
            dry_run=True,
        )

        assert config is not None
        assert config.symbols == ["BTC-USDT-SWAP"]
        assert config.timeframes == ["1H"]
        assert config.dry_run is True

        # Test scope estimation (should not raise errors)
        scope = manager.estimate_backfill_scope(config)
        assert scope is not None
        assert "total_estimated_records" in scope
        assert "estimated_duration_hours" in scope


class TestSmokeDataModels:
    """Test that data models can be instantiated."""

    def test_backfill_models(self):
        """Test BackfillConfig and BackfillResult models."""
        from datetime import datetime, timedelta

        from src.features.application.backfill import BackfillConfig, BackfillResult

        # Test BackfillConfig
        config = BackfillConfig(
            start_date=datetime.now(UTC) - timedelta(days=1),
            end_date=datetime.now(UTC),
            symbols=["BTC-USDT-SWAP"],
            timeframes=["1H"],
            batch_size=1000,
            parallel_workers=4,
            enable_volatility_normalize=True,
            enable_fallback_insert=True,
            dry_run=True,
        )

        assert config.symbols == ["BTC-USDT-SWAP"]
        assert config.timeframes == ["1H"]
        assert config.batch_size == 1000
        assert config.parallel_workers == 4
        assert config.enable_volatility_normalize is True
        assert config.enable_fallback_insert is True
        assert config.dry_run is True

        # Test BackfillResult
        result = BackfillResult(
            total_processed=100,
            successful=95,
            failed=5,
            duration_seconds=10.5,
            errors=["Error 1"],
            warnings=["Warning 1"],
        )

        assert result.total_processed == 100
        assert result.successful == 95
        assert result.failed == 5
        assert result.duration_seconds == 10.5
        assert result.errors == ["Error 1"]
        assert result.warnings == ["Warning 1"]

    def test_versioning_models(self):
        """Test VersionInfo model."""
        from src.features.infrastructure.versioning import VersionInfo

        version_info = VersionInfo(
            schema_version="schema_v12345678",
            algo_version="algo_v87654321",
            params_hash="params_abcdef12",
            created_at="2023-01-01T00:00:00Z",
            features_count=100,
            phase2_compliant=True,
        )

        assert version_info.schema_version == "schema_v12345678"
        assert version_info.algo_version == "algo_v87654321"
        assert version_info.params_hash == "params_abcdef12"
        assert version_info.created_at == "2023-01-01T00:00:00Z"
        assert version_info.features_count == 100
        assert version_info.phase2_compliant is True


class TestSmokeUtilities:
    """Test utility functions work correctly."""

    def test_time_utils_basic_functionality(self):
        """Test time utilities basic functionality."""

        import pandas as pd

        from src.features.utils.time_utils import (
            ensure_ts_column,
            normalize_timestamp_to_seconds,
        )

        # Test with timestamp in milliseconds
        timestamp_ms = 1640995200000  # 2022-01-01 00:00:00 UTC
        timestamp_s = normalize_timestamp_to_seconds(timestamp_ms)
        assert timestamp_s == 1640995200

        # Test with DataFrame
        df = pd.DataFrame(
            {"timestamp": [1640995200000, 1640995260000], "close": [100.0, 101.0]}
        )

        result_df = ensure_ts_column(df)
        assert "ts" in result_df.columns
        assert result_df["ts"].dtype == "int64"

    def test_validators_basic_functionality(self):
        """Test validators basic functionality."""
        import pandas as pd

        from src.features.validation.feature_validator import validate_ohlcv_data

        # Test with valid OHLCV data
        ohlcv_data = pd.DataFrame(
            {
                "timestamp": [1640995200000, 1640995260000],
                "open": [100.0, 101.0],
                "high": [102.0, 103.0],
                "low": [99.0, 100.0],
                "close": [101.0, 102.0],
                "volume": [1000, 1100],
            }
        )

        # Should not raise errors (function may return None or validation result)
        try:
            result = validate_ohlcv_data(ohlcv_data)
            # Result can be None, True, False, or validation info
            assert result is None or isinstance(result, bool | dict | str)
        except Exception as e:
            pytest.fail(f"validate_ohlcv_data should not raise exceptions: {e}")


class TestSmokeErrorHandling:
    """Test that modules handle errors gracefully."""

    def test_import_with_missing_dependencies(self):
        """Test that modules handle missing dependencies gracefully."""
        # This test ensures that modules don't crash on import
        # even if some optional dependencies are missing

        modules_to_test = [
            "src.features.core",
            "src.features.specs",
            "src.features.utils",
            "src.features.validators",
            "src.features.time_utils",
            "src.features.name_mapping",
            "src.features.logging_config",
            "src.features.metrics",
            "src.features.versioning",
            "src.features.database_indexes",
            "src.features.backfill",
        ]

        for module_name in modules_to_test:
            try:
                importlib.import_module(module_name)
            except ImportError as e:
                # Some imports might fail due to missing optional dependencies
                # This is acceptable for smoke tests
                if "No module named" in str(e):
                    # Check if it's a critical dependency
                    if any(dep in str(e) for dep in ["pandas", "numpy", "sqlalchemy"]):
                        pytest.fail(
                            f"Critical dependency missing for {module_name}: {e}"
                        )
                else:
                    pytest.fail(f"Unexpected import error for {module_name}: {e}")
            except Exception as e:
                pytest.fail(f"Unexpected error importing {module_name}: {e}")

    def test_modules_with_invalid_input(self):
        """Test that modules handle invalid input gracefully."""
        import pandas as pd

        from src.features.validation.feature_validator import validate_ohlcv_data

        # Test with invalid data (should not crash)
        invalid_data = pd.DataFrame(
            {
                "timestamp": [None, None],
                "open": [-1, -2],  # Negative prices
                "high": [0, 0],
                "low": [0, 0],
                "close": [0, 0],
                "volume": [-100, -200],  # Negative volume
            }
        )

        # Should handle invalid data gracefully
        try:
            validate_ohlcv_data(invalid_data)
            # Result might be False or contain warnings, which is acceptable
        except Exception as e:
            # Should not crash with unhandled exceptions
            if "unhandled" in str(e).lower():
                pytest.fail(f"Unhandled exception in validate_ohlcv_data: {e}")


if __name__ == "__main__":
    # Run smoke tests
    pytest.main([__file__, "-v"])
