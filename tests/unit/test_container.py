"""Unit tests for the public bootstrap contract."""

from src.features.bootstrap import (
    FeatureAirflowCallbacks,
    FeatureApplicationBootstrap,
    FeatureSaveDependencies,
    create_feature_airflow_callbacks,
    create_feature_application_bootstrap,
    create_feature_save_dependencies,
)


class TestFeatureBootstrap:
    """Tests for the public composition root."""

    def test_create_feature_application_bootstrap_returns_public_bundle(self):
        """Bootstrap factory returns the bounded-context dependency bundle."""
        bootstrap = create_feature_application_bootstrap()

        assert isinstance(bootstrap, FeatureApplicationBootstrap)
        assert hasattr(bootstrap.storage_gateway, "fetch_latest_ts")
        assert hasattr(bootstrap.storage_gateway, "fetch_ohlcv_df")
        assert hasattr(bootstrap.storage_gateway, "ensure_indicator_columns")
        assert callable(getattr(bootstrap.schema_ddl_port, "ensure_columns", None))
        assert callable(bootstrap.save_dependencies_factory)
        assert callable(bootstrap.partition_manager_factory)
        assert callable(bootstrap.quality_pipeline_runner)

    def test_create_feature_application_bootstrap_returns_fresh_bundles(self):
        """Each bootstrap factory call returns an isolated dependency bundle."""
        first = create_feature_application_bootstrap()
        second = create_feature_application_bootstrap()

        assert first is not second
        assert first.storage_gateway is not second.storage_gateway
        assert first.schema_ddl_port is not second.schema_ddl_port
        assert first.quality_pipeline_runner is not second.quality_pipeline_runner

    def test_create_feature_save_dependencies_uses_repository_contract(self):
        """Save dependencies are assembled through the public bootstrap module."""
        session = object()

        dependencies = create_feature_save_dependencies(session)

        assert isinstance(dependencies, FeatureSaveDependencies)
        assert callable(getattr(dependencies.repository, "save_batch", None))
        assert callable(getattr(dependencies.repository, "save_batch_from_df", None))
        assert dependencies.repository._session is session
        assert dependencies.validator is not None
        assert dependencies.observer is not None

    def test_create_feature_airflow_callbacks_returns_public_bundle(self):
        """Airflow callback wiring is exposed via the public bootstrap module."""
        callbacks = create_feature_airflow_callbacks()

        assert isinstance(callbacks, FeatureAirflowCallbacks)
        assert callable(callbacks.on_failure_callback)
        assert callable(callbacks.sla_miss_callback)
        assert callable(callbacks.on_success_callback)
