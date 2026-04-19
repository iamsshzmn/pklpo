from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

SUPPORTED_TIMEFRAMES = ("1m", "1H", "4H", "1D", "1W", "1M")


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
    monkeypatch.setitem(sys.modules, "airflow.operators.python", airflow_operators_python)

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
        if isinstance(self._payload, dict) and task_ids in self._payload:
            assert key == "return_value"
            return self._payload[task_ids]
        if task_ids == "validate_swap_repair_conf":
            assert key == "return_value"
            return self._payload
        assert task_ids == "swap_repair"
        assert key == "return_value"
        return self._payload


@dataclass
class _TypedSwapRepairSummary:
    mode: str
    strategy: str
    symbol: str
    timeframe: str
    window: dict[str, int]
    gap_tasks: int
    requested_bars: int
    remaining_gap_tasks: int
    remaining_requested_bars: int
    verification_method: str
    rows_written: int
    fetch_calls: int
    verified: bool
    guardrail_violations: list[str]
    watermark_updated: bool
    auto_apply_incomplete: bool = False


def test_validate_swap_repair_conf_accepts_legacy_single_timeframe(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(repair_dag_module, "_utc_now_ts_ms", lambda: 1_775_023_200_000)

    result = repair_dag_module.validate_swap_repair_conf_task(
        dag_run=SimpleNamespace(
            conf={
                "mode": "detect-only",
                "repair_strategy": "gap-repair",
                "timeframe": "1m",
                "start": "2026-04-01T00:00:00Z",
                "end": "2026-04-01T08:00:00Z",
            }
        )
    )

    assert result["symbol"] == "BTC-USDT-SWAP"
    assert result["timeframes"] == ["1m"]
    assert result["mode"] == "detect-only"
    assert result["repair_strategy"] == "gap-repair"
    assert result["end_ts_ms"] == 1_775_023_200_000


def test_repair_dag_default_args_include_alert_callbacks(
    repair_dag_module: types.ModuleType,
) -> None:
    assert repair_dag_module.default_args["on_failure_callback"] == "failure_cb"
    assert repair_dag_module.default_args["on_success_callback"] == "success_cb"
    assert repair_dag_module.default_args["on_retry_callback"] == "retry_cb"


def test_repair_dag_params_contract_snapshot(
    repair_dag_module: types.ModuleType,
) -> None:
    assert _normalize_param_contract(repair_dag_module.dag.kwargs["params"]) == {
        "symbol": {
            "default": None,
            "type": ["null", "string"],
            "description": "Required: OKX swap instId (e.g. BTC-USDT-SWAP)",
        },
        "timeframes": {
            "default": ["1m", "1H", "4H", "1D", "1W", "1M"],
            "type": "array",
            "items": {"type": "string", "enum": ["1m", "1H", "4H", "1D", "1W", "1M"]},
            "minItems": 1,
            "description": "Repair-safe OKX timeframes",
        },
        "mode": {
            "default": "detect-only",
            "type": "string",
            "enum": ["detect-only", "dry-run", "apply"],
        },
        "repair_strategy": {
            "default": "gap-repair",
            "type": "string",
            "enum": ["backfill", "gap-repair"],
        },
        "start": {
            "default": None,
            "type": ["null", "string"],
            "format": "date-time",
        },
        "end": {
            "default": None,
            "type": ["null", "string"],
            "format": "date-time",
        },
        "auto_apply_anchor_strategy": {
            "default": "first-coverage",
            "type": "string",
            "enum": ["first-coverage", "listing-date", "explicit"],
            "description": "Anchor strategy for apply runs without existing coverage",
        },
        "auto_apply_anchor": {
            "default": None,
            "type": ["null", "string"],
            "format": "date-time",
            "description": "Optional explicit anchor for apply runs without coverage",
        },
        "window_hours": {
            "default": 6,
            "type": "integer",
            "minimum": 1,
        },
        "padding_bars": {
            "default": 0,
            "type": "integer",
            "minimum": 0,
        },
        "max_gap_tasks_per_run": {
            "default": 50,
            "type": "integer",
            "minimum": 1,
        },
        "max_requested_bars_per_run": {
            "default": 10_000,
            "type": "integer",
            "minimum": 1,
        },
        "max_range_days": {
            "default": 7,
            "type": "integer",
            "minimum": 1,
        },
        "max_fail_ratio": {
            "default": 0.1,
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
    }


def test_validate_swap_repair_conf_accepts_dag_params_defaults(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(repair_dag_module, "_utc_now_ts_ms", lambda: 1_775_023_200_000)

    result = repair_dag_module.validate_swap_repair_conf_task(
        params={
            "symbol": "BTC-USDT-SWAP",
            "timeframes": ["1m", "1H"],
            "mode": "detect-only",
            "repair_strategy": "gap-repair",
            "start": "2026-04-01T00:00:00Z",
            "end": "2026-04-01T08:00:00Z",
        }
    )

    assert result["symbol"] == "BTC-USDT-SWAP"
    assert result["timeframes"] == ["1m", "1H"]


def test_validate_swap_repair_conf_dag_run_conf_overrides_params(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(repair_dag_module, "_utc_now_ts_ms", lambda: 1_775_023_200_000)

    result = repair_dag_module.validate_swap_repair_conf_task(
        params={
            "symbol": "BTC-USDT-SWAP",
            "timeframes": ["1m"],
            "mode": "detect-only",
            "repair_strategy": "gap-repair",
            "start": "2026-04-01T00:00:00Z",
            "end": "2026-04-01T08:00:00Z",
        },
        dag_run=SimpleNamespace(conf={"timeframes": ["4H"]}),
    )

    assert result["timeframes"] == ["4H"]


def test_validate_swap_repair_conf_apply_without_window_enables_auto_apply_window(
    repair_dag_module: types.ModuleType,
) -> None:
    result = repair_dag_module.validate_swap_repair_conf_task(
        dag_run=SimpleNamespace(
            conf={
                "mode": "apply",
                "repair_strategy": "gap-repair",
                "timeframes": ["1m"],
            }
        )
    )

    assert result["auto_apply_window"] is True
    assert result["start_ts_ms"] is None
    assert result["end_ts_ms"] is None


def test_validate_swap_repair_conf_parses_auto_apply_anchor(
    repair_dag_module: types.ModuleType,
) -> None:
    result = repair_dag_module.validate_swap_repair_conf_task(
        dag_run=SimpleNamespace(
            conf={
                "mode": "apply",
                "repair_strategy": "gap-repair",
                "timeframes": ["1m"],
                "auto_apply_anchor": "2026-04-01T00:00:00Z",
            }
        )
    )

    assert result["auto_apply_window"] is True
    assert result["anchor_ts_ms"] == 1_775_001_600_000


def test_validate_swap_repair_conf_accepts_listing_date_anchor_strategy(
    repair_dag_module: types.ModuleType,
) -> None:
    result = repair_dag_module.validate_swap_repair_conf_task(
        dag_run=SimpleNamespace(
            conf={
                "mode": "apply",
                "repair_strategy": "gap-repair",
                "timeframes": ["1m"],
                "auto_apply_anchor_strategy": "listing-date",
            }
        )
    )

    assert result["auto_apply_window"] is True
    assert result["auto_apply_anchor_strategy"] == "listing-date"


def test_validate_swap_repair_conf_rejects_missing_timeframes(
    repair_dag_module: types.ModuleType,
) -> None:
    with pytest.raises(ValueError, match="requires explicit timeframes or legacy timeframe"):
        repair_dag_module.validate_swap_repair_conf_task(
            dag_run=SimpleNamespace(conf={})
        )


@pytest.mark.parametrize("timeframes", [[], "", None])
def test_validate_swap_repair_conf_rejects_empty_timeframes(
    repair_dag_module: types.ModuleType,
    timeframes: Any,
) -> None:
    with pytest.raises(
        ValueError,
        match=r"requires explicit timeframes or legacy timeframe|timeframes is empty after normalization",
    ):
        repair_dag_module.validate_swap_repair_conf_task(
            dag_run=SimpleNamespace(conf={"timeframes": timeframes})
        )


def test_validate_swap_repair_conf_apply_without_explicit_window_uses_auto_mode(
    repair_dag_module: types.ModuleType,
) -> None:
    result = repair_dag_module.validate_swap_repair_conf_task(
        dag_run=SimpleNamespace(conf={"mode": "apply", "timeframe": "1m"})
    )

    assert result["auto_apply_window"] is True
    assert result["start_ts_ms"] is None
    assert result["end_ts_ms"] is None


def test_validate_swap_repair_conf_rejects_partial_window_bounds(
    repair_dag_module: types.ModuleType,
) -> None:
    with pytest.raises(
        ValueError,
        match="requires both start and end when either is provided",
    ):
        repair_dag_module.validate_swap_repair_conf_task(
            dag_run=SimpleNamespace(
                conf={
                    "mode": "detect-only",
                    "repair_strategy": "gap-repair",
                    "timeframe": "1m",
                    "start": "2026-04-01T00:00:00Z",
                }
            )
        )


@pytest.mark.parametrize(
    ("field_name", "field_value", "message"),
    [
        ("window_hours", "oops", "must be an integer"),
        ("padding_bars", "oops", "must be an integer"),
        ("max_fail_ratio", "oops", "must be a number"),
    ],
)
def test_validate_swap_repair_conf_rejects_invalid_numeric_fields(
    repair_dag_module: types.ModuleType,
    field_name: str,
    field_value: Any,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=rf"field '{field_name}'.*{message}"):
        repair_dag_module.validate_swap_repair_conf_task(
            dag_run=SimpleNamespace(
                conf={
                    "mode": "detect-only",
                    "repair_strategy": "gap-repair",
                    "timeframes": ["1m"],
                    field_name: field_value,
                }
            )
        )


@pytest.mark.parametrize("timeframe", ["5m", "15m", "30m", "12H", "2m", "3H"])
def test_validate_swap_repair_conf_rejects_unsupported_timeframe(
    repair_dag_module: types.ModuleType,
    timeframe: str,
) -> None:
    with pytest.raises(ValueError, match="Unsupported repair timeframe"):
        repair_dag_module.validate_swap_repair_conf_task(
            dag_run=SimpleNamespace(conf={"timeframe": timeframe})
        )


def test_validate_swap_repair_conf_accepts_timeframes_list_and_deduplicates(
    repair_dag_module: types.ModuleType,
) -> None:
    result = repair_dag_module.validate_swap_repair_conf_task(
        dag_run=SimpleNamespace(conf={"timeframes": ["1m", "1H", "1m"]})
    )

    assert result["timeframes"] == ["1m", "1H"]


def test_normalize_swap_repair_conf_returns_typed_dto(
    repair_dag_module: types.ModuleType,
) -> None:
    validated = repair_dag_module.normalize_swap_repair_conf(
        {
            "mode": "apply",
            "repair_strategy": "gap-repair",
            "timeframes": ["1m"],
            "auto_apply_anchor_strategy": "explicit",
            "auto_apply_anchor": "2026-04-01T00:00:00Z",
        }
    )

    assert validated.symbol == "BTC-USDT-SWAP"
    assert validated.timeframes == ["1m"]
    assert validated.auto_apply_window is True
    assert validated.anchor_ts_ms == 1_775_001_600_000
    assert validated.to_dict()["auto_apply_anchor_strategy"] == "explicit"


def test_validate_swap_repair_xcom_accepts_detect_only_payload(
    repair_dag_module: types.ModuleType,
) -> None:
    payload = {
        "mode": "detect-only",
        "strategy": "gap-repair",
        "symbol": "BTC-USDT-SWAP",
        "timeframe": "1m",
        "window": {"start_ts_ms": 1, "end_ts_ms": 2},
        "gap_tasks": 2,
        "requested_bars": 5,
        "remaining_gap_tasks": 2,
        "remaining_requested_bars": 5,
        "verification_method": "plan-only",
        "rows_written": 0,
        "fetch_calls": 0,
        "verified": False,
        "guardrail_violations": [],
        "watermark_updated": False,
    }

    result = repair_dag_module.validate_swap_repair_xcom_task(ti=_TaskInstance(payload))

    assert result == [
        {
            "mode": "detect-only",
            "strategy": "gap-repair",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "window": {"start_ts_ms": 1, "end_ts_ms": 2},
            "gap_tasks": 2,
            "requested_bars": 5,
            "remaining_gap_tasks": 2,
            "remaining_requested_bars": 5,
            "verification_method": "plan-only",
            "rows_written": 0,
            "fetch_calls": 0,
            "verified": False,
            "padding_bars": 0,
            "guardrail_violations": [],
            "watermark_updated": False,
            "auto_apply_incomplete": True,
        }
    ]


def test_validate_swap_repair_xcom_accepts_payload_list(
    repair_dag_module: types.ModuleType,
) -> None:
    payload = {
        "mode": "detect-only",
        "strategy": "gap-repair",
        "symbol": "BTC-USDT-SWAP",
        "timeframe": "1m",
        "window": {"start_ts_ms": 1, "end_ts_ms": 2},
        "gap_tasks": 2,
        "requested_bars": 5,
        "remaining_gap_tasks": 2,
        "remaining_requested_bars": 5,
        "verification_method": "plan-only",
        "rows_written": 0,
        "fetch_calls": 0,
        "verified": False,
        "guardrail_violations": [],
        "watermark_updated": False,
    }

    result = repair_dag_module.validate_swap_repair_xcom_task(ti=_TaskInstance([payload, payload]))

    assert result == [
        {
            "mode": "detect-only",
            "strategy": "gap-repair",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "window": {"start_ts_ms": 1, "end_ts_ms": 2},
            "gap_tasks": 2,
            "requested_bars": 5,
            "remaining_gap_tasks": 2,
            "remaining_requested_bars": 5,
            "verification_method": "plan-only",
            "rows_written": 0,
            "fetch_calls": 0,
            "verified": False,
            "padding_bars": 0,
            "guardrail_violations": [],
            "watermark_updated": False,
            "auto_apply_incomplete": True,
        },
        {
            "mode": "detect-only",
            "strategy": "gap-repair",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "window": {"start_ts_ms": 1, "end_ts_ms": 2},
            "gap_tasks": 2,
            "requested_bars": 5,
            "remaining_gap_tasks": 2,
            "remaining_requested_bars": 5,
            "verification_method": "plan-only",
            "rows_written": 0,
            "fetch_calls": 0,
            "verified": False,
            "padding_bars": 0,
            "guardrail_violations": [],
            "watermark_updated": False,
            "auto_apply_incomplete": True,
        },
    ]


def test_validate_swap_repair_xcom_accepts_typed_summary_payload(
    repair_dag_module: types.ModuleType,
) -> None:
    payload = _TypedSwapRepairSummary(
        mode="detect-only",
        strategy="gap-repair",
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        window={"start_ts_ms": 1, "end_ts_ms": 2},
        gap_tasks=2,
        requested_bars=5,
        remaining_gap_tasks=2,
        remaining_requested_bars=5,
        verification_method="plan-only",
        rows_written=0,
        fetch_calls=0,
        verified=False,
        guardrail_violations=[],
        watermark_updated=False,
    )

    result = repair_dag_module.validate_swap_repair_xcom_task(ti=_TaskInstance(payload))

    assert result == [
        {
            "mode": "detect-only",
            "strategy": "gap-repair",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "window": {"start_ts_ms": 1, "end_ts_ms": 2},
            "gap_tasks": 2,
            "requested_bars": 5,
            "remaining_gap_tasks": 2,
            "remaining_requested_bars": 5,
            "verification_method": "plan-only",
            "rows_written": 0,
            "fetch_calls": 0,
            "verified": False,
            "padding_bars": 0,
            "guardrail_violations": [],
            "watermark_updated": False,
            "auto_apply_incomplete": True,
        }
    ]


def test_validate_swap_repair_xcom_accepts_empty_window_noop_payload(
    repair_dag_module: types.ModuleType,
) -> None:
    payload = {
        "mode": "detect-only",
        "strategy": "gap-repair",
        "symbol": "BTC-USDT-SWAP",
        "timeframe": "1D",
        "window": {"start_ts_ms": 10, "end_ts_ms": 10},
        "gap_tasks": 0,
        "requested_bars": 0,
        "remaining_gap_tasks": 0,
        "remaining_requested_bars": 0,
        "verification_method": "plan-only",
        "rows_written": 0,
        "fetch_calls": 0,
        "verified": False,
        "guardrail_violations": [],
        "watermark_updated": False,
    }

    result = repair_dag_module.validate_swap_repair_xcom_task(ti=_TaskInstance(payload))

    assert result == [
        {
            "mode": "detect-only",
            "strategy": "gap-repair",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1D",
            "window": {"start_ts_ms": 10, "end_ts_ms": 10},
            "gap_tasks": 0,
            "requested_bars": 0,
            "remaining_gap_tasks": 0,
            "remaining_requested_bars": 0,
            "verification_method": "plan-only",
            "rows_written": 0,
            "fetch_calls": 0,
            "verified": False,
            "padding_bars": 0,
            "guardrail_violations": [],
            "watermark_updated": False,
        }
    ]


def test_validate_swap_repair_xcom_accepts_partial_apply_payload(
    repair_dag_module: types.ModuleType,
) -> None:
    payload = {
        "mode": "apply",
        "strategy": "gap-repair",
        "symbol": "BTC-USDT-SWAP",
        "timeframe": "1m",
        "window": {"start_ts_ms": 10, "end_ts_ms": 20},
        "gap_tasks": 4,
        "requested_bars": 12,
        "remaining_gap_tasks": 2,
        "remaining_requested_bars": 6,
        "verification_method": "gap-detection",
        "rows_written": 6,
        "fetch_calls": 1,
        "verified": False,
        "guardrail_violations": [],
        "watermark_updated": False,
        "auto_apply_incomplete": True,
    }

    result = repair_dag_module.validate_swap_repair_xcom_task(ti=_TaskInstance(payload))

    assert result == [
        {
            "mode": "apply",
            "strategy": "gap-repair",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "window": {"start_ts_ms": 10, "end_ts_ms": 20},
            "gap_tasks": 4,
            "requested_bars": 12,
            "remaining_gap_tasks": 2,
            "remaining_requested_bars": 6,
            "verification_method": "gap-detection",
            "rows_written": 6,
            "fetch_calls": 1,
            "verified": False,
            "padding_bars": 0,
            "guardrail_violations": [],
            "watermark_updated": False,
            "auto_apply_incomplete": True,
        }
    ]


def test_validate_swap_repair_xcom_rejects_empty_window_with_work(
    repair_dag_module: types.ModuleType,
) -> None:
    payload = {
        "mode": "detect-only",
        "strategy": "gap-repair",
        "symbol": "BTC-USDT-SWAP",
        "timeframe": "1D",
        "window": {"start_ts_ms": 10, "end_ts_ms": 10},
        "gap_tasks": 1,
        "requested_bars": 1,
        "remaining_gap_tasks": 1,
        "remaining_requested_bars": 1,
        "verification_method": "plan-only",
        "rows_written": 0,
        "fetch_calls": 0,
        "verified": False,
        "guardrail_violations": [],
        "watermark_updated": False,
    }

    with pytest.raises(ValueError, match=r"timeframe='1D': .*empty window is allowed only for no-op results"):
        repair_dag_module.validate_swap_repair_xcom_task(ti=_TaskInstance(payload))


def test_validate_swap_repair_xcom_rejects_apply_with_remaining_gaps(
    repair_dag_module: types.ModuleType,
) -> None:
    payload = {
        "mode": "apply",
        "strategy": "gap-repair",
        "symbol": "BTC-USDT-SWAP",
        "timeframe": "1m",
        "window": {"start_ts_ms": 1, "end_ts_ms": 2},
        "gap_tasks": 2,
        "requested_bars": 5,
        "remaining_gap_tasks": 1,
        "remaining_requested_bars": 1,
        "verification_method": "gap-detection",
        "rows_written": 5,
        "fetch_calls": 1,
        "verified": True,
        "guardrail_violations": [],
        "watermark_updated": False,
    }

    with pytest.raises(ValueError, match=r"timeframe='1m': .*must not leave remaining gaps"):
        repair_dag_module.validate_swap_repair_xcom_task(ti=_TaskInstance(payload))


@pytest.mark.parametrize("symbol", ["BTC-USDT-SWAP", "ETH-USDT-SWAP"])
@pytest.mark.parametrize("timeframe", SUPPORTED_TIMEFRAMES)
def test_swap_repair_task_uses_validated_conf_payload(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    symbol: str,
    timeframe: str,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _fake_run_swap_repair(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "mode": kwargs["mode"].value,
            "strategy": kwargs["strategy"].value,
            "symbol": kwargs["symbol"],
            "timeframe": kwargs["timeframe"],
            "window": {
                "start_ts_ms": kwargs["start_ts_ms"],
                "end_ts_ms": kwargs["end_ts_ms"],
            },
            "gap_tasks": 0,
            "requested_bars": 0,
            "remaining_gap_tasks": 0,
            "remaining_requested_bars": 0,
            "verification_method": "plan-only",
            "rows_written": 0,
            "fetch_calls": 0,
            "verified": False,
            "guardrail_violations": [],
            "watermark_updated": False,
        }

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> dict[str, Any]:
            import asyncio

            return asyncio.run(coro)

    monkeypatch.setattr(repair_dag_module.repair_interface, "run_swap_repair", _fake_run_swap_repair)
    monkeypatch.setattr(repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"})
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())

    result = repair_dag_module.swap_repair_task(
        ti=_TaskInstance(
            {
                "symbol": symbol,
                "timeframes": [timeframe],
                "mode": "detect-only",
                "repair_strategy": "gap-repair",
                "start_ts_ms": 1,
                "end_ts_ms": 2,
                "padding_bars": 0,
                "max_gap_tasks_per_run": 50,
                "max_requested_bars_per_run": 10_000,
                "max_range_days": 7,
                "max_fail_ratio": 0.1,
                "auto_apply_anchor_strategy": "first-coverage",
                "anchor_ts_ms": None,
                "auto_apply_window": False,
            }
        )
    )

    assert result[0]["symbol"] == symbol
    assert calls[0]["symbol"] == symbol
    assert calls[0]["timeframe"] == timeframe


def test_swap_repair_task_runs_for_each_requested_timeframe(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _fake_run_swap_repair(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "mode": kwargs["mode"].value,
            "strategy": kwargs["strategy"].value,
            "symbol": kwargs["symbol"],
            "timeframe": kwargs["timeframe"],
            "window": {
                "start_ts_ms": kwargs["start_ts_ms"],
                "end_ts_ms": kwargs["end_ts_ms"],
            },
            "gap_tasks": 0,
            "requested_bars": 0,
            "remaining_gap_tasks": 0,
            "remaining_requested_bars": 0,
            "verification_method": "plan-only",
            "rows_written": 0,
            "fetch_calls": 0,
            "verified": False,
            "guardrail_violations": [],
            "watermark_updated": False,
        }

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> dict[str, Any]:
            import asyncio

            return asyncio.run(coro)

    monkeypatch.setattr(repair_dag_module.repair_interface, "run_swap_repair", _fake_run_swap_repair)
    monkeypatch.setattr(repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"})
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())

    result = repair_dag_module.swap_repair_task(
        ti=_TaskInstance(
            {
                "symbol": "BTC-USDT-SWAP",
                "timeframes": ["1m", "1H"],
                "mode": "detect-only",
                "repair_strategy": "gap-repair",
                "start_ts_ms": 1,
                "end_ts_ms": 2,
                "padding_bars": 0,
                "max_gap_tasks_per_run": 50,
                "max_requested_bars_per_run": 10_000,
                "max_range_days": 7,
                "max_fail_ratio": 0.1,
                "auto_apply_anchor_strategy": "first-coverage",
                "anchor_ts_ms": None,
                "auto_apply_window": False,
            }
        )
    )

    assert [call["timeframe"] for call in calls] == ["1m", "1H"]
    assert [item["timeframe"] for item in result] == ["1m", "1H"]


def test_swap_repair_preview_task_plans_each_requested_timeframe(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _fake_plan_swap_repair(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "requested_mode": kwargs["mode"].value,
            "strategy": kwargs["strategy"].value,
            "symbol": kwargs["symbol"],
            "timeframe": kwargs["timeframe"],
            "window": {"start_ts_ms": 10, "end_ts_ms": 100},
            "auto_apply_window": kwargs["auto_apply_window"],
            "gap_tasks": 2,
            "requested_bars": 20,
            "expected_iteration_count": 2,
            "guardrail_risk": "high",
            "guardrail_violations": ["max_range_days"],
        }

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> dict[str, Any]:
            import asyncio

            return asyncio.run(coro)

    monkeypatch.setattr(repair_dag_module.repair_interface, "plan_swap_repair", _fake_plan_swap_repair)
    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"})
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)

    result = repair_dag_module.swap_repair_preview_task(
        ti=_TaskInstance(
            {
                "symbol": "BTC-USDT-SWAP",
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

    assert [call["timeframe"] for call in calls] == ["1m", "1H"]
    assert all(call["auto_apply_anchor_strategy"] == "listing-date" for call in calls)
    assert result[0]["expected_iteration_count"] == 2
    assert result[1]["guardrail_risk"] == "high"


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
        return 2

    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"})
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(
        repair_dag_module,
        "push_swap_repair_metrics",
        lambda payloads: metrics_calls.append(payloads) or True,
    )
    monkeypatch.setattr(repair_dag_module, "write_swap_repair_audit", _fake_write_swap_repair_audit)

    result = repair_dag_module.publish_swap_repair_ops_task(
        ti=_TaskInstance(
            {
                "validate_swap_repair_conf": {
                    "symbol": "BTC-USDT-SWAP",
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
                    "auto_apply_anchor_strategy": "first-coverage",
                    "anchor_ts_ms": None,
                    "auto_apply_window": True,
                },
                "swap_repair_preview": [
                    {"timeframe": "1m", "expected_iteration_count": 2},
                    {"timeframe": "1H", "expected_iteration_count": 1},
                ],
                "validate_swap_repair_xcom": [
                    {
                        "symbol": "BTC-USDT-SWAP",
                        "timeframe": "1m",
                        "mode": "apply",
                        "strategy": "gap-repair",
                        "window": {"start_ts_ms": 10, "end_ts_ms": 100},
                        "gap_tasks": 2,
                        "requested_bars": 20,
                        "remaining_gap_tasks": 1,
                        "remaining_requested_bars": 0,
                        "verification_method": "gap-detection",
                        "rows_written": 20,
                        "fetch_calls": 2,
                        "verified": True,
                        "padding_bars": 0,
                        "guardrail_violations": [],
                        "watermark_updated": False,
                        "auto_apply_incomplete": False,
                    },
                    {
                        "symbol": "BTC-USDT-SWAP",
                        "timeframe": "1H",
                        "mode": "apply",
                        "strategy": "gap-repair",
                        "window": {"start_ts_ms": 100, "end_ts_ms": 200},
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
                ],
            }
        ),
        dag_run=SimpleNamespace(run_id="manual__2026-04-16T10:00:00+00:00"),
        logical_date=__import__("datetime").datetime(2026, 4, 16, 10, 0),
    )

    assert metrics_calls and len(metrics_calls[0]) == 2
    assert metrics_calls[0][0]["auto_apply_incomplete"] is True
    assert metrics_calls[0][1].get("auto_apply_incomplete") is None
    assert audit_calls and audit_calls[0]["dag_id"] == "okx_swap_repair_v1"
    assert result == {"metrics_pushed": True, "audit_rows_written": 2}


def test_swap_repair_task_auto_apply_calls_public_helper(
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
    monkeypatch.setattr(repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"})
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)

    result = repair_dag_module.swap_repair_task(
        ti=_TaskInstance(
            {
                "symbol": "BTC-USDT-SWAP",
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
                "auto_apply_anchor_strategy": "first-coverage",
                "anchor_ts_ms": None,
                "auto_apply_window": True,
            }
        )
    )

    assert [call["timeframe"] for call in calls] == ["1m", "1H"]
    assert all(call["symbol"] == "BTC-USDT-SWAP" for call in calls)
    assert all(call["max_range_days"] == 7 for call in calls)
    assert all(call["anchor_ts_ms"] is None for call in calls)
    assert all(call["auto_apply_anchor_strategy"] == "first-coverage" for call in calls)
    assert all(call["auto_apply_max_iterations"] == 100 for call in calls)
    assert result[0]["window"] == {"start_ts_ms": 10, "end_ts_ms": 100}
    assert result[1]["verified"] is True
    assert result[1]["window"] == {"start_ts_ms": 10, "end_ts_ms": 100}


def test_swap_repair_task_auto_apply_passes_anchor_to_helper(
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
            "window": {"start_ts_ms": kwargs["anchor_ts_ms"], "end_ts_ms": 100},
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
    monkeypatch.setattr(repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"})
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)

    result = repair_dag_module.swap_repair_task(
        ti=_TaskInstance(
            {
                "symbol": "BTC-USDT-SWAP",
                "timeframes": ["1m"],
                "mode": "apply",
                "repair_strategy": "gap-repair",
                "start_ts_ms": None,
                "end_ts_ms": None,
                "padding_bars": 0,
                "max_gap_tasks_per_run": 50,
                "max_requested_bars_per_run": 10_000,
                "max_range_days": 7,
                "max_fail_ratio": 0.1,
                "anchor_ts_ms": 1_775_001_600_000,
                "auto_apply_anchor_strategy": "first-coverage",
                "auto_apply_window": True,
            }
        )
    )

    assert calls[0]["anchor_ts_ms"] == 1_775_001_600_000
    assert calls[0]["auto_apply_anchor_strategy"] == "first-coverage"
    assert result[0]["window"]["start_ts_ms"] == 1_775_001_600_000


def test_swap_repair_task_auto_apply_passes_listing_date_strategy_to_helper(
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
    monkeypatch.setattr(repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"})
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)

    repair_dag_module.swap_repair_task(
        ti=_TaskInstance(
            {
                "symbol": "BTC-USDT-SWAP",
                "timeframes": ["1m"],
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

    assert calls[0]["auto_apply_anchor_strategy"] == "listing-date"


def test_okx_swap_repair_v1_dag_does_not_define_local_auto_apply_fallback(
    repair_dag_module: types.ModuleType,
) -> None:
    assert not hasattr(repair_dag_module, "_get_auto_apply_helper")
    assert not hasattr(repair_dag_module, "_call_auto_apply_helper")
    assert not hasattr(repair_dag_module, "_run_auto_apply_for_timeframe_local")


def test_preflight_instrument_check_task_passes_for_known_symbol(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    class _FakeRepo:
        async def instrument_exists(self, symbol: str) -> bool:
            return True

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> Any:
            return asyncio.run(coro)

    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"})
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(repair_dag_module, "InstrumentSqlRepository", _FakeRepo)

    repair_dag_module.preflight_instrument_check_task(
        dag_run=SimpleNamespace(conf={"symbol": "ETH-USDT-SWAP"})
    )


def test_preflight_instrument_check_task_raises_for_unknown_symbol(
    repair_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    class _FakeRepo:
        async def instrument_exists(self, symbol: str) -> bool:
            return False

    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> Any:
            return asyncio.run(coro)

    monkeypatch.setattr(repair_dag_module, "_get_loop", lambda: _Loop())
    monkeypatch.setattr(repair_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"})
    monkeypatch.setattr(repair_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(repair_dag_module, "InstrumentSqlRepository", _FakeRepo)

    with pytest.raises(repair_dag_module.InstrumentNotFoundError):
        repair_dag_module.preflight_instrument_check_task(
            dag_run=SimpleNamespace(conf={"symbol": "FAKE-USDT-SWAP"})
        )
