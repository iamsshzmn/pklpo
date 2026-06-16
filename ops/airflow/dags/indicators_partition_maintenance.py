"""DAG: indicators_partition_maintenance."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from airflow import DAG
from airflow.operators.python import PythonOperator

if "/opt/airflow/project" not in sys.path:
    sys.path.insert(0, "/opt/airflow/project")

from src.pklpo_platform.observability import airflow_log_context

logger = logging.getLogger(__name__)

DEFAULT_MONTHS_BACK = 1
DEFAULT_MONTHS_AHEAD = 3


def _parse_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def get_or_create_event_loop():
    """Gets existing event loop or creates a new one."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Event loop is closed")
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


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
    Path("/tmp/pklpo").mkdir(parents=True, exist_ok=True)  # noqa: S108


def _parse_reference_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


async def _run_partition_maintenance_async(
    *,
    months_back: int,
    months_ahead: int,
    reference_dt: datetime | None,
    require_parent_pk: bool,
) -> dict[str, Any]:
    from src.db.indicators_partition.interfaces.indicators_partition_maintenance import (
        run_indicators_partition_maintenance,
    )

    return await run_indicators_partition_maintenance(
        months_back=months_back,
        months_ahead=months_ahead,
        reference_dt=reference_dt,
        require_parent_pk=require_parent_pk,
    )


async def _run_partition_validation_async(
    *,
    months_ahead: int,
    reference_dt: datetime | None,
) -> dict[str, Any]:
    from src.db.indicators_partition.interfaces.indicators_partition_maintenance import (
        run_indicators_partition_validation,
    )

    return await run_indicators_partition_validation(
        months_ahead=months_ahead,
        reference_dt=reference_dt,
    )


def run_partition_maintenance_task(**context) -> dict[str, Any]:
    with airflow_log_context(context, component="indicators_partition_maintenance"):
        env = get_dag_env()
        setup_env(env)

        dag_run = context.get("dag_run")
        conf = (dag_run.conf or {}) if dag_run else {}
        months_back = int(conf.get("months_back", DEFAULT_MONTHS_BACK))
        months_ahead = int(conf.get("months_ahead", DEFAULT_MONTHS_AHEAD))
        require_parent_pk = _parse_bool(conf.get("require_parent_pk", True))
        reference_dt = _parse_reference_dt(conf.get("reference_dt"))

        logger.info(
            "partition_maintenance start months_back=%s months_ahead=%s reference_dt=%s",
            months_back,
            months_ahead,
            reference_dt.isoformat() if reference_dt else "now",
        )

        loop = get_or_create_event_loop()
        result = loop.run_until_complete(
            _run_partition_maintenance_async(
                months_back=months_back,
                months_ahead=months_ahead,
                reference_dt=reference_dt,
                require_parent_pk=require_parent_pk,
            )
        )

        logger.info(
            "partition_maintenance finish created=%s existing=%s",
            result.get("created_count"),
            result.get("existing_count"),
        )
        return result


def validate_partition_horizon_task(**context) -> dict[str, Any]:
    with airflow_log_context(context, component="indicators_partition_maintenance"):
        env = get_dag_env()
        setup_env(env)

        dag_run = context.get("dag_run")
        conf = (dag_run.conf or {}) if dag_run else {}
        months_ahead = int(conf.get("months_ahead", DEFAULT_MONTHS_AHEAD))
        reference_dt = _parse_reference_dt(conf.get("reference_dt"))

        logger.info(
            "partition_validation start months_ahead=%s reference_dt=%s",
            months_ahead,
            reference_dt.isoformat() if reference_dt else "now",
        )

        loop = get_or_create_event_loop()
        result = loop.run_until_complete(
            _run_partition_validation_async(
                months_ahead=months_ahead,
                reference_dt=reference_dt,
            )
        )

        logger.info(
            "partition_validation finish actual_months_ahead=%s",
            result.get("actual_months_ahead"),
        )
        return result


default_args = {
    "owner": "pklpo",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=15),
}

dag = DAG(
    dag_id="indicators_partition_maintenance",
    start_date=datetime(2025, 1, 1),
    schedule="0 1 * * *",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
)

ensure_indicators_partitions = PythonOperator(
    task_id="ensure_indicators_partitions",
    python_callable=run_partition_maintenance_task,
    dag=dag,
)

validate_partition_horizon = PythonOperator(
    task_id="validate_partition_horizon",
    python_callable=validate_partition_horizon_task,
    dag=dag,
)

ensure_indicators_partitions >> validate_partition_horizon
