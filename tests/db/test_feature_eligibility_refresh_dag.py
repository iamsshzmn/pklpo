from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest


def _load_dag(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    class _DummyDAG:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs
            self.schedule_interval = kwargs.get("schedule")
            self.tasks: list[Any] = []

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

    common = types.ModuleType("_common")

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> Any:
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                asyncio.set_event_loop(asyncio.new_event_loop())

    common.get_or_create_event_loop = lambda: _Loop()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "_common", common)

    module_path = Path(
        str(
            Path(__file__).parents[2]
            / "ops/airflow/dags/feature_eligibility_refresh.py"
        )
    )
    module_name = "tests.db._feature_eligibility_refresh_dag"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_feature_eligibility_refresh_dag_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_dag(monkeypatch)
    source = Path(
        str(
            Path(__file__).parents[2]
            / "ops/airflow/dags/feature_eligibility_refresh.py"
        )
    ).read_text(encoding="utf-8")

    assert module.dag.kwargs["schedule"] == "0 2 * * *"
    assert module.dag.kwargs["max_active_runs"] == 1
    assert source.index('sys.path.insert(0, "/opt/airflow/project")') < source.index(
        "from src.candles.interfaces"
    )
    assert module.refresh_eligibility.kwargs["task_id"] == "refresh_eligibility"


def test_feature_eligibility_refresh_task_calls_interface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_dag(monkeypatch)
    calls: list[str | None] = []

    async def _refresh_eligibility(
        *,
        evaluator_run_id: str | None = None,
    ) -> dict[str, int]:
        calls.append(evaluator_run_id)
        return {"evaluated": 1, "transitions": 0}

    monkeypatch.setattr(
        module.eligibility_interface,
        "refresh_eligibility",
        _refresh_eligibility,
    )

    result = module.refresh_eligibility_task(
        dag_run=types.SimpleNamespace(run_id="scheduled__2026-05-25")
    )

    assert result == {"evaluated": 1, "transitions": 0}
    assert calls == ["scheduled__2026-05-25"]
