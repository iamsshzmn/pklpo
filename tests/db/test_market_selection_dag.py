from __future__ import annotations

import importlib.util
import sys
import types
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest


def _load_dag(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    class _DummyDAG:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

        def __enter__(self) -> _DummyDAG:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

    class _DummyOperator:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

        def __rshift__(self, other: Any) -> Any:
            return other

    airflow_module = types.ModuleType("airflow")
    airflow_module.DAG = _DummyDAG  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "airflow", airflow_module)

    airflow_operators = types.ModuleType("airflow.operators")
    monkeypatch.setitem(sys.modules, "airflow.operators", airflow_operators)

    airflow_operators_empty = types.ModuleType("airflow.operators.empty")
    airflow_operators_empty.EmptyOperator = _DummyOperator  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "airflow.operators.empty", airflow_operators_empty)

    airflow_operators_python = types.ModuleType("airflow.operators.python")
    airflow_operators_python.BranchPythonOperator = _DummyOperator  # type: ignore[attr-defined]
    airflow_operators_python.PythonOperator = _DummyOperator  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules,
        "airflow.operators.python",
        airflow_operators_python,
    )

    airflow_operators_trigger = types.ModuleType("airflow.operators.trigger_dagrun")
    airflow_operators_trigger.TriggerDagRunOperator = _DummyOperator  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules,
        "airflow.operators.trigger_dagrun",
        airflow_operators_trigger,
    )

    airflow_sensors = types.ModuleType("airflow.sensors")
    monkeypatch.setitem(sys.modules, "airflow.sensors", airflow_sensors)

    airflow_sensors_external = types.ModuleType("airflow.sensors.external_task")
    airflow_sensors_external.ExternalTaskSensor = _DummyOperator  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules,
        "airflow.sensors.external_task",
        airflow_sensors_external,
    )

    common = types.ModuleType("_common")
    common.get_dag_env = lambda job_name_default=None: {  # type: ignore[attr-defined]
        "OBSERVABILITY_JOB_NAME": job_name_default or "market_selection"
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

    module_path = Path("D:/projects/pklpo/ops/airflow/dags/market_selection.py")
    module_name = "tests.db._market_selection_dag"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_market_selection_dag_contract_and_shared_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_dag(monkeypatch)
    source = Path("D:/projects/pklpo/ops/airflow/dags/market_selection.py").read_text(
        encoding="utf-8"
    )

    assert module.dag.kwargs["dag_id"] == "market_selection"
    assert module.dag.kwargs["schedule"] == "0 */4 * * *"
    assert module.dag.kwargs["max_active_runs"] == 1
    assert module.default_args["execution_timeout"] == timedelta(hours=2)
    assert "create_async_engine" not in source
    assert "AsyncSession(" not in source
    assert "def get_or_create_event_loop" not in source
    assert source.index('sys.path.insert(0, "/opt/airflow/project")') < source.index(
        "from _common import"
    )


def test_validate_universe_handles_missing_versions_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_dag(monkeypatch)

    class _Result:
        @staticmethod
        def scalar() -> bool:
            return False

    class _Session:
        async def execute(self, *_args: Any, **_kwargs: Any) -> _Result:
            return _Result()

    session_utils = types.ModuleType("src.utils.session_utils")

    @asynccontextmanager
    async def _fake_get_db_session() -> Any:
        yield _Session()

    session_utils.get_db_session = _fake_get_db_session  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src.utils.session_utils", session_utils)

    result = module._get_loop().run_until_complete(module._validate_universe_async())

    assert result == {
        "valid": False,
        "reason": "market_universe_versions table missing",
    }


def test_get_universe_symbols_handles_missing_universe_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_dag(monkeypatch)

    class _Result:
        def __init__(self, value: bool) -> None:
            self.value = value

        def scalar(self) -> bool:
            return self.value

    class _Session:
        async def execute(self, _statement: Any, params: dict[str, Any]) -> _Result:
            return _Result(params["table_name"] == "public.market_universe_versions")

    session_utils = types.ModuleType("src.utils.session_utils")

    @asynccontextmanager
    async def _fake_get_db_session() -> Any:
        yield _Session()

    session_utils.get_db_session = _fake_get_db_session  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src.utils.session_utils", session_utils)

    result = module._get_loop().run_until_complete(module._get_universe_symbols_async())

    assert result == []
