"""Shared helpers for Airflow DAGs."""

from .async_runner import get_or_create_event_loop, run_coroutine
from .env import (
    get_dag_env,
    normalize_async_database_uri,
    project_env_default,
    setup_env,
)
from .observability import (
    airflow_log_context,
    airflow_run_id,
    airflow_task_id,
)
from .repair import (
    DEFAULT_SWAP_REPAIR_SYMBOL,
    DEFAULT_SWAP_REPAIR_TIMEFRAMES,
    DEFAULT_SWAP_REPAIR_WINDOW_HOURS,
    SwapRepairValidatedConf,
    coerce_float,
    coerce_int,
    normalize_swap_repair_conf,
    normalize_swap_repair_summary_payloads,
    normalize_swap_repair_timeframe,
    parse_utc_timestamp_ms,
    payload_to_dict,
    resolve_repair_window_from_conf,
    utc_now_ts_ms,
    validate_swap_repair_xcom_payload,
)

__all__ = [
    "DEFAULT_SWAP_REPAIR_SYMBOL",
    "DEFAULT_SWAP_REPAIR_TIMEFRAMES",
    "DEFAULT_SWAP_REPAIR_WINDOW_HOURS",
    "SwapRepairValidatedConf",
    "coerce_float",
    "coerce_int",
    "get_dag_env",
    "get_or_create_event_loop",
    "airflow_log_context",
    "airflow_run_id",
    "airflow_task_id",
    "normalize_async_database_uri",
    "normalize_swap_repair_conf",
    "normalize_swap_repair_summary_payloads",
    "normalize_swap_repair_timeframe",
    "parse_utc_timestamp_ms",
    "payload_to_dict",
    "project_env_default",
    "resolve_repair_window_from_conf",
    "run_coroutine",
    "setup_env",
    "utc_now_ts_ms",
    "validate_swap_repair_xcom_payload",
]
