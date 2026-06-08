from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _load_repair_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    class _DummyDAG:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    class _DummyOperator:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

        def __rshift__(self, other: Any) -> Any:
            return other

    airflow_module = types.ModuleType("airflow")
    airflow_module.DAG = _DummyDAG
    monkeypatch.setitem(sys.modules, "airflow", airflow_module)

    class _AirflowFailException(Exception):
        pass

    airflow_exceptions = types.ModuleType("airflow.exceptions")
    airflow_exceptions.AirflowFailException = _AirflowFailException
    monkeypatch.setitem(sys.modules, "airflow.exceptions", airflow_exceptions)

    airflow_models = types.ModuleType("airflow.models")
    monkeypatch.setitem(sys.modules, "airflow.models", airflow_models)

    airflow_models_param = types.ModuleType("airflow.models.param")

    class _DummyParam:
        def __init__(self, default: Any, **kwargs: Any) -> None:
            self.default = default
            self.kwargs = kwargs

    airflow_models_param.Param = _DummyParam
    monkeypatch.setitem(sys.modules, "airflow.models.param", airflow_models_param)

    airflow_operators = types.ModuleType("airflow.operators")
    monkeypatch.setitem(sys.modules, "airflow.operators", airflow_operators)

    airflow_operators_python = types.ModuleType("airflow.operators.python")
    airflow_operators_python.PythonOperator = _DummyOperator
    monkeypatch.setitem(
        sys.modules, "airflow.operators.python", airflow_operators_python
    )

    candles_bootstrap = types.ModuleType("src.candles.bootstrap")
    candles_bootstrap.create_candles_airflow_callbacks = lambda: SimpleNamespace(
        on_failure_callback="failure_cb",
        on_success_callback="success_cb",
        on_retry_callback="retry_cb",
    )
    monkeypatch.setitem(sys.modules, "src.candles.bootstrap", candles_bootstrap)

    module_path = Path("D:/projects/pklpo/ops/airflow/dags/okx_swap_repair_v1.py")
    module_name = "tests.db._okx_swap_repair_v1_dag"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_param_contract(params: dict[str, Any]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for name, param in params.items():
        entry: dict[str, Any] = {"default": param.default}
        entry.update(param.kwargs)
        normalized[name] = entry
    return normalized


@pytest.fixture
def repair_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    return _load_repair_dag_module(monkeypatch)


class _TaskInstance:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def xcom_pull(self, task_ids: str, key: str) -> Any:
        assert key == "return_value"
        if isinstance(self._payload, dict) and task_ids in self._payload:
            return self._payload[task_ids]
        return self._payload


def test_repair_dag_default_args_include_alert_callbacks(
    repair_dag_module: types.ModuleType,
) -> None:
    assert repair_dag_module.default_args["on_failure_callback"] == "failure_cb"
    assert repair_dag_module.default_args["on_success_callback"] == "success_cb"
    assert repair_dag_module.default_args["on_retry_callback"] == "retry_cb"


def test_repair_dag_appends_refresh_eligibility_task(
    repair_dag_module: types.ModuleType,
) -> None:
    assert repair_dag_module.refresh_eligibility.kwargs["task_id"] == (
        "refresh_eligibility"
    )
    assert (
        repair_dag_module.refresh_eligibility.kwargs["python_callable"]
        is repair_dag_module.refresh_eligibility_task
    )


def test_repair_dag_params_contract_snapshot(
    repair_dag_module: types.ModuleType,
) -> None:
    assert _normalize_param_contract(repair_dag_module.dag.kwargs["params"]) == {
        "trigger": {
            "default": "repair-all-swaps",
            "type": "string",
            "enum": ["last-200-guard", "repair-all-swaps"],
            "description": "Manual trigger preset. Runtime repair settings live in code.",
        }
    }


def test_validate_swap_repair_conf_builds_internal_preset_from_trigger(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        repair_dag_module,
        "_load_curated_swap_symbols",
        lambda: ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
    )

    result = repair_dag_module.validate_swap_repair_conf_task(
        dag_run=SimpleNamespace(conf={"trigger": "repair-all-swaps"})
    )

    assert result["trigger"] == "repair-all-swaps"
    assert result["symbols"] == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    assert result["timeframes"] == ["1H", "4H"]
    assert result["mode"] == "apply"
    assert result["repair_strategy"] == "gap-repair"
    assert result["auto_apply_anchor_strategy"] == "listing-date"
    assert result["auto_apply_window"] is True
    assert result["start_ts_ms"] is None
    assert result["end_ts_ms"] is None


def test_validate_swap_repair_conf_builds_last_200_guard_preset(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        repair_dag_module,
        "_load_curated_swap_symbols",
        lambda: ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
    )

    result = repair_dag_module.validate_swap_repair_conf_task(
        dag_run=SimpleNamespace(conf={"trigger": "last-200-guard"})
    )

    assert result["trigger"] == "last-200-guard"
    assert result["symbols"] == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    assert result["timeframes"] == ["1H", "4H", "1D", "1W", "1M"]
    assert "1m" not in result["critical_timeframes"]
    assert result["bars"] == 500
    assert result["mode"] == "apply"
    assert result["repair_strategy"] == "last_n_closed_bars"
    assert result["publish_on_statuses"] == [
        "partial",
        "blocked",
        "deferred",
        "not_matured",
    ]


def test_validate_swap_repair_conf_rejects_unknown_trigger(
    repair_dag_module: types.ModuleType,
) -> None:
    with pytest.raises(ValueError, match="unsupported trigger"):
        repair_dag_module.validate_swap_repair_conf_task(
            dag_run=SimpleNamespace(conf={"trigger": "custom"})
        )


def test_validate_swap_repair_conf_rejects_empty_curated_symbol_list(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(repair_dag_module, "_load_curated_swap_symbols", lambda: [])

    with pytest.raises(ValueError, match="curated symbol list is empty"):
        repair_dag_module.validate_swap_repair_conf_task(
            dag_run=SimpleNamespace(conf={"trigger": "repair-all-swaps"})
        )


def test_swap_repair_preview_task_runs_for_each_symbol_and_timeframe(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _fake_plan_swap_repair(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "requested_mode": "apply",
            "strategy": "gap-repair",
            "symbol": kwargs["symbol"],
            "timeframe": kwargs["timeframe"],
            "window": {"start_ts_ms": 10, "end_ts_ms": 100},
            "auto_apply_window": kwargs["auto_apply_window"],
            "gap_tasks": 1,
            "requested_bars": 5,
            "expected_iteration_count": 1,
            "guardrail_risk": "ok",
            "guardrail_violations": [],
        }

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> dict[str, Any]:
            import asyncio

            return asyncio.run(coro)

    monkeypatch.setattr(
        repair_dag_module.repair_interface, "plan_swap_repair", _fake_plan_swap_repair
    )
    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(
        repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)

    result = repair_dag_module.swap_repair_preview_task(
        ti=_TaskInstance(
            {
                "trigger": "repair-all-swaps",
                "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
                "timeframes": ["1m", "1H"],
                "mode": "apply",
                "repair_strategy": "gap-repair",
                "start_ts_ms": None,
                "end_ts_ms": None,
                "padding_bars": 0,
                "max_gap_tasks_per_run": 50,
                "max_requested_bars_per_run": 10_000,
                "max_range_days": 7,
                "max_fail_ratio": 0.1,
                "auto_apply_anchor_strategy": "listing-date",
                "anchor_ts_ms": None,
                "auto_apply_window": True,
            }
        )
    )

    assert [(call["symbol"], call["timeframe"]) for call in calls] == [
        ("BTC-USDT-SWAP", "1m"),
        ("BTC-USDT-SWAP", "1H"),
        ("ETH-USDT-SWAP", "1m"),
        ("ETH-USDT-SWAP", "1H"),
    ]
    assert len(result) == 4


def test_swap_repair_task_runs_for_each_symbol_and_timeframe(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _fake_run_swap_repair_auto_apply(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "mode": "apply",
            "strategy": kwargs["strategy"].value,
            "symbol": kwargs["symbol"],
            "timeframe": kwargs["timeframe"],
            "window": {"start_ts_ms": 10, "end_ts_ms": 100},
            "gap_tasks": 1,
            "requested_bars": 1,
            "remaining_gap_tasks": 0,
            "remaining_requested_bars": 0,
            "verification_method": "gap-detection",
            "rows_written": 1,
            "fetch_calls": 1,
            "verified": True,
            "padding_bars": 0,
            "guardrail_violations": [],
            "watermark_updated": False,
        }

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> dict[str, Any]:
            import asyncio

            return asyncio.run(coro)

    monkeypatch.setattr(
        repair_dag_module.repair_interface,
        "run_swap_repair_auto_apply",
        _fake_run_swap_repair_auto_apply,
    )
    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(
        repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)

    result = repair_dag_module.swap_repair_task(
        ti=_TaskInstance(
            {
                "trigger": "repair-all-swaps",
                "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
                "timeframes": ["1m", "1H"],
                "mode": "apply",
                "repair_strategy": "gap-repair",
                "start_ts_ms": None,
                "end_ts_ms": None,
                "padding_bars": 0,
                "max_gap_tasks_per_run": 50,
                "max_requested_bars_per_run": 10_000,
                "max_range_days": 7,
                "max_fail_ratio": 0.1,
                "auto_apply_anchor_strategy": "listing-date",
                "anchor_ts_ms": None,
                "auto_apply_window": True,
            }
        )
    )

    assert [(call["symbol"], call["timeframe"]) for call in calls] == [
        ("BTC-USDT-SWAP", "1m"),
        ("BTC-USDT-SWAP", "1H"),
        ("ETH-USDT-SWAP", "1m"),
        ("ETH-USDT-SWAP", "1H"),
    ]
    assert all(call["auto_apply_anchor_strategy"] == "listing-date" for call in calls)
    assert len(result) == 4


def test_swap_repair_task_forwards_no_progress_policy_from_preset(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _fake_run_swap_repair_auto_apply(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "mode": "apply",
            "strategy": kwargs["strategy"].value,
            "symbol": kwargs["symbol"],
            "timeframe": kwargs["timeframe"],
            "window": {"start_ts_ms": 10, "end_ts_ms": 100},
            "gap_tasks": 0,
            "requested_bars": 0,
            "remaining_gap_tasks": 0,
            "remaining_requested_bars": 0,
            "verification_method": "gap-detection",
            "rows_written": 0,
            "fetch_calls": 0,
            "verified": True,
            "padding_bars": 0,
            "guardrail_violations": [],
            "watermark_updated": False,
        }

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> dict[str, Any]:
            import asyncio

            return asyncio.run(coro)

    monkeypatch.setattr(
        repair_dag_module.repair_interface,
        "run_swap_repair_auto_apply",
        _fake_run_swap_repair_auto_apply,
    )
    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(
        repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)

    repair_dag_module.swap_repair_task(
        ti=_TaskInstance(
            {
                "trigger": "repair-all-swaps",
                "symbols": ["BTC-USDT-SWAP"],
                "timeframes": ["1m"],
                "mode": "apply",
                "repair_strategy": "gap-repair",
                "start_ts_ms": None,
                "end_ts_ms": None,
                "padding_bars": 0,
                "max_gap_tasks_per_run": 50,
                "max_requested_bars_per_run": 10_000,
                "max_range_days": 7,
                "max_fail_ratio": 1.0,
                "auto_apply_anchor_strategy": "listing-date",
                "anchor_ts_ms": None,
                "auto_apply_window": True,
                "critical_timeframes": ["1H"],
                "no_progress_threshold": 1,
            }
        )
    )

    assert len(calls) == 1
    assert calls[0]["critical_timeframes"] == ["1H"]
    assert calls[0]["no_progress_threshold"] == 1


def test_swap_repair_task_uses_last_n_guard_interface_for_guard_trigger(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> dict[str, Any]:
            import asyncio

            return asyncio.run(coro)

    async def _fake_guarantee_last_n_closed_bars(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "status": "ok",
            "symbol": kwargs["symbol"],
            "timeframe": kwargs["timeframe"],
            "affected_recalc_range": (10, 100),
            "unresolved_timestamps": [],
            "corrupted_count": 0,
            "repaired_count": 1,
        }

    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(
        repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(
        repair_dag_module.repair_interface,
        "guarantee_last_n_closed_bars",
        _fake_guarantee_last_n_closed_bars,
    )

    result = repair_dag_module.swap_repair_task(
        ti=_TaskInstance(
            {
                "trigger": "last-200-guard",
                "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
                "timeframes": ["1H"],
                "bars": 500,
                "mode": "apply",
                "repair_strategy": "last_n_closed_bars",
            }
        )
    )

    assert calls == [
        {"symbol": "BTC-USDT-SWAP", "timeframe": "1H", "bars": 500},
        {"symbol": "ETH-USDT-SWAP", "timeframe": "1H", "bars": 500},
    ]
    assert result == [
        {
            "status": "ok",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1H",
            "affected_recalc_range": (10, 100),
            "unresolved_timestamps": [],
            "corrupted_count": 0,
            "repaired_count": 1,
        },
        {
            "status": "ok",
            "symbol": "ETH-USDT-SWAP",
            "timeframe": "1H",
            "affected_recalc_range": (10, 100),
            "unresolved_timestamps": [],
            "corrupted_count": 0,
            "repaired_count": 1,
        },
    ]


def test_run_swap_repair_once_forwards_no_progress_policy_from_preset(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _fake_run_swap_repair(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {}

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> dict[str, Any]:
            import asyncio

            return asyncio.run(coro)

    monkeypatch.setattr(
        repair_dag_module.repair_interface,
        "run_swap_repair",
        _fake_run_swap_repair,
    )
    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())

    repair_dag_module._run_swap_repair_once(
        validated={
            "symbol": "BTC-USDT-SWAP",
            "mode": "apply",
            "repair_strategy": "gap-repair",
            "max_gap_tasks_per_run": 50,
            "max_requested_bars_per_run": 10_000,
            "max_range_days": 7,
            "max_fail_ratio": 1.0,
            "padding_bars": 0,
            "critical_timeframes": ["1H"],
            "no_progress_threshold": 2,
        },
        timeframe="1H",
        start_ts_ms=10,
        end_ts_ms=100,
    )

    assert len(calls) == 1
    assert calls[0]["critical_timeframes"] == ["1H"]
    assert calls[0]["no_progress_threshold"] == 2


def test_publish_swap_repair_ops_task_pushes_metrics_and_writes_audit(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics_calls: list[Any] = []
    audit_calls: list[dict[str, Any]] = []

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> Any:
            import asyncio

            return asyncio.run(coro)

    async def _fake_write_swap_repair_audit(**kwargs: Any) -> int:
        audit_calls.append(kwargs)
        return 4

    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(
        repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(
        repair_dag_module,
        "push_swap_repair_metrics",
        lambda payloads: metrics_calls.append(payloads) or True,
    )
    monkeypatch.setattr(
        repair_dag_module, "write_swap_repair_audit", _fake_write_swap_repair_audit
    )

    result = repair_dag_module.publish_swap_repair_ops_task(
        ti=_TaskInstance(
            {
                "validate_swap_repair_conf": {
                    "trigger": "repair-all-swaps",
                    "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
                    "timeframes": ["1m", "1H"],
                    "mode": "apply",
                    "repair_strategy": "gap-repair",
                    "start_ts_ms": None,
                    "end_ts_ms": None,
                    "padding_bars": 0,
                    "max_gap_tasks_per_run": 50,
                    "max_requested_bars_per_run": 10_000,
                    "max_range_days": 7,
                    "max_fail_ratio": 0.1,
                    "auto_apply_anchor_strategy": "listing-date",
                    "anchor_ts_ms": None,
                    "auto_apply_window": True,
                },
                "swap_repair_preview": [
                    {
                        "symbol": "BTC-USDT-SWAP",
                        "timeframe": "1m",
                        "expected_iteration_count": 1,
                    },
                    {
                        "symbol": "BTC-USDT-SWAP",
                        "timeframe": "1H",
                        "expected_iteration_count": 1,
                    },
                    {
                        "symbol": "ETH-USDT-SWAP",
                        "timeframe": "1m",
                        "expected_iteration_count": 1,
                    },
                    {
                        "symbol": "ETH-USDT-SWAP",
                        "timeframe": "1H",
                        "expected_iteration_count": 1,
                    },
                ],
                "validate_swap_repair_xcom": [
                    {
                        "symbol": "BTC-USDT-SWAP",
                        "timeframe": "1m",
                        "mode": "apply",
                        "strategy": "gap-repair",
                        "window": {"start_ts_ms": 10, "end_ts_ms": 100},
                        "gap_tasks": 1,
                        "requested_bars": 5,
                        "remaining_gap_tasks": 0,
                        "remaining_requested_bars": 0,
                        "verification_method": "gap-detection",
                        "rows_written": 5,
                        "fetch_calls": 1,
                        "verified": True,
                        "padding_bars": 0,
                        "guardrail_violations": [],
                        "watermark_updated": False,
                        "auto_apply_incomplete": False,
                    },
                    {
                        "symbol": "ETH-USDT-SWAP",
                        "timeframe": "1m",
                        "mode": "apply",
                        "strategy": "gap-repair",
                        "window": {"start_ts_ms": 20, "end_ts_ms": 200},
                        "gap_tasks": 2,
                        "requested_bars": 10,
                        "remaining_gap_tasks": 0,
                        "remaining_requested_bars": 0,
                        "verification_method": "gap-detection",
                        "rows_written": 10,
                        "fetch_calls": 2,
                        "verified": True,
                        "padding_bars": 0,
                        "guardrail_violations": [],
                        "watermark_updated": False,
                        "auto_apply_incomplete": False,
                    },
                ],
            }
        ),
        dag_run=SimpleNamespace(run_id="manual__2026-04-19T10:00:00+00:00"),
        logical_date=__import__("datetime").datetime(2026, 4, 19, 10, 0),
    )

    assert metrics_calls and len(metrics_calls[0]) == 2
    assert audit_calls and audit_calls[0]["dag_id"] == "okx_swap_repair_v1"
    assert audit_calls[0]["validated_conf"]["trigger"] == "repair-all-swaps"
    assert result == {"metrics_pushed": True, "audit_rows_written": 4}


def test_publish_swap_repair_ops_task_pushes_guard_metrics_and_guard_audit(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    metrics_calls: list[Any] = []
    guard_audit_calls: list[dict[str, Any]] = []

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> Any:
            return asyncio.run(coro)

    async def _fake_guard_audit(**kwargs: Any) -> int:
        guard_audit_calls.append(kwargs)
        return 1

    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(
        repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(
        repair_dag_module,
        "push_swap_repair_metrics",
        lambda payloads: metrics_calls.append(payloads) or True,
    )
    monkeypatch.setattr(
        repair_dag_module,
        "write_guard_repair_audit",
        _fake_guard_audit,
    )

    result = repair_dag_module.publish_swap_repair_ops_task(
        ti=_TaskInstance(
            {
                "validate_swap_repair_conf": {
                    "trigger": "last-200-guard",
                    "repair_strategy": "last_n_closed_bars",
                },
                "validate_swap_repair_xcom": [
                    {
                        "symbol": "BTC-USDT-SWAP",
                        "timeframe": "1H",
                        "strategy": "last_n_closed_bars",
                        "status": "ok",
                        "affected_recalc_range": (10, 100),
                        "unresolved_timestamps": [],
                        "corrupted_count": 1,
                        "repaired_count": 2,
                    }
                ],
            }
        )
    )

    assert len(metrics_calls) == 1
    assert metrics_calls[0][0]["strategy"] == "last_n_closed_bars"
    assert len(guard_audit_calls) == 1
    assert guard_audit_calls[0]["dag_id"] == "okx_swap_repair_v1"
    assert result == {"metrics_pushed": True, "audit_rows_written": 1}


def test_enqueue_indicator_recalc_task_calls_interface_for_guard_recalc_range(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> Any:
            import asyncio

            return asyncio.run(coro)

    async def _fake_enqueue_indicator_recalc(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "status": "queued",
            "symbol": kwargs["symbol"],
            "timeframe": kwargs["timeframe"],
            "start_ts_ms": kwargs["start_ts_ms"],
            "end_ts_ms": kwargs["end_ts_ms"],
            "rows_written": 17,
        }

    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(
        repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(
        repair_dag_module.repair_interface,
        "enqueue_indicator_recalc",
        _fake_enqueue_indicator_recalc,
    )

    result = repair_dag_module.enqueue_indicator_recalc_task(
        ti=_TaskInstance(
            {
                "validate_swap_repair_conf": {
                    "trigger": "last-200-guard",
                    "recalc_specs": [],
                },
                "swap_repair": [
                    {
                        "status": "ok",
                        "symbol": "BTC-USDT-SWAP",
                        "timeframe": "1H",
                        "affected_recalc_range": (10, 100),
                    },
                    {
                        "status": "blocked",
                        "symbol": "ETH-USDT-SWAP",
                        "timeframe": "1H",
                        "affected_recalc_range": (20, 200),
                    },
                    {
                        "status": "ok",
                        "symbol": "XRP-USDT-SWAP",
                        "timeframe": "1H",
                        "affected_recalc_range": None,
                    },
                ],
            }
        )
    )

    assert calls == [
        {
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1H",
            "start_ts_ms": 10,
            "end_ts_ms": 100,
            "specs": [],
        }
    ]
    assert result == [
        {
            "status": "queued",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1H",
            "start_ts_ms": 10,
            "end_ts_ms": 100,
            "rows_written": 17,
        }
    ]


def test_publish_report_task_builds_concise_guard_summary(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)

    result = repair_dag_module.publish_report_task(
        ti=_TaskInstance(
            {
                "validate_swap_repair_conf": {
                    "trigger": "last-200-guard",
                    "publish_on_statuses": ["partial", "blocked"],
                },
                "swap_repair": [
                    {
                        "status": "ok",
                        "symbol": "BTC-USDT-SWAP",
                        "timeframe": "1H",
                        "affected_recalc_range": (10, 100),
                        "repaired_count": 3,
                        "corrupted_count": 1,
                        "unresolved_timestamps": [],
                    },
                    {
                        "status": "blocked",
                        "symbol": "ETH-USDT-SWAP",
                        "timeframe": "1H",
                        "affected_recalc_range": None,
                        "repaired_count": 0,
                        "corrupted_count": 2,
                        "unresolved_timestamps": [20, 30],
                    },
                ],
                "enqueue_indicator_recalc": [
                    {
                        "status": "queued",
                        "symbol": "BTC-USDT-SWAP",
                        "timeframe": "1H",
                        "rows_written": 17,
                    }
                ],
            }
        ),
        dag_run=SimpleNamespace(run_id="manual__2026-05-07T09:00:00+00:00"),
        logical_date=__import__("datetime").datetime(2026, 5, 7, 9, 0),
    )

    assert result == {
        "trigger": "last-200-guard",
        "run_id": "manual__2026-05-07T09:00:00+00:00",
        "status_counts": {"ok": 1, "blocked": 1},
        "non_ok": [
            {
                "symbol": "ETH-USDT-SWAP",
                "timeframe": "1H",
                "status": "blocked",
                "unresolved_timestamps": [20, 30],
                "corrupted_count": 2,
                "repaired_count": 0,
            }
        ],
        "recalc_enqueued": 1,
    }


def test_preflight_instrument_check_task_validates_every_curated_symbol(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    checked: list[str] = []

    class _FakeRepo:
        async def instrument_exists(self, symbol: str) -> bool:
            checked.append(symbol)
            return True

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> Any:
            return asyncio.run(coro)

    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(
        repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(repair_dag_module, "InstrumentSqlRepository", _FakeRepo)

    repair_dag_module.preflight_instrument_check_task(
        ti=_TaskInstance(
            {
                "trigger": "repair-all-swaps",
                "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
            }
        )
    )

    assert checked == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]


def test_preflight_instrument_check_task_raises_for_unknown_symbol(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    class _FakeRepo:
        async def instrument_exists(self, symbol: str) -> bool:
            return symbol != "FAKE-USDT-SWAP"

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> Any:
            return asyncio.run(coro)

    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(
        repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(repair_dag_module, "InstrumentSqlRepository", _FakeRepo)

    with pytest.raises(repair_dag_module.InstrumentNotFoundError):
        repair_dag_module.preflight_instrument_check_task(
            ti=_TaskInstance(
                {
                    "trigger": "repair-all-swaps",
                    "symbols": ["BTC-USDT-SWAP", "FAKE-USDT-SWAP"],
                }
            )
        )


def test_ensure_instruments_loaded_task_calls_ensure_symbols_registered(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    ensure_calls: list[dict[str, Any]] = []

    async def _fake_ensure(symbols: list[str], *, repository: Any, logger: Any) -> None:
        ensure_calls.append({"symbols": symbols})

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> Any:
            return asyncio.run(coro)

    monkeypatch.setattr(repair_dag_module, "ensure_symbols_registered", _fake_ensure)
    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(
        repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(repair_dag_module, "InstrumentSqlRepository", lambda: object())

    repair_dag_module.ensure_instruments_loaded_task(
        ti=_TaskInstance(
            {
                "trigger": "repair-all-swaps",
                "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"],
            }
        )
    )

    assert len(ensure_calls) == 1
    assert ensure_calls[0]["symbols"] == [
        "BTC-USDT-SWAP",
        "ETH-USDT-SWAP",
        "SOL-USDT-SWAP",
    ]


def _make_swap_repair_xcom_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mode": "apply",
        "strategy": "gap-repair",
        "symbol": "BTC-USDT-SWAP",
        "timeframe": "1m",
        "window": {"start_ts_ms": 10, "end_ts_ms": 100},
        "gap_tasks": 1,
        "requested_bars": 5,
        "remaining_gap_tasks": 0,
        "remaining_requested_bars": 0,
        "verification_method": "gap-detection",
        "rows_written": 5,
        "fetch_calls": 1,
        "verified": True,
        "guardrail_violations": [],
        "watermark_updated": False,
    }
    payload.update(overrides)
    return payload


def test_xcom_accepts_payload_without_new_fields() -> None:
    from ops.airflow.dags._common.repair import validate_swap_repair_xcom_payload

    payload = _make_swap_repair_xcom_payload()
    normalized = validate_swap_repair_xcom_payload(payload)
    assert "outcome" not in normalized
    assert "received_bars" not in normalized


def test_xcom_accepts_payload_with_new_fields() -> None:
    from ops.airflow.dags._common.repair import validate_swap_repair_xcom_payload

    payload = _make_swap_repair_xcom_payload(
        outcome="partial",
        received_bars=3,
        remaining_missing_before=5,
        remaining_missing_after=2,
        progress=3,
        api_fill_ratio=0.6,
        write_success_ratio=1.0,
        blocked=True,
        blocked_reason="empty-chunk",
        blocked_cause="api_returned_empty",
    )
    normalized = validate_swap_repair_xcom_payload(payload)
    assert normalized["outcome"] == "partial"
    assert normalized["received_bars"] == 3
    assert normalized["progress"] == 3
    assert normalized["api_fill_ratio"] == pytest.approx(0.6)
    assert normalized["write_success_ratio"] == pytest.approx(1.0)
    assert normalized["blocked"] is True
    assert normalized["blocked_reason"] == "empty-chunk"
    assert normalized["blocked_cause"] == "api_returned_empty"


def test_xcom_rejects_invalid_outcome_value() -> None:
    from ops.airflow.dags._common.repair import validate_swap_repair_xcom_payload

    payload = _make_swap_repair_xcom_payload(outcome="bogus")
    with pytest.raises(ValueError, match="outcome must be one of"):
        validate_swap_repair_xcom_payload(payload)


def test_xcom_rejects_non_numeric_api_fill_ratio() -> None:
    from ops.airflow.dags._common.repair import validate_swap_repair_xcom_payload

    payload = _make_swap_repair_xcom_payload(api_fill_ratio="not-a-number")
    with pytest.raises(ValueError, match="api_fill_ratio must be numeric"):
        validate_swap_repair_xcom_payload(payload)


def test_xcom_rejects_non_integer_progress() -> None:
    from ops.airflow.dags._common.repair import validate_swap_repair_xcom_payload

    payload = _make_swap_repair_xcom_payload(progress="not-an-int")
    with pytest.raises(ValueError, match="'progress'"):
        validate_swap_repair_xcom_payload(payload)


def test_xcom_rejects_non_boolean_blocked() -> None:
    from ops.airflow.dags._common.repair import validate_swap_repair_xcom_payload

    payload = _make_swap_repair_xcom_payload(blocked="yes")
    with pytest.raises(ValueError, match="blocked must be a boolean"):
        validate_swap_repair_xcom_payload(payload)


def test_xcom_rejects_non_string_blocked_cause() -> None:
    from ops.airflow.dags._common.repair import validate_swap_repair_xcom_payload

    payload = _make_swap_repair_xcom_payload(blocked_cause=123)
    with pytest.raises(ValueError, match="blocked_cause must be a string"):
        validate_swap_repair_xcom_payload(payload)


def test_swap_repair_task_translates_guardrail_valueerror_to_airflow_fail(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    async def _raise_guardrail(**_kwargs: Any) -> dict[str, Any]:
        raise ValueError("apply blocked by guardrails: RANGE_TOO_LONG")

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> dict[str, Any]:
            import asyncio

            return asyncio.run(coro)

    monkeypatch.setattr(
        repair_dag_module.repair_interface,
        "run_swap_repair_auto_apply",
        _raise_guardrail,
    )
    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(
        repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)

    airflow_exceptions = sys.modules.get("airflow.exceptions")
    assert (
        airflow_exceptions is not None
    ), "airflow.exceptions not loaded via DAG module"
    AirflowFailException = airflow_exceptions.AirflowFailException

    with pytest.raises(AirflowFailException, match="apply blocked by guardrails"):
        repair_dag_module.swap_repair_task(
            ti=_TaskInstance(
                {
                    "trigger": "repair-all-swaps",
                    "symbols": ["BTC-USDT-SWAP"],
                    "timeframes": ["1H"],
                    "mode": "apply",
                    "repair_strategy": "gap-repair",
                    "padding_bars": 0,
                    "max_gap_tasks_per_run": 50,
                    "max_requested_bars_per_run": 10_000,
                    "max_range_days": 7,
                    "max_fail_ratio": 1.0,
                    "auto_apply_anchor_strategy": "listing-date",
                    "anchor_ts_ms": None,
                    "auto_apply_window": True,
                    "critical_timeframes": ["1H"],
                    "no_progress_threshold": 1,
                }
            )
        )


def test_swap_repair_task_translates_no_progress_valueerror_to_airflow_fail(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    async def _raise_no_progress(**_kwargs: Any) -> dict[str, Any]:
        raise ValueError("no progress on critical TF 1H: 1 iterations in a row")

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> dict[str, Any]:
            import asyncio

            return asyncio.run(coro)

    monkeypatch.setattr(
        repair_dag_module.repair_interface,
        "run_swap_repair_auto_apply",
        _raise_no_progress,
    )
    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(
        repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)

    airflow_exceptions = sys.modules.get("airflow.exceptions")
    assert airflow_exceptions is not None
    AirflowFailException = airflow_exceptions.AirflowFailException

    with pytest.raises(AirflowFailException, match="no progress on critical TF"):
        repair_dag_module.swap_repair_task(
            ti=_TaskInstance(
                {
                    "trigger": "repair-all-swaps",
                    "symbols": ["BTC-USDT-SWAP"],
                    "timeframes": ["1H"],
                    "mode": "apply",
                    "repair_strategy": "gap-repair",
                    "padding_bars": 0,
                    "max_gap_tasks_per_run": 50,
                    "max_requested_bars_per_run": 10_000,
                    "max_range_days": 7,
                    "max_fail_ratio": 1.0,
                    "auto_apply_anchor_strategy": "listing-date",
                    "anchor_ts_ms": None,
                    "auto_apply_window": True,
                    "critical_timeframes": ["1H"],
                    "no_progress_threshold": 1,
                }
            )
        )


def test_swap_repair_task_does_not_translate_other_exceptions(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _raise_transport(**_kwargs: Any) -> dict[str, Any]:
        raise TimeoutError("upstream OKX API timeout")

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> dict[str, Any]:
            import asyncio

            return asyncio.run(coro)

    monkeypatch.setattr(
        repair_dag_module.repair_interface,
        "run_swap_repair_auto_apply",
        _raise_transport,
    )
    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(
        repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)

    with pytest.raises(TimeoutError, match="upstream OKX API timeout"):
        repair_dag_module.swap_repair_task(
            ti=_TaskInstance(
                {
                    "trigger": "repair-all-swaps",
                    "symbols": ["BTC-USDT-SWAP"],
                    "timeframes": ["1H"],
                    "mode": "apply",
                    "repair_strategy": "gap-repair",
                    "padding_bars": 0,
                    "max_gap_tasks_per_run": 50,
                    "max_requested_bars_per_run": 10_000,
                    "max_range_days": 7,
                    "max_fail_ratio": 1.0,
                    "auto_apply_anchor_strategy": "listing-date",
                    "anchor_ts_ms": None,
                    "auto_apply_window": True,
                    "critical_timeframes": ["1H"],
                    "no_progress_threshold": 1,
                }
            )
        )


def test_publish_swap_repair_ops_calls_guard_audit_for_last_n_strategy(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """publish_swap_repair_ops must call write_guard_repair_audit (not skip) for guard trigger."""
    import asyncio

    guard_payloads = [
        {
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1H",
            "status": "ok",
            "strategy": "last_n_closed_bars",
            "mode": "apply",
            "repaired_count": 2,
            "corrupted_count": 0,
            "unresolved_timestamps": [],
            "affected_recalc_range": (1_700_000_000_000, 1_700_010_000_000),
            "run_id": "r1",
            "algo_version": "1",
            "params_hash": "h1",
        }
    ]
    validated = {
        "trigger": "last-200-guard",
        "repair_strategy": "last_n_closed_bars",
        "bars": 200,
        "timeframes": ["1H"],
        "symbols": ["BTC-USDT-SWAP"],
        "mode": "apply",
        "publish_on_statuses": ["partial"],
        "recalc_specs": [],
        "critical_timeframes": ["1H"],
    }

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> Any:
            return asyncio.run(coro)

    audit_calls: list[dict[str, Any]] = []

    async def _fake_guard_audit(**kwargs: Any) -> int:
        audit_calls.append(kwargs)
        return len(kwargs["guard_payloads"])

    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(
        repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(
        repair_dag_module,
        "push_swap_repair_metrics",
        lambda payloads: True,
    )
    monkeypatch.setattr(
        repair_dag_module, "write_guard_repair_audit", _fake_guard_audit
    )

    result = repair_dag_module.publish_swap_repair_ops_task(
        ti=_TaskInstance(
            {
                "validate_swap_repair_conf": validated,
                "validate_swap_repair_xcom": guard_payloads,
                "swap_repair": guard_payloads,
            }
        ),
        dag_run=SimpleNamespace(run_id="run_123"),
        logical_date=None,
    )

    assert result["audit_rows_written"] == 1
    assert len(audit_calls) == 1
    assert audit_calls[0]["dag_id"] == "okx_swap_repair_v1"
