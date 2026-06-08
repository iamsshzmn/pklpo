"""DAG: pipeline_monitoring.

Read-only operational snapshot for pipeline health and backlog metrics.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from _common import (  # type: ignore[import-not-found]
    get_dag_env as _get_common_dag_env,
    get_or_create_event_loop,
    setup_env as _setup_common_env,
)
from airflow import DAG
from airflow.operators.python import PythonOperator
from sqlalchemy import text

if "/opt/airflow/project" not in sys.path:
    sys.path.insert(0, "/opt/airflow/project")

from src.candles.observability.prometheus import push_pipeline_monitoring_metrics
from src.utils.session_utils import get_db_session

if TYPE_CHECKING:
    import asyncio


def _get_loop() -> asyncio.AbstractEventLoop:
    return cast("asyncio.AbstractEventLoop", get_or_create_event_loop())


def get_dag_env() -> dict[str, str]:
    return cast(
        "dict[str, str]", _get_common_dag_env(job_name_default="pipeline_monitoring")
    )


def setup_env(env: dict[str, str]) -> None:
    _setup_common_env(env)


async def _fetch_keyed_counts(
    session: Any,
    sql: str,
    *,
    key_fields: tuple[str, ...],
) -> dict[Any, int]:
    result = await session.execute(text(sql))
    output: dict[Any, int] = {}
    for row in result.mappings().all():
        key: Any
        if len(key_fields) == 1:
            key = str(row[key_fields[0]])
        else:
            key = tuple(str(row[field]) for field in key_fields)
        output[key] = int(row["count"])
    return output


async def _collect_pipeline_monitoring_snapshot() -> dict[str, Any]:
    async with get_db_session() as session:
        lag_result = await session.execute(
            text(
                """
                SELECT
                    timeframe,
                    EXTRACT(EPOCH FROM (now() - to_timestamp(MAX(timestamp) / 1000.0)))
                        AS lag_seconds
                FROM swap_ohlcv_p
                GROUP BY timeframe
                """
            )
        )
        candle_lag_seconds = {
            str(row["timeframe"]): float(row["lag_seconds"] or 0.0)
            for row in lag_result.mappings().all()
        }
        recalc_queue = await _fetch_keyed_counts(
            session,
            """
            SELECT status, COUNT(*) AS count
            FROM ops.indicator_recalc_queue
            GROUP BY status
            """,
            key_fields=("status",),
        )
        bootstrap_state = await _fetch_keyed_counts(
            session,
            """
            SELECT status, COUNT(*) AS count
            FROM ops.swap_ohlcv_bootstrap_state
            GROUP BY status
            """,
            key_fields=("status",),
        )
        eligibility_state_counts = await _fetch_keyed_counts(
            session,
            """
            SELECT timeframe, state, COUNT(*) AS count
            FROM ops.feature_eligibility
            GROUP BY timeframe, state
            """,
            key_fields=("timeframe", "state"),
        )
        eligibility_state = [
            {"timeframe": timeframe, "state": state, "count": count}
            for (timeframe, state), count in eligibility_state_counts.items()
        ]

    alerts = {
        "critical": int(recalc_queue.get("failed", 0))
        + int(recalc_queue.get("blocked", 0))
        + int(bootstrap_state.get("failed", 0)),
        "warning": int(recalc_queue.get("queued", 0))
        + int(bootstrap_state.get("running", 0)),
    }
    return {
        "candle_lag_seconds": candle_lag_seconds,
        "recalc_queue": recalc_queue,
        "bootstrap_state": bootstrap_state,
        "eligibility_state": eligibility_state,
        "alerts": alerts,
    }


def collect_pipeline_monitoring_task(**context: Any) -> dict[str, Any]:
    del context
    env = get_dag_env()
    setup_env(env)
    snapshot = _get_loop().run_until_complete(_collect_pipeline_monitoring_snapshot())
    metrics_pushed = push_pipeline_monitoring_metrics(snapshot)
    return {**snapshot, "metrics_pushed": metrics_pushed}


default_args = {
    "owner": "pipeline_monitoring",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=10),
}

dag = DAG(
    dag_id="pipeline_monitoring",
    start_date=datetime(2025, 1, 1, tzinfo=UTC),
    schedule="*/10 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["monitoring", "read-only", "ops"],
)

collect_pipeline_monitoring = PythonOperator(
    task_id="collect_pipeline_monitoring",
    python_callable=collect_pipeline_monitoring_task,
    dag=dag,
)
