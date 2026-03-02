"""DAG: features_calc_short."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.features.application.features_calc_short_service import (
    get_or_create_event_loop,
    run_features_calc_short,
    run_features_calc_short_validate,
)


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
    return env


def setup_env(env: dict[str, str | None]) -> None:
    for key, value in env.items():
        if value is not None:
            os.environ[key] = value
    Path("/tmp/pklpo").mkdir(parents=True, exist_ok=True)
    Path("/tmp/pklpo/data").mkdir(parents=True, exist_ok=True)


def features_calc_short_run_task(**context):
    env = get_dag_env()
    setup_env(env)

    dag_run = context.get("dag_run")
    conf = (dag_run.conf or {}) if dag_run else {}
    symbols = conf.get("symbols")
    timeframes = conf.get("timeframes", ["1m", "5m", "15m", "30m", "1H", "4H", "1D"])
    max_concurrent_symbols = conf.get("max_concurrent_symbols", 3)
    is_manual_run = bool(dag_run and dag_run.run_type == "manual")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    loop = get_or_create_event_loop()
    start_time = time.time()
    result = loop.run_until_complete(
        run_features_calc_short(
            database_url=database_url,
            symbols=symbols,
            timeframes=timeframes,
            max_concurrent_symbols=max_concurrent_symbols,
            is_manual_run=is_manual_run,
            max_lag_fast=int(conf.get("max_lag_fast", 240)),
            max_lag_slow=int(conf.get("max_lag_slow", 1200)),
            warmup_bars=int(conf.get("warmup_bars", 500)),
        )
    )
    if isinstance(result, dict):
        result["duration_seconds"] = round(time.time() - start_time, 2)
    return result


def features_calc_short_validate_task(**context):
    env = get_dag_env()
    setup_env(env)

    dag_run = context.get("dag_run")
    conf = (dag_run.conf or {}) if dag_run else {}
    quality_enabled = bool(conf.get("quality_postcheck_enabled", True))
    quality_send_alerts = bool(conf.get("quality_send_alerts", True))
    quality_alert_cooldown = int(conf.get("quality_alert_cooldown_minutes", 30))

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    loop = get_or_create_event_loop()
    return loop.run_until_complete(
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
}

dag = DAG(
    dag_id="features_calc_short",
    start_date=datetime(2025, 1, 1),
    schedule="*/15 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
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

features_calc_short_run >> features_calc_short_validate
