"""DAG: features_calc_short.

Incremental short-path features calculation over `swap_ohlcv_p` into
`indicators_p` via the public `src.features` module boundary.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

os.environ.setdefault("FEATURES_LOG_FILE", "/tmp/pklpo/features.log")  # noqa: S108
os.environ.setdefault("MARKET_META_LOG_FILE", "/tmp/pklpo/market_meta.log")  # noqa: S108
os.environ.setdefault("MARKET_META_FILE_LOG", "false")
os.environ.setdefault("MARKET_META_LOG_LEVEL", "WARNING")
os.environ.setdefault("MARKET_META_DATA_DIR", "/tmp/pklpo/data")  # noqa: S108
os.environ.setdefault("INSTRUMENTS_CACHE_DIR", "/tmp/pklpo")  # noqa: S108

if "/opt/airflow/project" not in sys.path:
    sys.path.insert(0, "/opt/airflow/project")

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.features.api import (
    run_features_calc_short,
    run_features_calc_short_validate,
)
from src.features.bootstrap import create_feature_airflow_callbacks

try:
    _callbacks = create_feature_airflow_callbacks()
    DAG_FAILURE_CALLBACK = _callbacks.on_failure_callback
    DAG_SUCCESS_CALLBACK = _callbacks.on_success_callback
    DAG_SLA_MISS_CALLBACK = _callbacks.sla_miss_callback
except Exception as exc:  # pragma: no cover - defensive Airflow import path
    print(f"[features_calc_short] alert callbacks unavailable: {exc}")
    DAG_FAILURE_CALLBACK = None
    DAG_SUCCESS_CALLBACK = None
    DAG_SLA_MISS_CALLBACK = None


DEFAULT_TIMEFRAMES = ["1m", "5m", "15m", "30m", "1H", "4H", "1D"]


def _to_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _to_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_symbols(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.lower() in {"", "none", "null"}:
            return None
        return [item for item in normalized.replace(",", " ").split() if item]
    if isinstance(value, (list, tuple, set)):
        symbols = [str(item).strip() for item in value if str(item).strip()]
        return symbols or None
    return None


def _normalize_timeframes(value: Any) -> list[str]:
    if value is None:
        return list(DEFAULT_TIMEFRAMES)
    if isinstance(value, str):
        timeframes = [item for item in value.replace(",", " ").split() if item]
        return timeframes or list(DEFAULT_TIMEFRAMES)
    if isinstance(value, (list, tuple, set)):
        timeframes = [str(item).strip() for item in value if str(item).strip()]
        return timeframes or list(DEFAULT_TIMEFRAMES)
    return list(DEFAULT_TIMEFRAMES)


def get_dag_env() -> dict[str, str]:
    """Load runtime env from Airflow Connection/Variables."""
    from airflow.hooks.base import BaseHook
    from airflow.models import Variable

    env: dict[str, str] = {}
    try:
        conn = BaseHook.get_connection("pklpo_db")
        if not conn:
            raise RuntimeError("Airflow connection 'pklpo_db' is not configured")
        uri = conn.get_uri()
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql+asyncpg://", 1)
        env["DATABASE_URL"] = uri
    except Exception as exc:
        raise RuntimeError(
            "DATABASE_URL is not configured. Set Airflow Connection 'pklpo_db'."
        ) from exc

    env["DATABASE_SSL"] = Variable.get("pklpo_database_ssl", default_var="disable")
    env["FEATURES_LOG_FILE"] = Variable.get(
        "features_log_file",
        default_var=os.environ.get("FEATURES_LOG_FILE", "/tmp/pklpo/features.log"),  # noqa: S108
    )
    env["MARKET_META_LOG_FILE"] = Variable.get(
        "market_meta_log_file",
        default_var=os.environ.get(
            "MARKET_META_LOG_FILE", "/tmp/pklpo/market_meta.log"  # noqa: S108
        ),
    )
    env["MARKET_META_FILE_LOG"] = Variable.get(
        "market_meta_file_log",
        default_var=os.environ.get("MARKET_META_FILE_LOG", "false"),
    )
    env["MARKET_META_LOG_LEVEL"] = Variable.get(
        "market_meta_log_level",
        default_var=os.environ.get("MARKET_META_LOG_LEVEL", "WARNING"),
    )
    env["MARKET_META_DATA_DIR"] = Variable.get(
        "market_meta_data_dir",
        default_var=os.environ.get("MARKET_META_DATA_DIR", "/tmp/pklpo/data"),  # noqa: S108
    )
    env["INSTRUMENTS_CACHE_DIR"] = Variable.get(
        "instruments_cache_dir",
        default_var=os.environ.get("INSTRUMENTS_CACHE_DIR", "/tmp/pklpo"),  # noqa: S108
    )
    return env


def setup_env(env: dict[str, str | None]) -> None:
    for key, value in env.items():
        if value is not None:
            os.environ[key] = value
    tmp_root_value = os.environ.get("INSTRUMENTS_CACHE_DIR")
    data_root_value = os.environ.get("MARKET_META_DATA_DIR")
    tmp_root = (
        Path(tmp_root_value)
        if tmp_root_value
        else Path(tempfile.gettempdir()) / "pklpo"
    )
    data_root = Path(data_root_value) if data_root_value else (tmp_root / "data")
    tmp_root.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)


def features_calc_short_run_task(**context):
    env = get_dag_env()
    setup_env(env)

    dag_run = context.get("dag_run")
    conf = (dag_run.conf or {}) if dag_run else {}
    symbols = _normalize_symbols(conf.get("symbols"))
    timeframes = _normalize_timeframes(conf.get("timeframes"))
    max_concurrent_symbols = _to_int(conf.get("max_concurrent_symbols"), 3)
    is_manual_run = bool(dag_run and dag_run.run_type == "manual")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    start_time = time.time()
    result = asyncio.run(
        run_features_calc_short(
            database_url=database_url,
            symbols=symbols,
            timeframes=timeframes,
            max_concurrent_symbols=max_concurrent_symbols,
            is_manual_run=is_manual_run,
            max_lag_fast=_to_int(conf.get("max_lag_fast"), 240),
            max_lag_slow=_to_int(conf.get("max_lag_slow"), 1200),
            warmup_bars=_to_int(conf.get("warmup_bars"), 500),
        )
    )
    if isinstance(result, dict):
        result["duration_seconds"] = round(time.time() - start_time, 2)
    return result


def features_calc_short_prepare_storage_task(**context):
    env = get_dag_env()
    setup_env(env)

    dag_run = context.get("dag_run")
    conf = (dag_run.conf or {}) if dag_run else {}
    reference_dt = context.get("logical_date")

    from src.db.indicators_partition.interfaces import (
        run_indicators_partition_maintenance,
    )

    return asyncio.run(
        run_indicators_partition_maintenance(
            months_back=_to_int(conf.get("partition_months_back"), 1),
            months_ahead=_to_int(conf.get("partition_months_ahead"), 3),
            reference_dt=reference_dt,
            require_parent_pk=True,
            repair_parent_schema=True,
        )
    )


def features_calc_short_validate_task(**context):
    env = get_dag_env()
    setup_env(env)

    dag_run = context.get("dag_run")
    conf = (dag_run.conf or {}) if dag_run else {}
    quality_enabled = _to_bool(conf.get("quality_postcheck_enabled"), True)
    quality_send_alerts = _to_bool(conf.get("quality_send_alerts"), True)
    quality_alert_cooldown = _to_int(conf.get("quality_alert_cooldown_minutes"), 30)

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    return asyncio.run(
        run_features_calc_short_validate(
            database_url=database_url,
            quality_enabled=quality_enabled,
            quality_send_alerts=quality_send_alerts,
            quality_alert_cooldown=quality_alert_cooldown,
        )
    )


default_args = {
    "owner": "features_calc_short",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
    "on_failure_callback": DAG_FAILURE_CALLBACK,
    "on_success_callback": DAG_SUCCESS_CALLBACK,
}

dag = DAG(
    dag_id="features_calc_short",
    start_date=datetime(2025, 1, 1),
    schedule="*/15 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    sla_miss_callback=DAG_SLA_MISS_CALLBACK,
)

features_calc_short_prepare_storage = PythonOperator(
    task_id="features_calc_short_prepare_storage",
    python_callable=features_calc_short_prepare_storage_task,
    dag=dag,
)

features_calc_short_run = PythonOperator(
    task_id="features_calc_short_run",
    python_callable=features_calc_short_run_task,
    dag=dag,
)

features_calc_short_validate = PythonOperator(
    task_id="features_calc_short_validate",
    python_callable=features_calc_short_validate_task,
    dag=dag,
)

features_calc_short_prepare_storage >> features_calc_short_run >> features_calc_short_validate
