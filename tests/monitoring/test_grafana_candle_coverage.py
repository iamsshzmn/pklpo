import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = ROOT / "ops/monitoring/grafana/dashboards/pklpo-candle-coverage.json"
DATASOURCE = (
    ROOT / "ops/monitoring/grafana/provisioning/datasources/postgres.yml"
)
COMPOSE = ROOT / "ops/monitoring/docker-compose.monitoring.yml"
ROLE_SQL = ROOT / "ops/monitoring/grafana/sql/create_grafana_ro_role.sql"
ENV_EXAMPLE = ROOT / ".env.example"


def test_postgres_datasource_is_provisioned_from_env() -> None:
    data = yaml.safe_load(DATASOURCE.read_text(encoding="utf-8"))

    datasource = data["datasources"][0]
    assert datasource["name"] == "PostgresPKLPO"
    assert datasource["uid"] == "PostgresPKLPO"
    assert datasource["type"] == "postgres"
    assert datasource["access"] == "proxy"
    assert datasource["url"] == "${GRAFANA_PG_HOST}:${GRAFANA_PG_PORT}"
    assert datasource["user"] == "${GRAFANA_PG_USER}"
    assert datasource["secureJsonData"]["password"] == "${GRAFANA_PG_PASSWORD}"
    assert datasource["jsonData"]["database"] == "${GRAFANA_PG_DB}"
    assert datasource["jsonData"]["postgresVersion"] == 1600
    assert datasource["jsonData"]["sslmode"] == "disable"
    assert datasource["editable"] is False


def test_grafana_compose_exposes_readonly_postgres_env() -> None:
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    env = compose["services"]["grafana"]["environment"]

    assert env["GRAFANA_PG_USER"] == "${GRAFANA_PG_USER:-grafana_ro}"
    assert env["GRAFANA_PG_PASSWORD"] == "${GRAFANA_PG_PASSWORD:-CHANGE_ME}"
    assert env["GRAFANA_PG_HOST"] == "${GRAFANA_PG_HOST:-pklpo_db}"
    assert env["GRAFANA_PG_PORT"] == "${GRAFANA_PG_PORT:-5432}"
    assert env["GRAFANA_PG_DB"] == "${GRAFANA_PG_DB:-pklpo}"

    env_example = ENV_EXAMPLE.read_text(encoding="utf-8")
    for name in (
        "GRAFANA_PG_USER",
        "GRAFANA_PG_PASSWORD",
        "GRAFANA_PG_HOST",
        "GRAFANA_PG_PORT",
        "GRAFANA_PG_DB",
    ):
        assert name in env_example


def test_readonly_role_script_is_idempotent_and_select_only() -> None:
    sql = ROLE_SQL.read_text(encoding="utf-8")

    assert "CREATE ROLE grafana_ro LOGIN PASSWORD" in sql
    assert "GRANT CONNECT ON DATABASE pklpo TO grafana_ro" in sql
    assert "GRANT USAGE ON SCHEMA public TO grafana_ro" in sql
    assert "GRANT USAGE ON SCHEMA ops TO grafana_ro" in sql
    assert "GRANT SELECT ON TABLE public.swap_ohlcv_p TO grafana_ro" in sql
    assert (
        "GRANT SELECT ON TABLE ops.pipeline_recovery_decisions TO grafana_ro" in sql
    )
    assert "GRANT INSERT" not in sql
    assert "GRANT UPDATE" not in sql
    assert "GRANT DELETE" not in sql


def test_candle_coverage_dashboard_has_expected_variables_and_panels() -> None:
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))

    assert dashboard["uid"] == "pklpo-candle-coverage"
    assert dashboard["title"] == "PKLPO Candle Coverage (test)"
    assert dashboard["timezone"] == "utc"
    assert dashboard["refresh"] == "5m"
    assert dashboard["tags"] == ["pklpo", "data-quality", "test"]

    variables = {item["name"]: item for item in dashboard["templating"]["list"]}
    assert variables["DS_POSTGRES"]["type"] == "datasource"
    assert variables["DS_POSTGRES"]["query"] == "postgres"
    assert variables["symbol"]["query"] == (
        "SELECT DISTINCT symbol FROM swap_ohlcv_p ORDER BY 1"
    )
    assert variables["symbol"]["includeAll"] is True
    assert variables["symbol"]["multi"] is True
    assert variables["bars_back"]["type"] == "textbox"
    assert variables["bars_back"]["current"]["value"] == "200"

    panels = {panel["title"]: panel for panel in dashboard["panels"]}
    assert set(panels) == {
        "Candle Coverage by Symbol",
        "Candle Coverage by Timeframe",
        "Recovery Lifecycle Buckets",
    }

    detail_sql = panels["Candle Coverage by Symbol"]["targets"][0]["rawSql"]
    summary_sql = panels["Candle Coverage by Timeframe"]["targets"][0]["rawSql"]
    for sql in (detail_sql, summary_sql):
        assert "'1H', 3600000::bigint" in sql
        assert "'4H', 14400000::bigint" in sql
        assert "date_trunc('day', now() AT TIME ZONE 'UTC')" in sql
        assert "date_trunc('week', now() AT TIME ZONE 'UTC')" in sql
        assert "date_trunc('month', now() AT TIME ZONE 'UTC')" in sql
        assert "LEFT JOIN swap_ohlcv_p o" in sql
        assert "o.timestamp = e.expected_ts_ms" in sql
        assert "${symbol:singlequote}" in sql

    assert "ORDER BY fill_pct ASC" in detail_sql
    assert "GROUP BY timeframe" in summary_sql

    lifecycle_sql = panels["Recovery Lifecycle Buckets"]["targets"][0]["rawSql"]
    assert "ops.pipeline_recovery_decisions" in lifecycle_sql
    assert "instrument_not_live" in lifecycle_sql
    assert "instrument_state_unknown" in lifecycle_sql
    assert "bootstrap_state_missing" in lifecycle_sql
    assert "new_live_no_bootstrap" in lifecycle_sql
    assert "expired_terminal" in lifecycle_sql
    assert "GROUP BY lifecycle_bucket" in lifecycle_sql
    assert "ORDER BY decisions DESC" in lifecycle_sql
