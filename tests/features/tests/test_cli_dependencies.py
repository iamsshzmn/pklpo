"""
Test CLI and pipeline dependencies.

These tests verify that all imports required for the CLI commands
and Airflow DAG work correctly. No actual calculations are performed.
"""

import pytest


class TestCLIDependencies:
    """Test that CLI command imports work correctly."""

    def test_features_command_imports(self):
        """Test all imports used by src/cli/commands/features.py"""
        # Standard library

        # Third-party

        # Features module imports
        from src.features import compute_features
        from src.features.infrastructure.database import (
            insert_indicators as infra_insert_indicators,
        )
        from src.features.specs import FEATURE_SPECS
        from src.logging import (
            get_features_logger,
            log_features_summary,
        )

        # Utils
        from src.utils.session_utils import get_db_session

        # Verify callables
        assert callable(compute_features)
        assert callable(infra_insert_indicators)
        assert callable(get_features_logger)
        assert callable(log_features_summary)
        assert callable(get_db_session)

        # Verify FEATURE_SPECS
        assert FEATURE_SPECS is not None
        assert len(FEATURE_SPECS) > 0, "FEATURE_SPECS should not be empty"

    def test_features_command_handle(self):
        """Test that handle function can be imported from features command."""
        from src.cli.commands.features import handle, register

        assert callable(handle)
        assert callable(register)

    def test_features_core_api(self):
        """Test core features API is accessible."""
        from src.features import compute_features
        from src.features.core import compute_features as core_compute_features
        from src.features.specs import FEATURE_SPECS

        # Should be the same function
        assert compute_features is core_compute_features

        # Check specs count
        assert len(FEATURE_SPECS) == 177, (
            f"Expected 177 specs, got {len(FEATURE_SPECS)}"
        )


class TestConfigDependencies:
    """Test configuration dependencies."""

    def test_config_imports(self):
        """Test src.config imports."""
        from src.config import FeaturesSettings, get_settings

        assert callable(get_settings)
        assert FeaturesSettings is not None

    def test_features_config(self):
        """Test features-specific config."""
        from src.features.config.settings import (
            create_streaming_config,
            load_config_from_env,
        )

        # Test config loading
        env_config = load_config_from_env()
        assert isinstance(env_config, dict)

        # Test streaming config creation
        streaming_config = create_streaming_config()
        assert streaming_config is not None


class TestModelsDependencies:
    """Test ORM model dependencies."""

    def test_models_imports(self):
        """Test src.models imports."""
        from src.models import OHLCV, Indicator

        assert Indicator is not None
        assert OHLCV is not None

        # Check table names exist
        assert hasattr(Indicator, "__tablename__")
        assert hasattr(OHLCV, "__tablename__")


class TestDatabaseDependencies:
    """Test database dependencies."""

    def test_database_imports(self):
        """Test src.database imports."""
        from src.database import get_async_session

        assert callable(get_async_session)

    def test_features_database_imports(self):
        """Test features infrastructure database imports."""
        from src.features.infrastructure.database import insert_indicators

        assert callable(insert_indicators)


class TestObservabilityDependencies:
    """Test logging and metrics dependencies."""

    def test_logging_imports(self):
        """Test logging imports."""
        from src.logging import (
            get_features_logger,
            log_features_summary,
            setup_features_logging,
        )

        assert callable(get_features_logger)
        assert callable(log_features_summary)
        assert callable(setup_features_logging)

        # Test logger creation
        logger = get_features_logger("test")
        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")

    def test_metrics_imports(self):
        """Test metrics imports."""
        from src.features.observability.metrics import FeaturesMetricsCollector

        collector = FeaturesMetricsCollector()
        assert collector is not None


class TestApplicationDependencies:
    """Test application layer dependencies."""

    def test_calc_imports(self):
        """Test calc module imports."""
        from src.features.application.calc import process_chunks

        assert callable(process_chunks)

    def test_save_imports(self):
        """Test save module imports."""
        from src.features.application.save import save_parquet_to_pg

        assert callable(save_parquet_to_pg)

    def test_backfill_imports(self):
        """Test backfill module imports."""
        from src.features.application.backfill import (
            BackfillConfig,
            FeaturesBackfillManager,
        )

        assert BackfillConfig is not None
        assert FeaturesBackfillManager is not None


class TestInfrastructureDependencies:
    """Test infrastructure layer dependencies."""

    def test_versioning_imports(self):
        """Test versioning imports."""
        from src.features.infrastructure.versioning import (
            FeaturesVersionManager,
            get_current_version,
        )

        assert callable(get_current_version)
        assert FeaturesVersionManager is not None

    def test_db_operations_imports(self):
        """Test db_operations imports."""
        from src.features.infrastructure.db_operations import (
            fetch_latest_ts,
            fetch_ohlcv_df,
        )

        assert callable(fetch_latest_ts)
        assert callable(fetch_ohlcv_df)


class TestSpecsDependencies:
    """Test specs module dependencies."""

    def test_all_spec_modules(self):
        """Test all spec submodules can be imported."""
        from src.features.specs import (
            candles,
            ma,
            oscillators,
            overlap,
            performance,
            statistics,
            trend,
            volatility,
            volume,
        )

        modules = [
            candles,
            ma,
            oscillators,
            overlap,
            performance,
            statistics,
            trend,
            volatility,
            volume,
        ]
        for mod in modules:
            assert mod is not None

    def test_feature_specs_structure(self):
        """Test FEATURE_SPECS has expected structure."""
        from src.features.specs import FEATURE_SPECS

        # Check a few known specs exist
        known_specs = ["rsi_14", "ema_21", "macd", "atr_14", "obv", "sma_50"]
        for spec_name in known_specs:
            assert spec_name in FEATURE_SPECS, f"Missing spec: {spec_name}"

        # Check spec has required attributes
        spec = FEATURE_SPECS["rsi_14"]
        assert hasattr(spec, "name")
        assert hasattr(spec, "type")
        assert spec.name == "rsi_14"


class TestCircularDependencies:
    """Test no circular import issues."""

    def test_no_circular_imports(self):
        """Test that importing features and cli together works."""
        import src.cli
        import src.features

        assert src.features is not None
        assert src.cli is not None

    def test_cli_features_bidirectional(self):
        """Test bidirectional imports between cli and features."""
        # Import in one order
        from src.cli.commands.features import handle
        from src.features import compute_features

        # Both should work
        assert callable(handle)
        assert callable(compute_features)


class TestUtilsDependencies:
    """Test utility dependencies."""

    def test_session_utils(self):
        """Test session utils imports."""
        from src.utils.session_utils import get_db_session

        assert callable(get_db_session)

    def test_db_schema_utils(self):
        """Test db schema utils imports."""
        from src.db.db_schema_utils import ensure_columns

        assert callable(ensure_columns)


class TestFullPipelineImports:
    """Test complete pipeline can be imported."""

    def test_full_pipeline_imports(self):
        """Test all imports needed for a full pipeline run."""
        # This mimics what Airflow DAG would need to import

        # Config
        # CLI command
        from src.cli.commands.features import handle
        from src.config import get_settings

        # Database
        from src.database import get_async_session

        # Features core
        from src.features import compute_features

        # Features application
        from src.features.application.calc import process_chunks
        from src.features.application.save import save_parquet_to_pg

        # Features infrastructure
        from src.features.infrastructure.database import insert_indicators
        from src.features.infrastructure.versioning import get_current_version
        from src.features.observability.metrics import FeaturesMetricsCollector
        from src.features.specs import FEATURE_SPECS

        # Observability
        from src.logging import get_features_logger
        from src.utils.session_utils import get_db_session

        # Verify all imports work
        assert callable(get_settings)
        assert callable(get_async_session)
        assert callable(get_db_session)
        assert callable(compute_features)
        assert len(FEATURE_SPECS) > 0
        assert callable(process_chunks)
        assert callable(save_parquet_to_pg)
        assert callable(insert_indicators)
        assert callable(get_current_version)
        assert callable(get_features_logger)
        assert FeaturesMetricsCollector is not None
        assert callable(handle)

        print(f"All pipeline imports OK. FEATURE_SPECS count: {len(FEATURE_SPECS)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
