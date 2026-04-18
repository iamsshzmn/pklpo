"""DAG: okx_swap_repair_v1.

Production-oriented manual DAG contract for OKX swap historical repair.

Purpose
- Reuse ``src.candles.interfaces.run_swap_repair`` as the single business entrypoint.
- Keep Airflow as a thin orchestration layer with strict preflight validation.
- Stay safe-by-default: no schedule, one symbol, bounded window, repair-safe timeframes only.

Run parameters (via dag_run.conf)
- symbol: str, optional, only ``BTC-USDT-SWAP`` is supported in v1
- timeframe: str, optional legacy single-timeframe field
- timeframes: list[str] | comma-separated str, optional, runs repair for each requested timeframe
- start: UTC ISO-8601 timestamp, optional
- end: UTC ISO-8601 timestamp, optional
- window_hours: int, default ``6`` when ``start``/``end`` are omitted
- mode: ``detect-only`` | ``dry-run`` | ``apply``
- repair_strategy: ``gap-repair`` | ``backfill``
- padding_bars: int, default ``0``
- max_gap_tasks_per_run: int, default ``50``
- max_requested_bars_per_run: int, default ``10000``
- max_range_days: int, default ``7``
- max_fail_ratio: float, default ``0.1``
- auto_apply_anchor_strategy: ``first-coverage`` | ``listing-date`` | ``explicit``
- auto_apply_anchor: UTC ISO-8601 timestamp, optional explicit anchor for apply without coverage

Contract
- `apply` requires explicit `start` and `end`, or `auto_apply_anchor` for empty-coverage bootstrap
- only `BTC-USDT-SWAP` is allowed in v1
- each requested timeframe must stay within the current repair-safe OKX set
- `apply` succeeds only when every timeframe result reports `verified=true`,
  `remaining_gap_tasks=0`, `remaining_requested_bars=0`, and
  `verification_method=gap-detection`, unless the result is a truthful partial
  auto-apply summary with `auto_apply_incomplete=true`
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from airflow import DAG
from airflow.models.param import Param
from airflow.operators.python import PythonOperator

from _common import (
    SwapRepairValidatedConf,
    coerce_float as _coerce_float,
    coerce_int as _coerce_int,
    get_dag_env as _get_common_dag_env,
    get_or_create_event_loop,
    normalize_swap_repair_conf,
    normalize_swap_repair_summary_payloads,
    parse_utc_timestamp_ms as _parse_utc_timestamp_ms,
    payload_to_dict as _payload_to_dict,
    setup_env as _setup_common_env,
    utc_now_ts_ms as _utc_now_ts_ms,
    validate_swap_repair_xcom_payload,
)
from src.candles.bootstrap import create_candles_airflow_callbacks
from src.candles.domain.repair import RepairExecutionMode, RepairStrategy
from src.candles.interfaces import repair as repair_interface
from src.candles.interfaces.repair_audit import write_swap_repair_audit
from src.candles.observability.prometheus import push_swap_repair_metrics

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import asyncio

DEFAULT_SYMBOL = "BTC-USDT-SWAP"
DEFAULT_WINDOW_HOURS = 6
SUPPORTED_SYMBOLS = (DEFAULT_SYMBOL,)
SUPPORTED_TIMEFRAMES = ("1m", "1H", "4H", "1D", "1W", "1M")

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


def _run_swap_repair_once(
    *,
    validated: dict[str, Any],
    timeframe: str,
    start_ts_ms: int,
    end_ts_ms: int,
    ) -> dict[str, Any]:
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
        )
    )


def _run_auto_apply_for_timeframe(
    *,
    validated: dict[str, Any],
    timeframe: str,
) -> dict[str, Any]:
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
        )
    )


def validate_swap_repair_conf_task(**context) -> dict[str, Any]:
    conf = _get_run_conf(context)
    log_ctx = _build_log_context(context)
    logger.info("validate_swap_repair_conf start %s raw_conf=%s", log_ctx, conf)
    validated = normalize_swap_repair_conf(
        conf,
        now_ts_ms=_utc_now_ts_ms(),
        parse_timestamp_ms=_parse_utc_timestamp_ms,
    )
    logger.info(
        "validate_swap_repair_conf finish %s symbol=%s timeframes=%s mode=%s strategy=%s auto_apply_window=%s",
        log_ctx,
        validated.symbol,
        validated.timeframes,
        validated.mode,
        validated.repair_strategy,
        validated.auto_apply_window,
    )
    return validated.to_dict()


def swap_repair_task(**context) -> list[dict[str, Any]]:
    log_ctx = _build_log_context(context)
    logger.info("swap_repair start %s", log_ctx)
    env = get_dag_env()
    setup_env(env)

    ti = context["ti"]
    validated = ti.xcom_pull(task_ids="validate_swap_repair_conf", key="return_value")
    if not isinstance(validated, dict):
        raise ValueError("swap_repair validated config must be a dict")
    validated_conf = SwapRepairValidatedConf(**validated)

    if not validated_conf.timeframes:
        raise ValueError("swap_repair validated config must contain non-empty timeframes")

    summaries = []
    for timeframe in validated_conf.timeframes:
        if validated_conf.auto_apply_window:
            summary = _run_auto_apply_for_timeframe(
                validated=validated,
                timeframe=str(timeframe),
            )
        else:
            summary = _run_swap_repair_once(
                validated=validated,
                timeframe=str(timeframe),
                start_ts_ms=_coerce_int(
                    validated_conf.start_ts_ms,
                    field_name="validated.start_ts_ms",
                ),
                end_ts_ms=_coerce_int(
                    validated_conf.end_ts_ms,
                    field_name="validated.end_ts_ms",
                ),
            )
        logger.info(
            "swap_repair finish %s timeframe=%s summary=%s",
            log_ctx,
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
    validated_conf = SwapRepairValidatedConf(**validated)

    if not validated_conf.timeframes:
        raise ValueError("swap_repair preview validated config must contain non-empty timeframes")

    previews: list[dict[str, Any]] = []
    for timeframe in validated_conf.timeframes:
        preview = _get_loop().run_until_complete(
            repair_interface.plan_swap_repair(
                symbol=validated_conf.symbol,
                timeframe=str(timeframe),
                start_ts_ms=validated_conf.start_ts_ms,
                end_ts_ms=validated_conf.end_ts_ms,
                mode=RepairExecutionMode(validated_conf.mode),
                strategy=RepairStrategy(validated_conf.repair_strategy),
                auto_apply_window=validated_conf.auto_apply_window,
                max_gap_tasks_per_run=_coerce_int(
                    validated_conf.max_gap_tasks_per_run,
                    field_name="validated.max_gap_tasks_per_run",
                ),
                max_requested_bars_per_run=_coerce_int(
                    validated_conf.max_requested_bars_per_run,
                    field_name="validated.max_requested_bars_per_run",
                ),
                max_range_days=_coerce_int(
                    validated_conf.max_range_days,
                    field_name="validated.max_range_days",
                ),
                max_fail_ratio=_coerce_float(
                    validated_conf.max_fail_ratio,
                    field_name="validated.max_fail_ratio",
                ),
                padding_bars=_coerce_int(
                    validated_conf.padding_bars,
                    field_name="validated.padding_bars",
                ),
                anchor_ts_ms=(
                    _coerce_int(
                        validated_conf.anchor_ts_ms,
                        field_name="validated.anchor_ts_ms",
                    )
                    if validated_conf.anchor_ts_ms is not None
                    else None
                ),
                auto_apply_anchor_strategy=validated_conf.auto_apply_anchor_strategy,
            )
        )
        logger.info(
            "swap_repair_preview finish %s timeframe=%s preview=%s",
            log_ctx,
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
                allowed_symbols=SUPPORTED_SYMBOLS,
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
    validated_conf = SwapRepairValidatedConf(**validated)
    if preview_payloads is not None and not isinstance(preview_payloads, list):
        raise ValueError("swap_repair publish step preview payload must be a list when present")

    summary_payloads = normalize_swap_repair_summary_payloads(summary_payloads)
    metrics_pushed = push_swap_repair_metrics(summary_payloads)
    dag_run = context.get("dag_run")
    audit_rows = _get_loop().run_until_complete(
        write_swap_repair_audit(
            validated_conf=validated_conf.to_dict(),
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
        "symbol": Param(DEFAULT_SYMBOL, type="string", enum=list(SUPPORTED_SYMBOLS)),
        "timeframes": Param(
            list(SUPPORTED_TIMEFRAMES),
            type="array",
            items={"type": "string", "enum": list(SUPPORTED_TIMEFRAMES)},
            minItems=1,
            description="Repair-safe OKX timeframes",
        ),
        "mode": Param(
            RepairExecutionMode.DETECT_ONLY.value,
            type="string",
            enum=[mode.value for mode in RepairExecutionMode],
        ),
        "repair_strategy": Param(
            RepairStrategy.GAP_REPAIR.value,
            type="string",
            enum=[strategy.value for strategy in RepairStrategy],
        ),
        "start": Param(None, type=["null", "string"], format="date-time"),
        "end": Param(None, type=["null", "string"], format="date-time"),
        "auto_apply_anchor_strategy": Param(
            "first-coverage",
            type="string",
            enum=["first-coverage", "listing-date", "explicit"],
            description="Anchor strategy for apply runs without existing coverage",
        ),
        "auto_apply_anchor": Param(
            None,
            type=["null", "string"],
            format="date-time",
            description="Optional explicit anchor for apply runs without coverage",
        ),
        "window_hours": Param(DEFAULT_WINDOW_HOURS, type="integer", minimum=1),
        "padding_bars": Param(0, type="integer", minimum=0),
        "max_gap_tasks_per_run": Param(50, type="integer", minimum=1),
        "max_requested_bars_per_run": Param(10_000, type="integer", minimum=1),
        "max_range_days": Param(7, type="integer", minimum=1),
        "max_fail_ratio": Param(0.1, type="number", minimum=0, maximum=1),
    },
)

validate_swap_repair_conf = PythonOperator(
    task_id="validate_swap_repair_conf",
    python_callable=validate_swap_repair_conf_task,
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

validate_swap_repair_conf >> swap_repair_preview >> swap_repair >> validate_swap_repair_xcom >> publish_swap_repair_ops
