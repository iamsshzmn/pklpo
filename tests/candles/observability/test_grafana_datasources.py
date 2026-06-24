from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GRAFANA_DIR = PROJECT_ROOT / "ops" / "monitoring" / "grafana"
DATASOURCE_DIR = GRAFANA_DIR / "provisioning" / "datasources"
DASHBOARD_DIR = GRAFANA_DIR / "dashboards"
ALERTING_DIR = GRAFANA_DIR / "provisioning" / "alerting"


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def test_grafana_datasource_uids_are_stable_literals() -> None:
    prometheus = _load_yaml(DATASOURCE_DIR / "prometheus.yml")["datasources"][0]
    loki = _load_yaml(DATASOURCE_DIR / "loki.yml")["datasources"][0]
    tempo = _load_yaml(DATASOURCE_DIR / "tempo.yml")["datasources"][0]

    assert prometheus["name"] == "Prometheus"
    assert prometheus["uid"] == "Prometheus"
    assert loki["name"] == "Loki"
    assert loki["uid"] == "Loki"
    assert tempo["name"] == "Tempo"
    assert tempo["uid"] == "Tempo"
    assert tempo["url"] == "http://tempo:3200"


def test_loki_datasource_links_trace_id_to_tempo() -> None:
    loki = _load_yaml(DATASOURCE_DIR / "loki.yml")["datasources"][0]
    derived_fields = {
        field["name"]: field for field in loki["jsonData"]["derivedFields"]
    }

    assert derived_fields["run_id"]["datasourceUid"] == ""
    assert derived_fields["trace_id"]["datasourceUid"] == "Tempo"
    assert derived_fields["trace_id"]["url"] == "$${__value.raw}"
    assert "trace_id" in derived_fields["trace_id"]["matcherRegex"]
    assert "run_id" in derived_fields["run_id"]["matcherRegex"]


def test_grafana_dashboards_reference_stable_datasource_uids() -> None:
    for dashboard_path in DASHBOARD_DIR.glob("*.json"):
        dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
        datasource_uids = {
            item["uid"]
            for item in _walk(dashboard)
            if isinstance(item.get("uid"), str)
            and item.get("type") in {"prometheus", "loki", "tempo"}
        }

        assert not datasource_uids - {
            "Prometheus",
            "Loki",
            "Tempo",
            "${DS_PROMETHEUS}",
            "${DS_LOKI}",
            "${DS_TEMPO}",
        }


def test_grafana_alert_rules_reference_stable_datasource_uids() -> None:
    for alert_path in ALERTING_DIR.glob("*.yml"):
        alerting = _load_yaml(alert_path)
        datasource_uids = {
            item["datasourceUid"]
            for item in _walk(alerting)
            if isinstance(item.get("datasourceUid"), str)
        }

        assert not datasource_uids - {"Prometheus", "Loki", "Tempo", "__expr__"}


def test_operator_docs_describe_run_id_to_trace_id_to_tempo_workflow() -> None:
    readme = (PROJECT_ROOT / "ops" / "monitoring" / "README.md").read_text(
        encoding="utf-8"
    )
    runbook = (PROJECT_ROOT / "ops" / "monitoring" / "LOGS_RUNBOOK.md").read_text(
        encoding="utf-8"
    )

    for content in (readme, runbook):
        assert "run_id" in content
        assert "trace_id" in content
        assert "Tempo" in content


def test_pipeline_dashboard_log_panel_mentions_trace_links() -> None:
    dashboard = json.loads(
        (DASHBOARD_DIR / "pipeline_observability.json").read_text(encoding="utf-8")
    )
    log_panels = [panel for panel in dashboard["panels"] if panel.get("type") == "logs"]

    assert any(
        "trace_id" in panel.get("description", "")
        and "Tempo" in panel.get("description", "")
        for panel in log_panels
    )
