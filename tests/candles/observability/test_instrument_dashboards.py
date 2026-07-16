"""Grafana contracts for instrument onboarding/drilldown dashboards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DASHBOARD_DIR = _PROJECT_ROOT / "ops" / "monitoring" / "grafana" / "dashboards"


def _load_dashboard(name: str) -> dict[str, Any]:
    return json.loads((_DASHBOARD_DIR / name).read_text(encoding="utf-8"))


def _target_exprs(dashboard: dict[str, Any]) -> list[str]:
    exprs: list[str] = []
    for panel in dashboard["panels"]:
        for target in panel.get("targets", []):
            expr = target.get("expr")
            if expr:
                exprs.append(expr)
    return exprs


def _panel_titles(dashboard: dict[str, Any]) -> set[str]:
    return {panel["title"] for panel in dashboard["panels"]}


def test_instrument_onboarding_dashboard_contract() -> None:
    dashboard = _load_dashboard("pklpo-instrument-onboarding.json")

    assert dashboard["uid"] == "pklpo-instrument-onboarding"
    assert dashboard["title"] == "PKLPO Instrument Onboarding"
    assert len([p for p in dashboard["panels"] if p.get("type") != "row"]) == 7

    titles = _panel_titles(dashboard)
    assert {
        "Bootstrap Progress",
        "Eligibility Funnel",
        "Eligibility Transitions",
        "Warm-up Transitions",
        "Eligible Symbols",
        "Universe Size",
        "Eligibility Staleness",
    } <= titles

    exprs = "\n".join(_target_exprs(dashboard))
    assert "pklpo_pipeline_bootstrap_state_rows" in exprs
    assert "sum by (state) (pklpo_feature_eligibility_symbols" in exprs
    assert (
        "sum by (to_state) (increase(pklpo_feature_eligibility_transitions_total[1h]))"
        in exprs
    )
    assert 'from_state="insufficient_history",to_state="eligible"' in exprs
    assert "pklpo_feature_eligible_total" in exprs
    assert "pklpo_market_selection_universe_size" in exprs
    assert "pklpo_market_selection_eligible_count" in exprs
    assert "pklpo_feature_eligibility_stale_seconds" in exprs


def test_instrument_drilldown_dashboard_contract() -> None:
    dashboard = _load_dashboard("pklpo-instrument-drilldown.json")

    assert dashboard["uid"] == "pklpo-instrument-drilldown"
    assert dashboard["title"] == "PKLPO Instrument Drilldown"
    assert len([p for p in dashboard["panels"] if p.get("type") != "row"]) == 6

    variables = {item["name"]: item for item in dashboard["templating"]["list"]}
    assert variables["symbol"]["type"] == "textbox"
    assert variables["symbol"]["current"]["value"] == "BTC-USDT-SWAP"
    assert (
        variables["timeframe"]["query"]
        == "label_values(pklpo_data_freshness_lag_seconds, timeframe)"
    )

    exprs = "\n".join(_target_exprs(dashboard))
    assert '{symbol="$symbol",timeframe="$timeframe"}' in exprs
    assert "pklpo_swap_repair_remaining_gap_tasks" in exprs
    assert "pklpo_swap_repair_api_fill_ratio" in exprs
    assert "pklpo_swap_repair_write_success_ratio" in exprs
    assert "pklpo_feature_warmup_bars_remaining" in exprs
    assert "rate(pklpo_features_rows_written_total" in exprs
    assert "rate(pklpo_upsert_failures_total" in exprs
    assert '|= "$symbol"' in exprs


def test_data_quality_dashboard_scales_with_symbol_variable_and_topn() -> None:
    dashboard = _load_dashboard("data_quality.json")

    variables = {item["name"]: item for item in dashboard["templating"]["list"]}
    assert variables["symbol"]["query"] == "label_values(pklpo_data_hole_rate, symbol)"
    assert variables["symbol"]["multi"] is True
    assert variables["symbol"]["includeAll"] is True
    assert variables["top_n"]["type"] == "textbox"
    assert variables["top_n"]["current"]["value"] == "10"

    exprs = _target_exprs(dashboard)
    assert any('symbol=~"$symbol"' in expr for expr in exprs)
    assert any(
        "topk($top_n, pklpo_data_freshness_lag_seconds" in expr for expr in exprs
    )
    assert any("topk($top_n, pklpo_data_hole_rate" in expr for expr in exprs)
    assert any("bottomk($top_n, pklpo_data_quality_score" in expr for expr in exprs)
    assert any("min by (timeframe) (pklpo_data_quality_score" in expr for expr in exprs)
    assert any("avg by (timeframe) (pklpo_data_quality_score" in expr for expr in exprs)
    assert any("max by (timeframe) (pklpo_data_quality_score" in expr for expr in exprs)
    assert any("count(pklpo_data_hole_rate" in expr for expr in exprs)
    assert any("count(pklpo_data_freshness_lag_seconds" in expr for expr in exprs)


def test_freshness_panels_fall_back_to_aggregate_symbol() -> None:
    """Current freshness lag is emitted by smoke checks as symbol=all."""
    data_quality = _load_dashboard("data_quality.json")
    drilldown = _load_dashboard("pklpo-instrument-drilldown.json")

    freshness_exprs = [
        expr
        for expr in [*_target_exprs(data_quality), *_target_exprs(drilldown)]
        if "pklpo_data_freshness_lag_seconds" in expr
    ]

    assert freshness_exprs
    assert all('symbol="all"' in expr for expr in freshness_exprs)
