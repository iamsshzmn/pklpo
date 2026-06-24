from __future__ import annotations

import importlib.util
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest

from src.logging.context import get_current_context, get_current_run_id

_COMMON_DIR = Path("D:/projects/pklpo/ops/airflow/dags/_common")


def _load_common_module(module_name: str) -> types.ModuleType:
    module_path = _COMMON_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"tests.db._airflow_common_{module_name}",
        module_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_get_dag_env_defaults_enable_pushgateway(monkeypatch: pytest.MonkeyPatch) -> None:
    env_module = _load_common_module("env")

    class _BaseHook:
        @staticmethod
        def get_connection(name: str) -> Any:
            assert name == "pklpo_db"
            return SimpleNamespace(get_uri=lambda: "postgresql://user:pass@db/pklpo")

    class _Variable:
        @staticmethod
        def get(name: str, *, default_var: str) -> str:
            return default_var

    airflow_hooks_base = types.ModuleType("airflow.hooks.base")
    airflow_hooks_base.BaseHook = _BaseHook
    airflow_models = types.ModuleType("airflow.models")
    airflow_models.Variable = _Variable
    monkeypatch.setitem(sys.modules, "airflow.hooks.base", airflow_hooks_base)
    monkeypatch.setitem(sys.modules, "airflow.models", airflow_models)
    monkeypatch.delenv("OBSERVABILITY_PROMETHEUS_ENABLED", raising=False)
    monkeypatch.delenv("OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL", raising=False)
    monkeypatch.setattr(
        env_module,
        "project_env_default",
        lambda name, fallback: fallback,
    )

    env = env_module.get_dag_env(job_name_default="pipeline_monitoring")

    assert env["OBSERVABILITY_PROMETHEUS_ENABLED"] == "true"
    assert env["OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL"] == "http://pushgateway:9091"


def test_airflow_log_context_sets_structured_fields() -> None:
    observability_module = _load_common_module("observability")
    context = {
        "dag_run": SimpleNamespace(run_id="manual__2026-06-09T00:00:00+00:00"),
        "ti": SimpleNamespace(task_id="swap_sync"),
    }

    with observability_module.airflow_log_context(
        context,
        component="swap_sync",
        extra_field="extra-value",
    ) as run_id:
        assert run_id == "manual__2026-06-09T00:00:00+00:00"
        assert get_current_context() == {
            "run_id": "manual__2026-06-09T00:00:00+00:00",
            "symbol": None,
            "timeframe": None,
            "component": "swap_sync",
            "trace_id": None,
            "span_id": None,
            "task_id": "swap_sync",
            "extra_field": "extra-value",
        }

    assert get_current_run_id() is None


def test_airflow_log_context_initializes_tracing_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observability_module = _load_common_module("observability")
    configure_calls: list[bool] = []

    class _Span:
        @staticmethod
        def set_attribute(key: str, value: Any) -> None:
            return None

    @contextmanager
    def fake_start_span(*args: Any, **kwargs: Any):
        yield _Span()

    monkeypatch.setattr(
        observability_module,
        "configure_tracing",
        lambda: configure_calls.append(True) or False,
    )
    monkeypatch.setattr(observability_module, "start_span", fake_start_span)
    context = {
        "dag_run": SimpleNamespace(run_id="manual__run"),
        "ti": SimpleNamespace(task_id="task_a"),
    }

    with observability_module.airflow_log_context(context, component="component"):
        pass
    with observability_module.airflow_log_context(context, component="component"):
        pass

    assert configure_calls == [True]


def test_airflow_log_context_starts_task_span_with_run_attributes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observability_module = _load_common_module("observability")
    span_calls: list[dict[str, Any]] = []
    span_attributes: dict[str, Any] = {}

    class _Span:
        @staticmethod
        def set_attribute(key: str, value: Any) -> None:
            span_attributes[key] = value

    @contextmanager
    def fake_start_span(*args: Any, **kwargs: Any):
        span_calls.append({"args": args, "kwargs": kwargs})
        yield _Span()

    monkeypatch.setattr(observability_module, "configure_tracing", lambda: False)
    monkeypatch.setattr(observability_module, "start_span", fake_start_span)
    context = {
        "dag_run": SimpleNamespace(run_id="manual__2026-06-20T00:00:00+00:00"),
        "ti": SimpleNamespace(task_id="swap_sync"),
        "params": {"symbol": "BTC-USDT-SWAP", "timeframe": "1m"},
    }

    with observability_module.airflow_log_context(context, component="swap_sync"):
        pass

    assert span_calls == [
        {
            "args": ("airflow.swap_sync.swap_sync",),
            "kwargs": {
                "run_id": "manual__2026-06-20T00:00:00+00:00",
                "attributes": {
                    "run_id": "manual__2026-06-20T00:00:00+00:00",
                    "component": "swap_sync",
                    "task_id": "swap_sync",
                    "symbol": "BTC-USDT-SWAP",
                    "timeframe": "1m",
                },
            },
        }
    ]
    assert span_attributes["status"] == "ok"
    assert isinstance(span_attributes["duration_seconds"], float)


def test_airflow_log_context_marks_failed_task_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observability_module = _load_common_module("observability")
    span_attributes: dict[str, Any] = {}

    class _Span:
        @staticmethod
        def set_attribute(key: str, value: Any) -> None:
            span_attributes[key] = value

    @contextmanager
    def fake_start_span(*args: Any, **kwargs: Any):
        yield _Span()

    monkeypatch.setattr(observability_module, "configure_tracing", lambda: False)
    monkeypatch.setattr(observability_module, "start_span", fake_start_span)
    context = {
        "dag_run": SimpleNamespace(run_id="manual__failed"),
        "ti": SimpleNamespace(task_id="pipeline_monitoring"),
    }

    try:
        with observability_module.airflow_log_context(
            context,
            component="pipeline_monitoring",
        ):
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert span_attributes["status"] == "error"
    assert span_attributes["error_type"] == "RuntimeError"
    assert span_attributes["error.reason"] == "boom"
    assert isinstance(span_attributes["duration_seconds"], float)
