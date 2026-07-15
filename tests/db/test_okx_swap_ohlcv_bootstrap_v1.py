"""Smoke tests for okx_swap_ohlcv_bootstrap_v1 DAG."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _load_bootstrap_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    class _DummyDAG:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs
            self.tasks: list[Any] = []
            self.schedule_interval = kwargs.get("schedule_interval")

        def __enter__(self) -> _DummyDAG:
            return self

        def __exit__(self, *exc: Any) -> None:
            pass

    class _DummyOperator:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.task_id: str = kwargs.get("task_id", "")
            self.args = args
            self.kwargs = kwargs

        def __rshift__(self, other: Any) -> Any:
            return other

    # Patch DAG to track tasks automatically
    _dag_instance: list[_DummyDAG] = []

    class _TrackingDAG(_DummyDAG):
        def __enter__(self) -> _TrackingDAG:
            _dag_instance.clear()
            _dag_instance.append(self)
            return self

    class _TrackingOperator(_DummyOperator):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            if _dag_instance:
                _dag_instance[0].tasks.append(self)

    airflow_module = types.ModuleType("airflow")
    airflow_module.DAG = _TrackingDAG  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "airflow", airflow_module)

    class _AirflowFailException(Exception):
        pass

    airflow_exceptions = types.ModuleType("airflow.exceptions")
    airflow_exceptions.AirflowFailException = _AirflowFailException  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "airflow.exceptions", airflow_exceptions)

    airflow_models = types.ModuleType("airflow.models")
    monkeypatch.setitem(sys.modules, "airflow.models", airflow_models)

    airflow_models_param = types.ModuleType("airflow.models.param")

    class _DummyParam:
        def __init__(self, default: Any, **kwargs: Any) -> None:
            self.default = default
            self.kwargs = kwargs

    airflow_models_param.Param = _DummyParam  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "airflow.models.param", airflow_models_param)

    airflow_operators = types.ModuleType("airflow.operators")
    monkeypatch.setitem(sys.modules, "airflow.operators", airflow_operators)

    airflow_operators_python = types.ModuleType("airflow.operators.python")
    airflow_operators_python.PythonOperator = _TrackingOperator  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules, "airflow.operators.python", airflow_operators_python
    )

    candles_bootstrap = types.ModuleType("src.candles.bootstrap")
    candles_bootstrap.create_candles_airflow_callbacks = lambda: SimpleNamespace(  # type: ignore[attr-defined]
        on_failure_callback="failure_cb",
        on_success_callback="success_cb",
        on_retry_callback="retry_cb",
    )
    monkeypatch.setitem(sys.modules, "src.candles.bootstrap", candles_bootstrap)

    module_path = Path(
        str(
            Path(__file__).parents[2]
            / "ops/airflow/dags/okx_swap_ohlcv_bootstrap_v1.py"
        )
    )
    module_name = "tests.db._okx_swap_ohlcv_bootstrap_v1_dag"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture
def bootstrap_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    return _load_bootstrap_dag_module(monkeypatch)


@pytest.mark.smoke
def test_bootstrap_dag_loads_without_error(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """DAG file must be importable and expose the expected task IDs."""
    dag = getattr(bootstrap_dag_module, "dag", None)
    assert dag is not None, "module must expose a 'dag' variable"

    task_ids = {t.task_id for t in dag.tasks}
    expected = {
        "validate_conf",
        "preflight_instrument_check",
        "init_bootstrap_state",
        "coverage_report",
        "bootstrap_symbol_tf",
        "validate_bootstrap_xcom",
        "enqueue_indicator_recalc",
        "publish_bootstrap_report",
        "publish_bootstrap_ops",
        "refresh_eligibility",
    }
    assert expected.issubset(task_ids), f"missing tasks: {expected - task_ids}"


@pytest.mark.smoke
def test_bootstrap_dag_schedule_is_none(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """Bootstrap DAG must have schedule=None (manual trigger only)."""
    dag = getattr(bootstrap_dag_module, "dag", None)
    assert dag is not None
    assert dag.schedule_interval is None, "bootstrap must be manual-trigger only"


# ---------------------------------------------------------------------------
# task_validate_conf — timeframe validation
# ---------------------------------------------------------------------------


def _make_context(conf: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal Airflow context stub for task_validate_conf."""
    dag_run = SimpleNamespace(conf=conf)
    return {"params": {}, "dag_run": dag_run}


def _call_validate_conf(
    module: types.ModuleType, conf: dict[str, Any]
) -> dict[str, Any]:
    """Call task_validate_conf with env setup stubbed out."""
    context = _make_context(conf)
    module.get_dag_env = lambda: {}
    module.setup_env = lambda env: None
    return module.task_validate_conf(**context)


@pytest.mark.unit
def test_validate_conf_accepts_valid_timeframes(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """Valid separate timeframe strings must pass without error."""
    result = _call_validate_conf(
        bootstrap_dag_module,
        {
            "symbols": ["BTC-USDT-SWAP"],
            "timeframes": ["1H", "4H"],
            "lookback_days": 200,
            "chunk_bars": 500,
            "dry_run": True,
        },
    )
    assert result["timeframes"] == ["1H", "4H"]


@pytest.mark.unit
def test_validate_conf_rejects_comma_in_single_string(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """Comma-joined TFs in one string ('1H, 4H') must raise AirflowFailException."""
    AirflowFailException = sys.modules["airflow.exceptions"].AirflowFailException
    with pytest.raises(AirflowFailException, match="1H, 4H"):
        _call_validate_conf(
            bootstrap_dag_module,
            {
                "symbols": ["BTC-USDT-SWAP"],
                "timeframes": ["1H, 4H"],
                "lookback_days": 200,
                "dry_run": True,
            },
        )


@pytest.mark.unit
def test_validate_conf_rejects_unknown_timeframe(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """Completely unrecognised TF string must raise AirflowFailException."""
    AirflowFailException = sys.modules["airflow.exceptions"].AirflowFailException
    with pytest.raises(AirflowFailException, match="bad_tf"):
        _call_validate_conf(
            bootstrap_dag_module,
            {
                "symbols": ["BTC-USDT-SWAP"],
                "timeframes": ["bad_tf"],
                "lookback_days": 200,
                "dry_run": True,
            },
        )


@pytest.mark.unit
def test_validate_conf_rejects_mixed_valid_and_invalid(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """A list with one good and one bad TF must still fail."""
    AirflowFailException = sys.modules["airflow.exceptions"].AirflowFailException
    with pytest.raises(AirflowFailException, match="bad_tf"):
        _call_validate_conf(
            bootstrap_dag_module,
            {
                "symbols": ["BTC-USDT-SWAP"],
                "timeframes": ["1H", "bad_tf"],
                "lookback_days": 200,
                "dry_run": True,
            },
        )


# ---------------------------------------------------------------------------
# init_bootstrap_state interface — unknown TF must not silently continue
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_init_bootstrap_state_raises_on_unknown_tf() -> None:
    """init_bootstrap_state must raise ValueError for unrecognised timeframes,
    not silently skip them and return empty pending list."""
    import asyncio

    from src.candles.interfaces.bootstrap import init_bootstrap_state

    class _FailIfCalled:
        async def get_listing_time_ts_ms(self, *, symbol: str) -> int | None:
            return None

        async def get_bootstrap_state(self, *, symbol: str, timeframe: str) -> None:
            return None

        async def count_candles(self, **_: Any) -> int:
            return 0

        async def upsert_bootstrap_state(self, **_: Any) -> None:
            pass

    import unittest.mock as mock

    with mock.patch(
        "src.candles.interfaces.bootstrap.BootstrapCandlesRepository",
        return_value=_FailIfCalled(),
    ):
        with pytest.raises(ValueError, match="1H, 4H"):
            asyncio.run(
                init_bootstrap_state(
                    symbols=["BTC-USDT-SWAP"],
                    timeframes=["1H, 4H"],
                    lookback_days=200,
                )
            )


# ---------------------------------------------------------------------------
# task_validate_conf — comma-string normalization
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_validate_conf_accepts_symbols_as_comma_string(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """'BTC-USDT-SWAP,ETH-USDT-SWAP' must be split into two symbols."""
    result = _call_validate_conf(
        bootstrap_dag_module,
        {
            "symbols": "BTC-USDT-SWAP,ETH-USDT-SWAP",
            "timeframes": ["1H"],
            "lookback_days": 200,
            "dry_run": True,
        },
    )
    assert result["symbols"] == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]


@pytest.mark.unit
def test_validate_conf_accepts_timeframes_as_comma_string(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """'1H,4H' must be split and treated the same as ['1H', '4H']."""
    result = _call_validate_conf(
        bootstrap_dag_module,
        {
            "symbols": ["BTC-USDT-SWAP"],
            "timeframes": "1H,4H",
            "lookback_days": 200,
            "dry_run": True,
        },
    )
    assert result["timeframes"] == ["1H", "4H"]


@pytest.mark.unit
def test_validate_conf_comma_string_with_spaces(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """'1H, 4H' (with space) must be split and stripped correctly."""
    result = _call_validate_conf(
        bootstrap_dag_module,
        {
            "symbols": ["BTC-USDT-SWAP"],
            "timeframes": "1H, 4H",
            "lookback_days": 200,
            "dry_run": True,
        },
    )
    assert result["timeframes"] == ["1H", "4H"]


@pytest.mark.unit
def test_validate_conf_invalid_tf_in_comma_string_fails(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """'1H,bad_tf' as a comma-string must still fail fast on the bad entry."""
    AirflowFailException = sys.modules["airflow.exceptions"].AirflowFailException
    with pytest.raises(AirflowFailException, match="bad_tf"):
        _call_validate_conf(
            bootstrap_dag_module,
            {
                "symbols": ["BTC-USDT-SWAP"],
                "timeframes": "1H,bad_tf",
                "lookback_days": 200,
                "dry_run": True,
            },
        )


@pytest.mark.unit
def test_validate_conf_single_symbol_string_no_comma(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """A single symbol passed as a plain string (no comma) must become a one-element list."""
    result = _call_validate_conf(
        bootstrap_dag_module,
        {
            "symbols": "BTC-USDT-SWAP",
            "timeframes": ["1H"],
            "lookback_days": 200,
            "dry_run": True,
        },
    )
    assert result["symbols"] == ["BTC-USDT-SWAP"]


@pytest.mark.unit
def test_validate_conf_skip_recalc_default_false(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """skip_recalc must default to False when not supplied."""
    result = _call_validate_conf(
        bootstrap_dag_module,
        {"symbols": ["BTC-USDT-SWAP"], "timeframes": ["1H"], "dry_run": True},
    )
    assert result["skip_recalc"] is False


@pytest.mark.unit
def test_validate_conf_skip_recalc_true(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """skip_recalc=True in conf must be passed through as True."""
    result = _call_validate_conf(
        bootstrap_dag_module,
        {
            "symbols": ["BTC-USDT-SWAP"],
            "timeframes": ["1H"],
            "skip_recalc": True,
            "dry_run": True,
        },
    )
    assert result["skip_recalc"] is True


@pytest.mark.unit
def test_enqueue_indicator_recalc_skips_when_skip_recalc_true(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """When skip_recalc=True, task_enqueue_indicator_recalc must return without enqueuing."""
    import unittest.mock as mock

    validated = {
        "lookback_days": 200,
        "symbols": ["BTC-USDT-SWAP"],
        "timeframes": ["1H"],
        "skip_recalc": True,
        "dry_run": True,
    }

    ti_stub = SimpleNamespace(xcom_pull=lambda task_ids, key: [])
    context = {
        "ti": ti_stub,
        "params": {},
        "dag_run": SimpleNamespace(conf={}),
    }

    bootstrap_dag_module.get_dag_env = lambda: {}
    bootstrap_dag_module.setup_env = lambda env: None
    bootstrap_dag_module._get_validated_conf = lambda ctx: validated

    with mock.patch(
        "src.candles.interfaces.repair.enqueue_indicator_recalc"
    ) as mock_enqueue:
        bootstrap_dag_module.task_enqueue_indicator_recalc(**context)
        mock_enqueue.assert_not_called()


@pytest.mark.unit
def test_validate_conf_accepts_1d_timeframe(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """1D must be accepted by validate_conf (it is in TF_TO_MS and StorageCalendar supports it)."""
    result = _call_validate_conf(
        bootstrap_dag_module,
        {
            "symbols": ["BTC-USDT-SWAP"],
            "timeframes": ["1H", "4H", "1D"],
            "lookback_days": 200,
            "dry_run": True,
        },
    )
    assert "1D" in result["timeframes"]


@pytest.mark.unit
def test_validate_conf_accepts_1w_1m_timeframes(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """1W and 1M must be accepted by validate_conf."""
    result = _call_validate_conf(
        bootstrap_dag_module,
        {
            "symbols": ["BTC-USDT-SWAP"],
            "timeframes": ["1W", "1M"],
            "lookback_days": 730,
            "dry_run": True,
        },
    )
    assert result["timeframes"] == ["1W", "1M"]


@pytest.mark.unit
def test_validate_conf_defaults_to_all_research_timeframes(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """No timeframes in conf must select the full research TF set."""
    result = _call_validate_conf(
        bootstrap_dag_module,
        {"symbols": ["BTC-USDT-SWAP"], "lookback_days": 730, "dry_run": True},
    )
    assert result["timeframes"] == ["1H", "4H", "1D", "1W", "1M"]


@pytest.mark.unit
def test_bootstrap_dag_has_four_hour_execution_timeout(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """Bootstrap task defaults must cap hung manual runs."""
    dag = getattr(bootstrap_dag_module, "dag", None)
    assert dag is not None
    assert dag.kwargs["default_args"]["execution_timeout"].total_seconds() == 4 * 3600


@pytest.mark.unit
def test_enqueue_indicator_recalc_skips_1m_timeframe(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """1M is informational-only OHLCV and must not enqueue standard features."""
    import unittest.mock as mock

    validated = {
        "lookback_days": 730,
        "symbols": ["BTC-USDT-SWAP"],
        "timeframes": ["1M", "1H"],
        "skip_recalc": False,
        "dry_run": False,
    }
    results = [
        {"symbol": "BTC-USDT-SWAP", "timeframe": "1M", "status": "completed"},
        {"symbol": "BTC-USDT-SWAP", "timeframe": "1H", "status": "completed"},
    ]
    ti_stub = SimpleNamespace(
        xcom_pull=lambda task_ids, key: (
            results if task_ids == "validate_bootstrap_xcom" else None
        )
    )
    context = {"ti": ti_stub, "params": {}, "dag_run": SimpleNamespace(conf={})}

    bootstrap_dag_module.get_dag_env = lambda: {}
    bootstrap_dag_module.setup_env = lambda env: None
    bootstrap_dag_module._get_validated_conf = lambda ctx: validated

    with mock.patch(
        "src.candles.interfaces.repair.enqueue_indicator_recalc"
    ) as mock_enqueue:
        bootstrap_dag_module.task_enqueue_indicator_recalc(**context)

    called_timeframes = [
        call.kwargs["timeframe"] for call in mock_enqueue.call_args_list
    ]
    assert called_timeframes == ["1H"]
