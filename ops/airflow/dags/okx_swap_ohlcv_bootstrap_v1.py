"""DAG: okx_swap_ohlcv_bootstrap_v1.

Manual trigger only. Trigger via Airflow UI with conf::

    {
        "lookback_days": 730,
        "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
        "timeframes": ["1H", "4H"],
        "chunk_bars": 500,
        "circuit_break_after": 3,
        "dry_run": false
    }

Ops prerequisite — create bootstrap_pool before first run::

    airflow pools set bootstrap_pool 2 "Historical OHLCV bootstrap"
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from _common import (  # type: ignore[import-not-found]
    coerce_int as _coerce_int,
    get_dag_env as _get_common_dag_env,
    get_or_create_event_loop,
    payload_to_dict as _payload_to_dict,
    setup_env as _setup_common_env,
)
from airflow import DAG
from airflow.exceptions import AirflowFailException
from airflow.models.param import Param
from airflow.operators.python import PythonOperator

from src.candles.application.bootstrap.dto import BootstrapCommand, BootstrapResult
from src.candles.application.bootstrap.summary import merge_bootstrap_results
from src.candles.bootstrap import create_candles_airflow_callbacks
from src.candles.instruments_service import (
    load_symbols_from_file,
    resolve_repo_instruments_file,
)
from src.candles.interfaces import (
    bootstrap as bootstrap_interface,
    repair as repair_interface,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import asyncio

SUPPORTED_TIMEFRAMES = ("1H", "4H")
DEFAULT_LOOKBACK_DAYS = 730
DEFAULT_CHUNK_BARS = 500
DEFAULT_CIRCUIT_BREAK_AFTER = 3

try:
    _callbacks = create_candles_airflow_callbacks()
    DAG_FAILURE_CALLBACK = _callbacks.on_failure_callback
    DAG_SUCCESS_CALLBACK = _callbacks.on_success_callback
    DAG_RETRY_CALLBACK = _callbacks.on_retry_callback
except Exception:  # pragma: no cover
    DAG_FAILURE_CALLBACK = None
    DAG_SUCCESS_CALLBACK = None
    DAG_RETRY_CALLBACK = None


def _get_loop() -> asyncio.AbstractEventLoop:
    return cast("asyncio.AbstractEventLoop", get_or_create_event_loop())


def get_dag_env() -> dict[str, str]:
    return cast("dict[str, str]", _get_common_dag_env(job_name_default="swap_bootstrap_v1"))


def setup_env(env: dict[str, str]) -> None:
    _setup_common_env(env)


def _load_curated_swap_symbols() -> list[str]:
    return load_symbols_from_file(resolve_repo_instruments_file(), logger=logger)


def _get_run_conf(context: dict[str, Any]) -> dict[str, Any]:
    conf = dict(context.get("params") or {})
    dag_run = context.get("dag_run")
    if dag_run and dag_run.conf:
        conf.update(dict(dag_run.conf))
    return conf


def _get_validated_conf(context: dict[str, Any]) -> dict[str, Any]:
    ti = context.get("ti")
    if ti is not None:
        payload = ti.xcom_pull(task_ids="validate_conf", key="return_value")
        if isinstance(payload, dict):
            return payload
    return _get_run_conf(context)


# ---------------------------------------------------------------------------
# Task callables
# ---------------------------------------------------------------------------


def task_validate_conf(**context: Any) -> dict[str, Any]:
    env = get_dag_env()
    setup_env(env)

    conf = _get_run_conf(context)
    lookback_days = _coerce_int(
        conf.get("lookback_days", DEFAULT_LOOKBACK_DAYS),
        field_name="lookback_days",
    )
    if lookback_days <= 0:
        raise AirflowFailException("lookback_days must be positive")

    symbols_raw = conf.get("symbols")
    if symbols_raw:
        symbols = [str(s) for s in symbols_raw]
    else:
        symbols = _load_curated_swap_symbols()
    if not symbols:
        raise AirflowFailException("symbol list is empty")

    timeframes_raw = conf.get("timeframes")
    timeframes = [str(tf) for tf in timeframes_raw] if timeframes_raw else list(SUPPORTED_TIMEFRAMES)

    chunk_bars = _coerce_int(conf.get("chunk_bars", DEFAULT_CHUNK_BARS), field_name="chunk_bars")
    circuit_break_after = _coerce_int(
        conf.get("circuit_break_after", DEFAULT_CIRCUIT_BREAK_AFTER),
        field_name="circuit_break_after",
    )
    dry_run = bool(conf.get("dry_run", False))

    validated = {
        "lookback_days": lookback_days,
        "symbols": symbols,
        "timeframes": timeframes,
        "chunk_bars": chunk_bars,
        "circuit_break_after": circuit_break_after,
        "dry_run": dry_run,
    }
    logger.info(
        "bootstrap conf validated: %d symbols, %s TFs, lookback=%d days",
        len(symbols),
        timeframes,
        lookback_days,
    )
    return validated


def task_preflight_instrument_check(**context: Any) -> None:
    validated = _get_validated_conf(context)
    symbols: list[str] = validated["symbols"]
    logger.info("preflight: %d symbols queued for bootstrap", len(symbols))


def task_init_bootstrap_state(**context: Any) -> dict[str, Any]:
    env = get_dag_env()
    setup_env(env)
    validated = _get_validated_conf(context)
    result = _get_loop().run_until_complete(
        bootstrap_interface.init_bootstrap_state(
            symbols=validated["symbols"],
            timeframes=validated["timeframes"],
            lookback_days=validated["lookback_days"],
            chunk_bars=validated["chunk_bars"],
        )
    )
    logger.info(
        "init_bootstrap_state: %d pending, %d skipped",
        len(result["pending"]),
        len(result["skipped"]),
    )
    return result


def task_coverage_report(**context: Any) -> list[dict[str, Any]]:
    env = get_dag_env()
    setup_env(env)
    validated = _get_validated_conf(context)
    report = _get_loop().run_until_complete(
        bootstrap_interface.build_coverage_report(
            symbols=validated["symbols"],
            timeframes=validated["timeframes"],
        )
    )
    for row in report:
        logger.info(
            "coverage: %s/%s status=%s coverage_pct=%s missing=%s",
            row["symbol"],
            row["timeframe"],
            row["status"],
            row.get("coverage_pct"),
            row.get("missing_bars"),
        )
    if validated.get("dry_run"):
        logger.info("dry_run=True — stopping after coverage report")
    return report


def task_bootstrap_symbol_tf(**context: Any) -> dict[str, Any]:
    """Bootstrap a single (symbol, timeframe) pair — dispatched via map_index."""
    env = get_dag_env()
    setup_env(env)
    ti = context["ti"]
    map_index = getattr(ti, "map_index", 0)

    validated = _get_validated_conf(context)
    init_result = ti.xcom_pull(task_ids="init_bootstrap_state", key="return_value") or {}
    pending: list[str] = init_result.get("pending", [])

    if map_index >= len(pending):
        return {"status": "skipped", "reason": "no pending item at map_index"}

    pair = pending[map_index]
    symbol, timeframe = pair.split("/", 1)

    command = BootstrapCommand(
        symbol=symbol,
        timeframe=timeframe,
        lookback_days=validated["lookback_days"],
        chunk_bars=validated["chunk_bars"],
        circuit_break_after=validated["circuit_break_after"],
        dry_run=bool(validated.get("dry_run", False)),
    )
    result = _get_loop().run_until_complete(bootstrap_interface.run_bootstrap(command))
    logger.info(
        "bootstrap %s/%s → status=%s missing=%d rows_written=%d",
        symbol,
        timeframe,
        result.status,
        result.missing_bars,
        result.rows_written,
    )
    return result.to_dict()


def task_validate_bootstrap_xcom(**context: Any) -> list[dict[str, Any]]:
    ti = context["ti"]
    raw = ti.xcom_pull(task_ids="bootstrap_symbol_tf", key="return_value") or []
    if isinstance(raw, dict):
        raw = [raw]
    return [_payload_to_dict(item) for item in raw if item]


def task_enqueue_indicator_recalc(**context: Any) -> None:
    env = get_dag_env()
    setup_env(env)
    ti = context["ti"]
    results = ti.xcom_pull(task_ids="validate_bootstrap_xcom", key="return_value") or []
    validated = _get_validated_conf(context)

    completed_symbols: list[str] = [
        str(r.get("symbol", ""))
        for r in results
        if isinstance(r, dict) and r.get("status") == "completed"
    ]

    if completed_symbols:
        _get_loop().run_until_complete(
            repair_interface.enqueue_indicator_recalc(
                symbols=list(set(completed_symbols)),
                timeframes=validated["timeframes"],
            )
        )
        logger.info("enqueued indicator recalc for %d symbols", len(set(completed_symbols)))


def task_publish_bootstrap_report(**context: Any) -> dict[str, Any]:
    ti = context["ti"]
    results_raw = ti.xcom_pull(task_ids="validate_bootstrap_xcom", key="return_value") or []

    results: list[BootstrapResult] = []
    for r in results_raw:
        d = _payload_to_dict(r)
        try:
            results.append(
                BootstrapResult(
                    symbol=str(d["symbol"]),
                    timeframe=str(d["timeframe"]),
                    status=str(d["status"]),
                    chunks_fetched=int(d.get("chunks_fetched", 0)),
                    rows_written=int(d.get("rows_written", 0)),
                    expected_bars=int(d.get("expected_bars", 0)),
                    actual_bars=int(d.get("actual_bars", 0)),
                    missing_bars=int(d.get("missing_bars", 0)),
                    coverage_pct=float(d.get("coverage_pct", 0.0)),
                    elapsed_seconds=float(d.get("elapsed_seconds", 0.0)),
                    error=d.get("error"),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("skipping malformed result in report: %s", exc)

    summary = merge_bootstrap_results(results)
    logger.info("bootstrap summary: %s", summary.to_dict())
    return summary.to_dict()


def task_publish_bootstrap_ops(**context: Any) -> None:
    ti = context["ti"]
    summary_dict = ti.xcom_pull(task_ids="publish_bootstrap_report", key="return_value") or {}
    logger.info(
        "bootstrap ops metrics: coverage_pct=%.2f missing_bars=%s",
        summary_dict.get("overall_coverage_pct", 0),
        summary_dict.get("total_missing_bars", 0),
    )


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

with DAG(
    dag_id="okx_swap_ohlcv_bootstrap_v1",
    description="Manual historical OHLCV backfill for OKX SWAP instruments",
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 0,
        "retry_delay": timedelta(minutes=5),
    },
    on_failure_callback=DAG_FAILURE_CALLBACK,
    on_success_callback=DAG_SUCCESS_CALLBACK,
    params={
        "lookback_days": Param(730, type="integer", description="Days back to bootstrap"),
        "symbols": Param(None, type=["null", "array"], description="Symbols (null=all)"),
        "timeframes": Param(None, type=["null", "array"], description="Timeframes (null=1H,4H)"),
        "chunk_bars": Param(500, type="integer"),
        "circuit_break_after": Param(3, type="integer"),
        "dry_run": Param(False, type="boolean"),
    },
    tags=["bootstrap", "candles", "swap"],
) as dag:
    t_validate_conf = PythonOperator(
        task_id="validate_conf",
        python_callable=task_validate_conf,
    )
    t_preflight = PythonOperator(
        task_id="preflight_instrument_check",
        python_callable=task_preflight_instrument_check,
    )
    t_init_state = PythonOperator(
        task_id="init_bootstrap_state",
        python_callable=task_init_bootstrap_state,
    )
    t_coverage_report = PythonOperator(
        task_id="coverage_report",
        python_callable=task_coverage_report,
    )
    t_bootstrap = PythonOperator(
        task_id="bootstrap_symbol_tf",
        python_callable=task_bootstrap_symbol_tf,
        pool="bootstrap_pool",
        pool_slots=1,
    )
    t_validate_xcom = PythonOperator(
        task_id="validate_bootstrap_xcom",
        python_callable=task_validate_bootstrap_xcom,
    )
    t_recalc = PythonOperator(
        task_id="enqueue_indicator_recalc",
        python_callable=task_enqueue_indicator_recalc,
    )
    t_report = PythonOperator(
        task_id="publish_bootstrap_report",
        python_callable=task_publish_bootstrap_report,
    )
    t_ops = PythonOperator(
        task_id="publish_bootstrap_ops",
        python_callable=task_publish_bootstrap_ops,
    )

    (
        t_validate_conf
        >> t_preflight
        >> t_init_state
        >> t_coverage_report
        >> t_bootstrap
        >> t_validate_xcom
        >> t_recalc
        >> t_report
        >> t_ops
    )
