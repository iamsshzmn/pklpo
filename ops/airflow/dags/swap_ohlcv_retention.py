"""DAG: swap_ohlcv_retention.

Scheduled maintenance cleanup for ``swap_ohlcv_p``. Retention is driven by the
``swap_ohlcv_retention_policy`` table; ``NULL`` retention means infinite.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, cast

from _common import (  # type: ignore[import-not-found]
    get_dag_env as _get_common_dag_env,
    get_or_create_event_loop,
    setup_env as _setup_common_env,
)
from airflow import DAG
from airflow.exceptions import AirflowSkipException
from airflow.operators.python import PythonOperator
from sqlalchemy import text

from src.candles.bootstrap import create_candles_airflow_callbacks
from src.candles.infrastructure.ohlcv_write_lock import ohlcv_retention_write_lock
from src.pklpo_platform.observability import airflow_log_context
from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

try:
    _callbacks = create_candles_airflow_callbacks()
    DAG_FAILURE_CALLBACK = _callbacks.on_failure_callback
    DAG_SUCCESS_CALLBACK = _callbacks.on_success_callback
    DAG_RETRY_CALLBACK = _callbacks.on_retry_callback
except Exception:  # pragma: no cover - defensive Airflow import path
    DAG_FAILURE_CALLBACK = None
    DAG_SUCCESS_CALLBACK = None
    DAG_RETRY_CALLBACK = None


def _get_loop():
    return get_or_create_event_loop()


def get_dag_env() -> dict[str, str]:
    return cast(
        "dict[str, str]", _get_common_dag_env(job_name_default="swap_ohlcv_retention")
    )


def setup_env(env: dict[str, str]) -> None:
    _setup_common_env(env)


async def _run_cleanup(triggered_by: str, run_id: str | None) -> list[dict[str, Any]]:
    async with get_db_session() as session:
        async with ohlcv_retention_write_lock(session):
            result = await session.execute(
                text("SELECT * FROM cleanup_old_swap_data(:triggered_by, :run_id)"),
                {"triggered_by": triggered_by, "run_id": run_id},
            )
        rows = result.fetchall()
        await session.commit()

    return [
        {
            "timeframe": row[0],
            "cutoff_timestamp": row[1],
            "deleted_count": int(row[2]),
            "duration_ms": int(row[3]),
            "skipped_reason": row[4],
        }
        for row in rows
    ]


async def _bootstrap_cleanup_is_safe() -> bool:
    try:
        async with get_db_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM ops.swap_ohlcv_bootstrap_state
                    WHERE status NOT IN ('completed', 'skipped')
                    """
                )
            )
            active_count = int(result.scalar() or 0)
            await session.commit()
            return active_count == 0
    except Exception:
        logger.exception(
            "could not inspect ops.swap_ohlcv_bootstrap_state; skipping cleanup"
        )
        return False


def cleanup_swap_ohlcv_task(**context) -> dict[str, Any]:
    with airflow_log_context(context, component="swap_ohlcv_retention"):
        env = get_dag_env()
        setup_env(env)
        dag_run = context.get("dag_run")
        run_id = getattr(dag_run, "run_id", None)

        if not _get_loop().run_until_complete(_bootstrap_cleanup_is_safe()):
            raise AirflowSkipException(
                "bootstrap in progress; skipping retention cleanup"
            )

        rows = _get_loop().run_until_complete(
            _run_cleanup(triggered_by="airflow:swap_ohlcv_retention", run_id=run_id)
        )
        deleted_total = sum(row["deleted_count"] for row in rows)
        skipped = [row for row in rows if row["skipped_reason"]]
        duration_total_ms = sum(row["duration_ms"] for row in rows)
        logger.info(
            "swap_ohlcv_retention completed rows=%d deleted_total=%d skipped=%d duration_ms=%d",
            len(rows),
            deleted_total,
            len(skipped),
            duration_total_ms,
        )
        return {
            "rows": rows,
            "deleted_total": deleted_total,
            "skipped": len(skipped),
            "duration_ms": duration_total_ms,
        }


default_args = {
    "owner": "swap_ohlcv_retention",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
    "on_failure_callback": DAG_FAILURE_CALLBACK,
    "on_success_callback": DAG_SUCCESS_CALLBACK,
    "on_retry_callback": DAG_RETRY_CALLBACK,
}

dag = DAG(
    dag_id="swap_ohlcv_retention",
    start_date=datetime(2025, 1, 1),
    schedule="0 4 * * *",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["candles", "retention", "maintenance"],
)

cleanup_swap_ohlcv = PythonOperator(
    task_id="cleanup_swap_ohlcv",
    python_callable=cleanup_swap_ohlcv_task,
    dag=dag,
    pool="ohlcv_write_pool",
    pool_slots=1,
)
