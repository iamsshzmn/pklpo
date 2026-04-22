"""DAG: okx_swap_repair_v1.

Manual repair DAG with a trigger-only external contract.

All runtime settings now live in code. A manual Airflow run only selects a
named trigger preset, and the DAG expands that preset into the curated swap
symbol universe from ``src/candles/instruments_list.json``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from _common import (
    coerce_float as _coerce_float,
    coerce_int as _coerce_int,
    get_dag_env as _get_common_dag_env,
    get_or_create_event_loop,
    normalize_swap_repair_summary_payloads,
    payload_to_dict as _payload_to_dict,
    setup_env as _setup_common_env,
    validate_swap_repair_xcom_payload,
)
from airflow import DAG
from airflow.exceptions import AirflowFailException
from airflow.models.param import Param
from airflow.operators.python import PythonOperator

from src.candles.bootstrap import create_candles_airflow_callbacks
from src.candles.domain.repair import RepairExecutionMode, RepairStrategy
from src.candles.instruments_service import (
    ensure_symbols_registered,
    load_symbols_from_file,
    resolve_repo_instruments_file,
)
from src.candles.interfaces import repair as repair_interface
from src.candles.interfaces.repair_audit import write_swap_repair_audit
from src.candles.observability.prometheus import push_swap_repair_metrics
from src.market_meta.application.validate_instrument import validate_instrument_exists
from src.market_meta.domain.exceptions import InstrumentNotFoundError
from src.market_meta.infrastructure.sql_adapter import InstrumentSqlRepository

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import asyncio

SUPPORTED_TIMEFRAMES = ("1m", "1H", "4H", "1D", "1W", "1M")
DEFAULT_TRIGGER = "repair-all-swaps"
REPAIR_TRIGGER_PRESETS: dict[str, dict[str, Any]] = {
    DEFAULT_TRIGGER: {
        "timeframes": list(SUPPORTED_TIMEFRAMES),
        "mode": RepairExecutionMode.APPLY.value,
        "repair_strategy": RepairStrategy.GAP_REPAIR.value,
        "padding_bars": 0,
        "max_gap_tasks_per_run": 50,
        "max_requested_bars_per_run": 10_000,
        "max_range_days": 7,
        "max_fail_ratio": 1.0,
        "auto_apply_anchor_strategy": "listing-date",
        "anchor_ts_ms": None,
        "auto_apply_window": True,
        "start_ts_ms": None,
        "end_ts_ms": None,
        "critical_timeframes": ["1m", "1H"],
        "no_progress_threshold": 3,
    }
}

try:
    _callbacks = create_candles_airflow_callbacks()
    DAG_FAILURE_CALLBACK = _callbacks.on_failure_callback
    DAG_SUCCESS_CALLBACK = _callbacks.on_success_callback
    DAG_RETRY_CALLBACK = _callbacks.on_retry_callback
except Exception:  # pragma: no cover - defensive Airflow import path
    DAG_FAILURE_CALLBACK = None
    DAG_SUCCESS_CALLBACK = None
    DAG_RETRY_CALLBACK = None


def _get_run_conf(context: dict[str, Any]) -> dict[str, Any]:
    conf = dict(context.get("params") or {})
    dag_run = context.get("dag_run")
    if dag_run and dag_run.conf:
        conf.update(dict(dag_run.conf))
    return conf


def _build_log_context(context: dict[str, Any]) -> str:
    dag_run = context.get("dag_run")
    dag_run_id = getattr(dag_run, "run_id", "unknown")
    logical_date = context.get("logical_date", "unknown")
    ti = context.get("ti")
    try_number = getattr(ti, "try_number", "unknown")
    return (
        f"dag_run_id={dag_run_id} "
        f"logical_date={logical_date} "
        f"try_number={try_number}"
    )


def _get_loop() -> asyncio.AbstractEventLoop:
    return get_or_create_event_loop()


def get_dag_env() -> dict[str, str]:
    return _get_common_dag_env(job_name_default="swap_repair_v1")


def setup_env(env: dict[str, str]) -> None:
    _setup_common_env(env)


def _load_curated_swap_symbols() -> list[str]:
    return load_symbols_from_file(resolve_repo_instruments_file(), logger=logger)


def _build_validated_conf_from_trigger(trigger: str) -> dict[str, Any]:
    preset = REPAIR_TRIGGER_PRESETS.get(trigger)
    if preset is None:
        supported = ", ".join(sorted(REPAIR_TRIGGER_PRESETS))
        raise ValueError(f"unsupported trigger {trigger!r}; expected one of: {supported}")

    symbols = _load_curated_swap_symbols()
    if not symbols:
        raise ValueError("curated symbol list is empty; cannot run swap repair trigger")

    return {
        "trigger": trigger,
        "symbols": symbols,
        **preset,
    }


def _get_validated_conf(context: dict[str, Any]) -> dict[str, Any]:
    ti = context.get("ti")
    if ti is not None:
        payload = ti.xcom_pull(task_ids="validate_swap_repair_conf", key="return_value")
        if isinstance(payload, dict):
            return payload

    conf = _get_run_conf(context)
    trigger = str(conf.get("trigger") or DEFAULT_TRIGGER).strip()
    return _build_validated_conf_from_trigger(trigger)


TERMINAL_REPAIR_ERROR_PREFIXES: tuple[str, ...] = (
    "apply blocked by guardrails",
    "no progress on critical TF",
)


def _is_terminal_repair_error(exc: BaseException) -> bool:
    if not isinstance(exc, ValueError):
        return False
    message = str(exc)
    return any(message.startswith(prefix) for prefix in TERMINAL_REPAIR_ERROR_PREFIXES)


def _extract_no_progress_policy(
    validated: dict[str, Any],
) -> tuple[list[str] | None, int | None]:
    critical_raw = validated.get("critical_timeframes")
    critical = None if critical_raw is None else [str(tf) for tf in critical_raw]
    threshold_raw = validated.get("no_progress_threshold")
    threshold = (
        None
        if threshold_raw is None
        else _coerce_int(
            threshold_raw,
            field_name="validated.no_progress_threshold",
        )
    )
    return critical, threshold


def _run_swap_repair_once(
    *,
    validated: dict[str, Any],
    timeframe: str,
    start_ts_ms: int,
    end_ts_ms: int,
) -> dict[str, Any]:
    critical_timeframes, no_progress_threshold = _extract_no_progress_policy(validated)
    return _get_loop().run_until_complete(
        repair_interface.run_swap_repair(
            symbol=str(validated["symbol"]),
            timeframe=str(timeframe),
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
            mode=RepairExecutionMode(str(validated["mode"])),
            strategy=RepairStrategy(str(validated["repair_strategy"])),
            max_gap_tasks_per_run=_coerce_int(
                validated["max_gap_tasks_per_run"],
                field_name="validated.max_gap_tasks_per_run",
            ),
            max_requested_bars_per_run=_coerce_int(
                validated["max_requested_bars_per_run"],
                field_name="validated.max_requested_bars_per_run",
            ),
            max_range_days=_coerce_int(
                validated["max_range_days"],
                field_name="validated.max_range_days",
            ),
            max_fail_ratio=_coerce_float(
                validated["max_fail_ratio"],
                field_name="validated.max_fail_ratio",
            ),
            padding_bars=_coerce_int(
                validated["padding_bars"],
                field_name="validated.padding_bars",
            ),
            critical_timeframes=critical_timeframes,
            no_progress_threshold=no_progress_threshold,
        )
    )


def _run_auto_apply_for_timeframe(
    *,
    validated: dict[str, Any],
    timeframe: str,
) -> dict[str, Any]:
    critical_timeframes, no_progress_threshold = _extract_no_progress_policy(validated)
    return _get_loop().run_until_complete(
        repair_interface.run_swap_repair_auto_apply(
            symbol=str(validated["symbol"]),
            timeframe=timeframe,
            strategy=RepairStrategy(str(validated["repair_strategy"])),
            max_gap_tasks_per_run=_coerce_int(
                validated["max_gap_tasks_per_run"],
                field_name="validated.max_gap_tasks_per_run",
            ),
            max_requested_bars_per_run=_coerce_int(
                validated["max_requested_bars_per_run"],
                field_name="validated.max_requested_bars_per_run",
            ),
            max_range_days=_coerce_int(
                validated["max_range_days"],
                field_name="validated.max_range_days",
            ),
            max_fail_ratio=_coerce_float(
                validated["max_fail_ratio"],
                field_name="validated.max_fail_ratio",
            ),
            padding_bars=_coerce_int(
                validated["padding_bars"],
                field_name="validated.padding_bars",
            ),
            auto_apply_max_iterations=100,
            anchor_ts_ms=(
                _coerce_int(
                    validated["anchor_ts_ms"],
                    field_name="validated.anchor_ts_ms",
                )
                if validated.get("anchor_ts_ms") is not None
                else None
            ),
            auto_apply_anchor_strategy=str(
                validated.get("auto_apply_anchor_strategy", "first-coverage")
            ),
            critical_timeframes=critical_timeframes,
            no_progress_threshold=no_progress_threshold,
        )
    )


def ensure_instruments_loaded_task(**context) -> None:
    validated = _get_validated_conf(context)
    log_ctx = _build_log_context(context)
    env = get_dag_env()
    setup_env(env)

    symbols = [str(s).strip() for s in validated.get("symbols", []) if str(s).strip()]
    if not symbols:
        raise ValueError("ensure_instruments_loaded: validated config contains no symbols")

    logger.info(
        "ensure_instruments_loaded start %s symbols=%d",
        log_ctx,
        len(symbols),
    )
    repository = InstrumentSqlRepository()
    _get_loop().run_until_complete(
        ensure_symbols_registered(symbols, repository=repository, logger=logger)
    )
    logger.info("ensure_instruments_loaded pass %s", log_ctx)


def preflight_instrument_check_task(**context) -> None:
    validated = _get_validated_conf(context)
    log_ctx = _build_log_context(context)
    env = get_dag_env()
    setup_env(env)

    symbols = [str(symbol).strip() for symbol in validated.get("symbols", []) if str(symbol).strip()]
    if not symbols:
        raise ValueError("preflight: validated config must contain at least one symbol")
    logger.info(
        "preflight_instrument_check start %s trigger=%s symbols=%d",
        log_ctx,
        validated.get("trigger"),
        len(symbols),
    )

    repository = InstrumentSqlRepository()
    for symbol in symbols:
        try:
            _get_loop().run_until_complete(
                validate_instrument_exists(symbol, repository=repository)
            )
        except InstrumentNotFoundError:
            raise
    logger.info("preflight_instrument_check pass %s symbols=%d", log_ctx, len(symbols))


def validate_swap_repair_conf_task(**context) -> dict[str, Any]:
    conf = _get_run_conf(context)
    log_ctx = _build_log_context(context)
    logger.info("validate_swap_repair_conf start %s raw_conf=%s", log_ctx, conf)
    trigger = str(conf.get("trigger") or DEFAULT_TRIGGER).strip()
    validated = _build_validated_conf_from_trigger(trigger)
    logger.info(
        "validate_swap_repair_conf finish %s trigger=%s symbols=%d timeframes=%s mode=%s strategy=%s",
        log_ctx,
        validated["trigger"],
        len(validated["symbols"]),
        validated["timeframes"],
        validated["mode"],
        validated["repair_strategy"],
    )
    return validated


def swap_repair_task(**context) -> list[dict[str, Any]]:
    log_ctx = _build_log_context(context)
    logger.info("swap_repair start %s", log_ctx)
    env = get_dag_env()
    setup_env(env)

    ti = context["ti"]
    validated = ti.xcom_pull(task_ids="validate_swap_repair_conf", key="return_value")
    if not isinstance(validated, dict):
        raise ValueError("swap_repair validated config must be a dict")
    timeframes = [str(timeframe) for timeframe in validated.get("timeframes", [])]
    symbols = [str(symbol) for symbol in validated.get("symbols", [])]
    if not timeframes:
        raise ValueError("swap_repair validated config must contain non-empty timeframes")
    if not symbols:
        raise ValueError("swap_repair validated config must contain non-empty symbols")

    summaries = []
    for symbol in symbols:
        per_symbol_validated = dict(validated)
        per_symbol_validated["symbol"] = symbol
        for timeframe in timeframes:
            try:
                if bool(validated.get("auto_apply_window", False)):
                    summary = _run_auto_apply_for_timeframe(
                        validated=per_symbol_validated,
                        timeframe=str(timeframe),
                    )
                else:
                    summary = _run_swap_repair_once(
                        validated=per_symbol_validated,
                        timeframe=str(timeframe),
                        start_ts_ms=_coerce_int(
                            validated.get("start_ts_ms"),
                            field_name="validated.start_ts_ms",
                        ),
                        end_ts_ms=_coerce_int(
                            validated.get("end_ts_ms"),
                            field_name="validated.end_ts_ms",
                        ),
                    )
            except ValueError as exc:
                if _is_terminal_repair_error(exc):
                    logger.error(
                        "swap_repair terminal failure %s symbol=%s timeframe=%s reason=%s",
                        log_ctx,
                        symbol,
                        timeframe,
                        exc,
                    )
                    raise AirflowFailException(str(exc)) from exc
                raise
            logger.info(
                "swap_repair finish %s symbol=%s timeframe=%s summary=%s",
                log_ctx,
                symbol,
                timeframe,
                summary,
            )
            summaries.append(summary)
    logger.info("swap_repair completed %s summaries=%d", log_ctx, len(summaries))
    return summaries


def swap_repair_preview_task(**context) -> list[dict[str, Any]]:
    log_ctx = _build_log_context(context)
    logger.info("swap_repair_preview start %s", log_ctx)
    env = get_dag_env()
    setup_env(env)

    ti = context["ti"]
    validated = ti.xcom_pull(task_ids="validate_swap_repair_conf", key="return_value")
    if not isinstance(validated, dict):
        raise ValueError("swap_repair preview validated config must be a dict")
    timeframes = [str(timeframe) for timeframe in validated.get("timeframes", [])]
    symbols = [str(symbol) for symbol in validated.get("symbols", [])]
    if not timeframes:
        raise ValueError("swap_repair preview validated config must contain non-empty timeframes")
    if not symbols:
        raise ValueError("swap_repair preview validated config must contain non-empty symbols")

    previews: list[dict[str, Any]] = []
    for symbol in symbols:
        for timeframe in timeframes:
            preview = _get_loop().run_until_complete(
                repair_interface.plan_swap_repair(
                    symbol=symbol,
                    timeframe=str(timeframe),
                    start_ts_ms=validated.get("start_ts_ms"),
                    end_ts_ms=validated.get("end_ts_ms"),
                    mode=RepairExecutionMode(str(validated["mode"])),
                    strategy=RepairStrategy(str(validated["repair_strategy"])),
                    auto_apply_window=bool(validated.get("auto_apply_window", False)),
                    max_gap_tasks_per_run=_coerce_int(
                        validated["max_gap_tasks_per_run"],
                        field_name="validated.max_gap_tasks_per_run",
                    ),
                    max_requested_bars_per_run=_coerce_int(
                        validated["max_requested_bars_per_run"],
                        field_name="validated.max_requested_bars_per_run",
                    ),
                    max_range_days=_coerce_int(
                        validated["max_range_days"],
                        field_name="validated.max_range_days",
                    ),
                    max_fail_ratio=_coerce_float(
                        validated["max_fail_ratio"],
                        field_name="validated.max_fail_ratio",
                    ),
                    padding_bars=_coerce_int(
                        validated["padding_bars"],
                        field_name="validated.padding_bars",
                    ),
                    anchor_ts_ms=(
                        _coerce_int(
                            validated["anchor_ts_ms"],
                            field_name="validated.anchor_ts_ms",
                        )
                        if validated.get("anchor_ts_ms") is not None
                        else None
                    ),
                    auto_apply_anchor_strategy=str(validated["auto_apply_anchor_strategy"]),
                )
            )
            logger.info(
                "swap_repair_preview finish %s symbol=%s timeframe=%s preview=%s",
                log_ctx,
                symbol,
                timeframe,
                preview,
            )
            previews.append(preview)

    logger.info("swap_repair_preview completed %s previews=%d", log_ctx, len(previews))
    return previews


def validate_swap_repair_xcom_task(**context) -> list[dict[str, Any]]:
    ti = context["ti"]
    payload = ti.xcom_pull(task_ids="swap_repair", key="return_value")
    log_ctx = _build_log_context(context)
    payloads = payload if isinstance(payload, list) else [payload]

    if not payloads:
        raise ValueError("swap_repair XCom must contain at least one timeframe result")

    normalized_payloads: list[dict[str, Any]] = []
    for item in payloads:
        try:
            normalized = _payload_to_dict(item)
        except TypeError as exc:
            raise ValueError(
                f"swap_repair XCom list entries must be dict-like, got {type(item).__name__}"
            ) from exc
        try:
            normalized = validate_swap_repair_xcom_payload(
                normalized,
                allowed_timeframes=SUPPORTED_TIMEFRAMES,
            )
        except ValueError as exc:
            raise ValueError(f"timeframe={normalized.get('timeframe')!r}: {exc}") from exc
        normalized_payloads.append(normalized)
        logger.info(
            "validate_swap_repair_xcom finish %s mode=%s strategy=%s symbol=%s timeframe=%s gap_tasks=%s requested_bars=%s remaining_gap_tasks=%s rows_written=%s",
            log_ctx,
            normalized["mode"],
            normalized["strategy"],
            normalized["symbol"],
            normalized["timeframe"],
            normalized["gap_tasks"],
            normalized["requested_bars"],
            normalized["remaining_gap_tasks"],
            normalized["rows_written"],
        )
    return normalize_swap_repair_summary_payloads(normalized_payloads)


def publish_swap_repair_ops_task(**context) -> dict[str, Any]:
    log_ctx = _build_log_context(context)
    logger.info("publish_swap_repair_ops start %s", log_ctx)
    env = get_dag_env()
    setup_env(env)

    ti = context["ti"]
    validated = ti.xcom_pull(task_ids="validate_swap_repair_conf", key="return_value")
    preview_payloads = ti.xcom_pull(task_ids="swap_repair_preview", key="return_value")
    summary_payloads = ti.xcom_pull(task_ids="validate_swap_repair_xcom", key="return_value")

    if not isinstance(validated, dict):
        raise ValueError("swap_repair publish step requires validated config dict")
    if preview_payloads is not None and not isinstance(preview_payloads, list):
        raise ValueError("swap_repair publish step preview payload must be a list when present")

    summary_payloads = normalize_swap_repair_summary_payloads(summary_payloads)
    metrics_pushed = push_swap_repair_metrics(summary_payloads)
    dag_run = context.get("dag_run")
    audit_rows = _get_loop().run_until_complete(
        write_swap_repair_audit(
            validated_conf=validated,
            preview_payloads=preview_payloads,
            summary_payloads=summary_payloads,
            dag_id=str(getattr(dag, "dag_id", "okx_swap_repair_v1")),
            dag_run_id=getattr(dag_run, "run_id", None),
            logical_date=context.get("logical_date"),
        )
    )
    result = {"metrics_pushed": metrics_pushed, "audit_rows_written": audit_rows}
    logger.info("publish_swap_repair_ops finish %s result=%s", log_ctx, result)
    return result


default_args = {
    "owner": "okx_swap_repair",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(hours=2),
    "on_failure_callback": DAG_FAILURE_CALLBACK,
    "on_success_callback": DAG_SUCCESS_CALLBACK,
    "on_retry_callback": DAG_RETRY_CALLBACK,
}

dag = DAG(
    dag_id="okx_swap_repair_v1",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["candles", "repair", "manual"],
    params={
        "trigger": Param(
            DEFAULT_TRIGGER,
            type="string",
            enum=sorted(REPAIR_TRIGGER_PRESETS),
            description="Manual trigger preset. Runtime repair settings live in code.",
        ),
    },
)

validate_swap_repair_conf = PythonOperator(
    task_id="validate_swap_repair_conf",
    python_callable=validate_swap_repair_conf_task,
    dag=dag,
)

preflight_instrument_check = PythonOperator(
    task_id="preflight_instrument_check",
    python_callable=preflight_instrument_check_task,
    dag=dag,
)

ensure_instruments_loaded = PythonOperator(
    task_id="ensure_instruments_loaded",
    python_callable=ensure_instruments_loaded_task,
    dag=dag,
)

swap_repair = PythonOperator(
    task_id="swap_repair",
    python_callable=swap_repair_task,
    dag=dag,
)

swap_repair_preview = PythonOperator(
    task_id="swap_repair_preview",
    python_callable=swap_repair_preview_task,
    dag=dag,
)

validate_swap_repair_xcom = PythonOperator(
    task_id="validate_swap_repair_xcom",
    python_callable=validate_swap_repair_xcom_task,
    dag=dag,
)

publish_swap_repair_ops = PythonOperator(
    task_id="publish_swap_repair_ops",
    python_callable=publish_swap_repair_ops_task,
    dag=dag,
)

validate_swap_repair_conf >> ensure_instruments_loaded >> preflight_instrument_check >> swap_repair_preview >> swap_repair >> validate_swap_repair_xcom >> publish_swap_repair_ops
