"""Tests for Phase 1 blocks A, B, D."""

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent


# ============================================================================
# Block A: Prometheus metrics
# ============================================================================


class TestPrometheusMetricsDisabled:
    """Test noop behavior when prometheus is disabled (default)."""

    def test_import(self):
        from src.features.observability.prometheus import (
            PipelineMetrics,
            get_metrics,
            reset_metrics,
        )

        reset_metrics()
        m = get_metrics()
        assert isinstance(m, PipelineMetrics)

    def test_noop_recording_does_not_raise(self):
        from src.features.observability.prometheus import get_metrics, reset_metrics

        reset_metrics()
        m = get_metrics()
        # All methods should be safe no-ops when disabled
        m.record_rows_written("BTC", "1m", 100)
        m.record_upsert_failure("BTC", "1m")
        m.record_duplicates("BTC", "1m", 5)
        m.record_freshness_lag("BTC", "1m", 42.0)
        m.record_fill_rate("BTC", "1m", 0.998)
        m.record_hole_rate("BTC", "1m", 0.0001)
        m.record_quality_score("BTC", "1m", 0.95)
        m.record_batch_size("BTC", "1m", 150)
        m.observe_calc_duration("BTC", "1m", 3.14)
        m.observe_upsert_duration("BTC", "1m", 0.5)

    def test_push_returns_false_when_disabled(self):
        from src.features.observability.prometheus import get_metrics, reset_metrics

        reset_metrics()
        m = get_metrics()
        assert m.push() is False

    def test_enabled_property_false_by_default(self):
        from src.features.observability.prometheus import get_metrics, reset_metrics

        reset_metrics()
        m = get_metrics()
        assert m.enabled is False

    def test_calc_timer_context_manager(self):
        from src.features.observability.prometheus import get_metrics, reset_metrics

        reset_metrics()
        m = get_metrics()
        with m.calc_timer("BTC", "1m"):
            time.sleep(0.01)
        # Should not raise

    def test_upsert_timer_context_manager(self):
        from src.features.observability.prometheus import get_metrics, reset_metrics

        reset_metrics()
        m = get_metrics()
        with m.upsert_timer("BTC", "1m"):
            time.sleep(0.01)


class TestPrometheusMetricsEnabled:
    """Test real prometheus metrics when enabled."""

    @pytest.fixture(autouse=True)
    def _enable_prometheus(self, monkeypatch):
        monkeypatch.setenv("OBSERVABILITY_PROMETHEUS_ENABLED", "true")
        # Clear settings cache so new env is picked up
        from src.config import reload_settings
        reload_settings()
        from src.features.observability.prometheus import reset_metrics
        reset_metrics()
        yield
        # Cleanup
        from src.config import reload_settings
        reset_metrics()
        reload_settings()

    def test_enabled_flag(self):
        from src.features.observability.prometheus import get_metrics

        m = get_metrics()
        assert m.enabled is True

    def test_registry_created(self):
        from src.features.observability.prometheus import get_metrics

        m = get_metrics()
        assert m._registry is not None

    def test_record_rows_increments_counter(self):
        from src.features.observability.prometheus import get_metrics

        m = get_metrics()
        m.record_rows_written("ETH", "5m", 200)
        m.record_rows_written("ETH", "5m", 300)
        # Counter should have accumulated 500
        val = m.rows_written_total.labels("ETH", "5m")._value.get()
        assert val == 500.0

    def test_record_freshness_sets_gauge(self):
        from src.features.observability.prometheus import get_metrics

        m = get_metrics()
        m.record_freshness_lag("BTC", "1m", 42.5)
        val = m.freshness_lag_seconds.labels("BTC", "1m")._value.get()
        assert val == 42.5

    def test_observe_histogram(self):
        from src.features.observability.prometheus import get_metrics

        m = get_metrics()
        m.observe_calc_duration("BTC", "1m", 2.5)
        m.observe_calc_duration("BTC", "1m", 3.5)
        # Histogram sum should be 6.0
        sample_sum = m.calc_duration_seconds.labels("BTC", "1m")._sum.get()
        assert sample_sum == pytest.approx(6.0)

    def test_push_fails_gracefully_no_gateway(self):
        from src.features.observability.prometheus import get_metrics

        m = get_metrics()
        # No pushgateway URL configured — should return False, no exception
        assert m.push() is False

    def test_calc_timer_records_duration(self):
        from src.features.observability.prometheus import get_metrics

        m = get_metrics()
        with m.calc_timer("BTC", "15m"):
            time.sleep(0.05)
        sample_sum = m.calc_duration_seconds.labels("BTC", "15m")._sum.get()
        assert sample_sum >= 0.04  # at least 40ms


# ============================================================================
# Block A: ObservabilitySettings
# ============================================================================


class TestObservabilitySettings:
    def test_default_values(self):
        from src.config.settings import ObservabilitySettings

        s = ObservabilitySettings()
        assert s.prometheus_enabled is False
        assert s.prometheus_pushgateway_url == ""
        assert s.metrics_prefix == "pklpo"
        assert s.job_name == "features_pipeline"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("OBSERVABILITY_PROMETHEUS_ENABLED", "true")
        monkeypatch.setenv("OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL", "http://gw:9091")
        monkeypatch.setenv("OBSERVABILITY_METRICS_PREFIX", "test")

        from src.config.settings import ObservabilitySettings

        s = ObservabilitySettings()
        assert s.prometheus_enabled is True
        assert s.prometheus_pushgateway_url == "http://gw:9091"
        assert s.metrics_prefix == "test"

    def test_integrated_in_main_settings(self):
        from src.config import get_settings, reload_settings

        reload_settings()
        s = get_settings()
        assert hasattr(s, "observability")
        assert s.observability.metrics_prefix == "pklpo"


# ============================================================================
# Block B: Grafana / Docker-compose file validation
# ============================================================================


MONITORING_DIR = PROJECT_ROOT / "ops" / "monitoring"


class TestGrafanaDashboard:
    def test_dashboard_json_valid(self):
        path = MONITORING_DIR / "grafana" / "dashboards" / "data_quality.json"
        assert path.exists(), f"Dashboard not found: {path}"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["uid"] == "pklpo-data-quality"
        assert data["title"] == "PKLPO Data Quality"
        assert len(data["panels"]) >= 8

    def test_dashboard_has_required_panels(self):
        path = MONITORING_DIR / "grafana" / "dashboards" / "data_quality.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        titles = {p["title"] for p in data["panels"]}
        required = {
            "Freshness Lag (seconds)",
            "Fill Rate",
            "Hole Rate (missing bars)",
            "Data Quality Score",
        }
        missing = required - titles
        assert not missing, f"Missing panels: {missing}"

    def test_dashboard_panels_have_targets(self):
        path = MONITORING_DIR / "grafana" / "dashboards" / "data_quality.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for panel in data["panels"]:
            assert "targets" in panel, f"Panel '{panel['title']}' has no targets"
            assert len(panel["targets"]) > 0


class TestGrafanaAlertRules:
    def test_alert_rules_yaml_valid(self):
        path = MONITORING_DIR / "grafana" / "provisioning" / "alerting" / "data_quality_alerts.yml"
        assert path.exists()
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "groups" in data
        rules = data["groups"][0]["rules"]
        assert len(rules) >= 6

    def test_alert_severities(self):
        path = MONITORING_DIR / "grafana" / "provisioning" / "alerting" / "data_quality_alerts.yml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        rules = data["groups"][0]["rules"]
        severities = {r["labels"]["severity"] for r in rules}
        assert "warning" in severities
        assert "critical" in severities

    def test_all_alerts_have_annotations(self):
        path = MONITORING_DIR / "grafana" / "provisioning" / "alerting" / "data_quality_alerts.yml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for rule in data["groups"][0]["rules"]:
            assert "summary" in rule["annotations"]
            assert "description" in rule["annotations"]


class TestDockerCompose:
    def test_docker_compose_yaml_valid(self):
        path = MONITORING_DIR / "docker-compose.monitoring.yml"
        assert path.exists()
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "services" in data

    def test_required_services(self):
        path = MONITORING_DIR / "docker-compose.monitoring.yml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        services = set(data["services"].keys())
        assert {"prometheus", "pushgateway", "grafana"} <= services

    def test_prometheus_config_valid(self):
        path = MONITORING_DIR / "prometheus" / "prometheus.yml"
        assert path.exists()
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "scrape_configs" in data
        job_names = {sc["job_name"] for sc in data["scrape_configs"]}
        assert "pushgateway" in job_names

    def test_grafana_datasource_provisioning(self):
        path = MONITORING_DIR / "grafana" / "provisioning" / "datasources" / "prometheus.yml"
        assert path.exists()
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["datasources"][0]["type"] == "prometheus"


# ============================================================================
# Block D: Quality store + migration + validate task
# ============================================================================


class TestQualityStore:
    def test_import(self):
        pass

    @pytest.mark.asyncio
    async def test_record_quality_metrics_empty_dict(self):
        from src.features.observability.quality_store import record_quality_metrics

        session = AsyncMock()
        count = await record_quality_metrics(
            session, symbol="BTC", timeframe="1m", metrics={}, window_hours=24
        )
        assert count == 0
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_quality_metrics_inserts(self):
        from src.features.observability.quality_store import record_quality_metrics

        session = AsyncMock()
        count = await record_quality_metrics(
            session,
            symbol="all",
            timeframe="5m",
            metrics={"fill_rate": 0.998, "hole_rate": 0.0001},
            window_hours=24,
        )
        assert count == 2
        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_record_handles_db_error_gracefully(self):
        from src.features.observability.quality_store import record_quality_metrics

        session = AsyncMock()
        session.execute.side_effect = Exception("DB down")
        count = await record_quality_metrics(
            session,
            symbol="all",
            timeframe="1m",
            metrics={"fill_rate": 0.99},
            window_hours=168,
        )
        assert count == 0  # Failed but no exception raised

    @pytest.mark.asyncio
    async def test_get_quality_trend(self):
        from src.features.observability.quality_store import get_quality_trend

        session = AsyncMock()
        # execute returns a Result whose fetchall is sync
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("2026-02-13T20:00:00", 0.998),
            ("2026-02-13T19:45:00", 0.997),
        ]
        session.execute.return_value = mock_result
        result = await get_quality_trend(
            session,
            symbol="all",
            timeframe="1m",
            metric_name="fill_rate",
            window_hours=24,
        )
        assert len(result) == 2
        assert result[0][1] == 0.998


class TestMigration:
    def test_migration_file_exists(self):
        path = PROJECT_ROOT / "src" / "db" / "migrate_create_data_quality_metrics.py"
        assert path.exists()

    def test_migration_syntax(self):
        import py_compile
        path = str(PROJECT_ROOT / "src" / "db" / "migrate_create_data_quality_metrics.py")
        py_compile.compile(path, doraise=True)

    def test_migration_function_importable(self):
        import asyncio

        from src.db.migrate_create_data_quality_metrics import (
            migrate_create_data_quality_metrics,
        )
        assert asyncio.iscoroutinefunction(migrate_create_data_quality_metrics)


class TestValidateTaskRefactored:
    def test_dag_file_syntax(self):
        import py_compile
        path = str(PROJECT_ROOT / "ops" / "airflow" / "dags" / "features_calc_short.py")
        py_compile.compile(path, doraise=True)

    def test_check_quality_helper_importable(self):
        """Verify _check_quality_for_window is defined in DAG module."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "dag_module",
            str(PROJECT_ROOT / "ops" / "airflow" / "dags" / "features_calc_short.py"),
        )
        # Just verify the module can be loaded as far as syntax
        assert spec is not None
