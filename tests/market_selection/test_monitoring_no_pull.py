"""Tests for T5.1: market_selection monitoring uses push, not pull.

Host-runnable (stdlib only — text-scan approach avoids Python 3.11-only
syntax in monitoring.py at load time).

RED/GREEN contract
------------------
Before T5.1:
  - factory.py imports MarketSelectionMonitoring (pull adapter)
  - MarketSelectionPushMonitoring class does not exist
  -> test_factory_uses_push_monitoring, test_push_monitoring_class_exists FAIL

After T5.1: all tests pass.
"""

from __future__ import annotations

import pathlib

_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _monitoring_src() -> str:
    return (
        _PROJECT_ROOT / "src" / "market_selection" / "infrastructure" / "monitoring.py"
    ).read_text(encoding="utf-8")


def _factory_src() -> str:
    return (
        _PROJECT_ROOT / "src" / "market_selection" / "infrastructure" / "factory.py"
    ).read_text(encoding="utf-8")


def _push_class_body() -> str:
    src = _monitoring_src()
    start = src.find("class MarketSelectionPushMonitoring")
    assert start != -1, "class MarketSelectionPushMonitoring not found in monitoring.py"
    return src[start:]


# ── source-contract checks ────────────────────────────────────────────────────


def test_factory_uses_push_monitoring() -> None:
    """factory.py must inject MarketSelectionPushMonitoring, not the pull adapter."""
    src = _factory_src()
    assert "MarketSelectionPushMonitoring" in src, (
        "factory.py must use MarketSelectionPushMonitoring (push adapter)"
    )
    assert "MarketSelectionMonitoring()" not in src, (
        "factory.py must not instantiate the old pull-based MarketSelectionMonitoring"
    )


def test_push_monitoring_class_exists() -> None:
    """MarketSelectionPushMonitoring must be defined in monitoring.py."""
    assert "class MarketSelectionPushMonitoring" in _monitoring_src()


def test_start_http_server_not_called_by_push_adapter() -> None:
    """MarketSelectionPushMonitoring must not *call* start_http_server."""
    class_body = _push_class_body()
    # Check for actual call syntax, not docstring mentions
    assert "start_http_server(" not in class_body, (
        "MarketSelectionPushMonitoring must not call start_http_server()"
    )


def test_push_adapter_calls_push_market_selection_metrics() -> None:
    """The push adapter body must reference push_market_selection_metrics."""
    class_body = _push_class_body()
    assert "push_market_selection_metrics" in class_body, (
        "MarketSelectionPushMonitoring must call push_market_selection_metrics"
    )


def test_push_adapter_port_contract_methods_present() -> None:
    """The push adapter must implement both MonitoringPort methods."""
    class_body = _push_class_body()
    assert "def record_error" in class_body
    assert "def record_pipeline_metrics" in class_body


def test_push_market_selection_metrics_in_prometheus_py() -> None:
    """push_market_selection_metrics must exist in prometheus.py."""
    src = (
        _PROJECT_ROOT / "src" / "candles" / "observability" / "prometheus.py"
    ).read_text(encoding="utf-8")
    assert "def push_market_selection_metrics" in src


def test_push_market_selection_metrics_in_facade_init() -> None:
    """push_market_selection_metrics must be exported from the facade __init__."""
    src = (
        _PROJECT_ROOT / "src" / "pklpo_platform" / "observability" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert "push_market_selection_metrics" in src


def test_push_function_emits_key_gauges() -> None:
    """push_market_selection_metrics must set the universe_size and success gauges."""
    src = (
        _PROJECT_ROOT / "src" / "candles" / "observability" / "prometheus.py"
    ).read_text(encoding="utf-8")
    fn_start = src.find("def push_market_selection_metrics")
    assert fn_start != -1
    fn_body = src[fn_start:]
    assert "universe_size" in fn_body
    assert "run_success" in fn_body
    assert "duration_seconds" in fn_body
    assert "eligible_count" in fn_body
    assert (
        'job_name="market_selection"' in fn_body
        or 'job_name="market_selection"' in fn_body
    )


def test_no_start_http_server_in_factory() -> None:
    """factory.py must not call start_http_server."""
    assert "start_http_server" not in _factory_src()
