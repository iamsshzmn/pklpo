"""T7.1: Verify Gauge-vs-Counter naming and dashboard rate() usage.

Host-runnable (stdlib only).

RED/GREEN contract
------------------
Before T7.1: swap_sync Gauge metrics have _total suffix and dashboard uses rate() on them.
After T7.1: all assertions pass.
"""
from __future__ import annotations

import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PROMETHEUS_PY = (
    _PROJECT_ROOT / "src" / "candles" / "observability" / "prometheus.py"
)
_DASHBOARD_JSON = (
    _PROJECT_ROOT
    / "ops"
    / "monitoring"
    / "grafana"
    / "dashboards"
    / "pipeline_observability.json"
)


def _prometheus_src() -> str:
    return _PROMETHEUS_PY.read_text(encoding="utf-8")


def _dashboard_src() -> str:
    return _DASHBOARD_JSON.read_text(encoding="utf-8")


# ── prometheus.py: Gauge naming rules ────────────────────────────────────────

def test_swap_sync_per_run_gauges_have_no_total_suffix() -> None:
    """Per-run swap_sync Gauges must not use _total suffix (reserved for Counters)."""
    src = _prometheus_src()
    # Extract the push_swap_sync_metrics function body
    fn_match = re.search(
        r"def push_swap_sync_metrics.*?(?=\ndef |\Z)", src, re.DOTALL
    )
    assert fn_match, "push_swap_sync_metrics not found"
    fn_body = fn_match.group(0)

    # Find all Gauge metric name strings in the function
    gauge_names = re.findall(r'Gauge\(\s*"(pklpo_swap_sync_[^"]+)"', fn_body)
    assert gauge_names, "No Gauge metrics found in push_swap_sync_metrics"

    for name in gauge_names:
        assert not name.endswith("_total"), (
            f"Gauge '{name}' has _total suffix — "
            "rename to drop _total or change to Counter"
        )


def test_true_counters_retain_total_suffix() -> None:
    """Counter metrics must keep _total suffix (Prometheus convention)."""
    src = _prometheus_src()
    # These are the known true Counters in the file
    for name in (
        "pklpo_duplicate_rows_detected_total",
        "pklpo_feature_eligibility_transitions_total",
    ):
        assert f'"{name}"' in src, f"True Counter {name!r} missing from prometheus.py"


def test_no_total_gauge_in_dashboard_under_rate() -> None:
    """No rate(pklpo_..._total[...]) expression on a Gauge series in the dashboard."""
    dash = _dashboard_src()
    # Any _total metric under rate() is suspect — Counter names are OK but swap_sync ones were Gauges
    bad = re.findall(r'rate\(pklpo_swap_sync_\w+_total\[', dash)
    assert not bad, (
        f"Dashboard still uses rate() on _total Gauge series: {bad}"
    )


def test_dashboard_panel_201_uses_per_run_gauge_exprs() -> None:
    """Panel 201 throughput expressions must be bare Gauge queries, not rate()."""
    dash = _dashboard_src()
    assert "pklpo_swap_sync_rows_upserted\"" in dash, (
        "pklpo_swap_sync_rows_upserted not found in dashboard"
    )
    assert "pklpo_swap_sync_symbols_processed\"" in dash, (
        "pklpo_swap_sync_symbols_processed not found in dashboard"
    )
    # Must not appear with _total suffix
    assert "pklpo_swap_sync_rows_upserted_total" not in dash
    assert "pklpo_swap_sync_symbols_processed_total" not in dash


def test_dashboard_panel_202_uses_per_run_gauge_expr() -> None:
    """Panel 202 error expression must be a bare Gauge query, not rate()."""
    dash = _dashboard_src()
    assert "pklpo_swap_sync_errors\"" in dash, (
        "pklpo_swap_sync_errors not found in dashboard"
    )
    assert "pklpo_swap_sync_errors_total" not in dash


def test_dashboard_panel_303_api_saturation_names_updated() -> None:
    """USE panel 303 must use the renamed Gauge names (no _total)."""
    dash = _dashboard_src()
    assert "pklpo_swap_sync_api_rate_limit_hits\"" in dash
    assert "pklpo_swap_sync_api_timeouts\"" in dash
    assert "pklpo_swap_sync_api_rate_limit_hits_total" not in dash
    assert "pklpo_swap_sync_api_timeouts_total" not in dash
