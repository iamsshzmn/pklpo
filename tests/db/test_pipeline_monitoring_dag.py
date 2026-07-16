from __future__ import annotations

import importlib.util
import json
import sys
import types
from contextlib import nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest


def _load_dag(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    class _DummyDAG:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    class _DummyOperator:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    airflow_module = types.ModuleType("airflow")
    airflow_module.DAG = _DummyDAG  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "airflow", airflow_module)

    airflow_operators = types.ModuleType("airflow.operators")
    monkeypatch.setitem(sys.modules, "airflow.operators", airflow_operators)

    airflow_operators_python = types.ModuleType("airflow.operators.python")
    airflow_operators_python.PythonOperator = _DummyOperator  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules,
        "airflow.operators.python",
        airflow_operators_python,
    )

    sqlalchemy = types.ModuleType("sqlalchemy")
    sqlalchemy.text = lambda sql: sql  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sqlalchemy", sqlalchemy)

    src_module = types.ModuleType("src")
    src_module.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src", src_module)

    candles_module = types.ModuleType("src.candles")
    candles_module.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src.candles", candles_module)

    observability_module = types.ModuleType("src.candles.observability")
    observability_module.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules,
        "src.candles.observability",
        observability_module,
    )

    prometheus_module = types.ModuleType("src.candles.observability.prometheus")
    prometheus_module.push_pipeline_monitoring_metrics = lambda snapshot: True  # type: ignore[attr-defined]
    prometheus_module.push_dependency_health_metrics = lambda **kwargs: True  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules,
        "src.candles.observability.prometheus",
        prometheus_module,
    )

    src_logging_module = types.ModuleType("src.logging")
    src_logging_module.get_logger = lambda name=None: types.SimpleNamespace(  # type: ignore[attr-defined]
        info=lambda *args, **kwargs: None
    )
    src_logging_module.set_span_attributes = lambda attributes: None  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src.logging", src_logging_module)

    utils_module = types.ModuleType("src.utils")
    utils_module.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src.utils", utils_module)

    session_utils_module = types.ModuleType("src.utils.session_utils")
    session_utils_module.get_db_session = lambda: None  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src.utils.session_utils", session_utils_module)

    common = types.ModuleType("_common")
    common.airflow_log_context = lambda context, **kwargs: nullcontext("run-id")
    common.get_dag_env = lambda job_name_default=None: {  # type: ignore[attr-defined]
        "OBSERVABILITY_JOB_NAME": job_name_default or "pipeline_monitoring"
    }
    common.setup_env = lambda env: None  # type: ignore[attr-defined]

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> Any:
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

    common.get_or_create_event_loop = lambda: _Loop()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "_common", common)

    module_path = Path(__file__).parents[2] / "ops/airflow/dags/pipeline_monitoring.py"
    module_name = "tests.db._pipeline_monitoring_dag"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_pipeline_monitoring_dag_contract_and_read_only_sql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_dag(monkeypatch)
    source = Path(
        str(Path(__file__).parents[2] / "ops/airflow/dags/pipeline_monitoring.py")
    ).read_text(encoding="utf-8")
    upper = source.upper()

    assert module.dag.kwargs["dag_id"] == "pipeline_monitoring"
    assert module.dag.kwargs["schedule"] == "*/10 * * * *"
    assert module.dag.kwargs["max_active_runs"] == 1
    assert source.index('sys.path.insert(0, "/opt/airflow/project")') < source.index(
        "from src.candles.observability.prometheus"
    )
    assert module.collect_pipeline_monitoring.kwargs["task_id"] == (
        "collect_pipeline_monitoring"
    )
    assert not any(token in upper for token in ("INSERT ", "UPDATE ", "DELETE "))


def test_collect_pipeline_monitoring_task_pushes_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_dag(monkeypatch)
    pushed: list[dict[str, Any]] = []
    log_records: list[dict[str, Any]] = []
    span_attributes: dict[str, Any] = {}
    snapshot = {
        "candle_lag_seconds": {"1H": 120.0},
        "recalc_queue": {"queued": 1},
        "bootstrap_state": {"completed": 2},
        "eligibility_state": [{"timeframe": "1H", "state": "eligible", "count": 3}],
        "alerts": {"critical": 0},
    }

    async def _collect_snapshot() -> dict[str, Any]:
        return snapshot

    async def _probe_dependency_health() -> dict[str, bool]:
        return {"postgres_up": True, "okx_up": False}

    monkeypatch.setattr(
        module, "_collect_pipeline_monitoring_snapshot", _collect_snapshot
    )
    monkeypatch.setattr(module, "_probe_dependency_health", _probe_dependency_health)
    monkeypatch.setattr(
        module,
        "push_pipeline_monitoring_metrics",
        lambda payload: pushed.append(payload) or True,
    )
    monkeypatch.setattr(
        module,
        "push_dependency_health_metrics",
        lambda **kwargs: kwargs["postgres_up"] and not kwargs["okx_up"],
    )
    monkeypatch.setattr(
        module,
        "LOGGER",
        types.SimpleNamespace(
            info=lambda message, **kwargs: log_records.append(
                {"message": message, **kwargs}
            )
        ),
    )
    monkeypatch.setattr(
        module,
        "set_span_attributes",
        lambda attributes: span_attributes.update(attributes),
    )

    result = module.collect_pipeline_monitoring_task()

    assert result == {
        **snapshot,
        "metrics_pushed": True,
        "dep_health": {"postgres_up": True, "okx_up": False},
        "dep_metrics_pushed": True,
    }
    json.dumps(result)
    assert pushed == [snapshot]
    assert span_attributes == {"processed_count": 1}
    assert log_records == [
        {
            "message": "pipeline_monitoring_snapshot_collected",
            "extra": {
                "event": "pipeline_monitoring_snapshot_collected",
                "processed_count": 1,
            },
        },
        {
            "message": "pipeline_monitoring_metrics_pushed",
            "extra": {
                "event": "pipeline_monitoring_metrics_pushed",
                "processed_count": 2,
            },
        },
    ]
