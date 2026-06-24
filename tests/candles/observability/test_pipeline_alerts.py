from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ALERTS_PATH = (
    Path(__file__).resolve().parents[3]
    / "ops"
    / "monitoring"
    / "grafana"
    / "provisioning"
    / "alerting"
    / "pipeline_observability_alerts.yml"
)


def _rules() -> list[dict[str, Any]]:
    data = yaml.safe_load(ALERTS_PATH.read_text(encoding="utf-8"))
    return data["groups"][0]["rules"]


def _rule(uid: str) -> dict[str, Any]:
    matches = [rule for rule in _rules() if rule["uid"] == uid]
    assert len(matches) == 1
    return matches[0]


def _expr(rule: dict[str, Any]) -> str:
    return rule["data"][0]["model"]["expr"]


def test_pushgateway_staleness_alert_covers_pipeline_jobs() -> None:
    expr = _expr(_rule("pklpo-pushgateway-stale"))

    for job in {
        "dependency_health",
        "pipeline_monitoring",
        "features_pipeline",
        "swap_ohlcv_sync",
        "swap_repair_v1",
        "market_selection",
    }:
        assert job in expr


def test_onboarding_stall_alerts_are_provisioned() -> None:
    bootstrap_expr = _expr(_rule("pklpo-instrument-bootstrap-stalled"))
    warmup_expr = _expr(_rule("pklpo-instrument-warmup-stalled"))

    assert 'pklpo_pipeline_bootstrap_state_rows{status="running"}' in bootstrap_expr
    assert (
        'pklpo_feature_warmup_bars_remaining{symbol!="",timeframe!=""}' in warmup_expr
    )
    assert _rule("pklpo-instrument-bootstrap-stalled")["labels"]["severity"] == "warning"
    assert _rule("pklpo-instrument-warmup-stalled")["labels"]["severity"] == "warning"
