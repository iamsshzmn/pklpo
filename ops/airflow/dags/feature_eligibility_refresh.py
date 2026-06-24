"""DAG: feature_eligibility_refresh.

Daily materialized eligibility refresh for research timeframes.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

if "/opt/airflow/project" not in sys.path:
    sys.path.insert(0, "/opt/airflow/project")

from _common import get_or_create_event_loop  # type: ignore[import-not-found]
from airflow import DAG
from airflow.operators.python import PythonOperator

from src.candles.interfaces import eligibility as eligibility_interface
from src.pklpo_platform.observability import airflow_log_context

if TYPE_CHECKING:
    import asyncio


def _get_loop() -> asyncio.AbstractEventLoop:
    return cast("asyncio.AbstractEventLoop", get_or_create_event_loop())


def refresh_eligibility_task(**context: object) -> dict[str, int]:
    with airflow_log_context(context, component="feature_eligibility_refresh"):
        dag_run = context.get("dag_run")
        run_id = getattr(dag_run, "run_id", None) or "feature_eligibility_refresh"
        return _get_loop().run_until_complete(
            eligibility_interface.refresh_eligibility(evaluator_run_id=run_id)
        )


default_args = {
    "owner": "feature_eligibility",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
}

dag = DAG(
    dag_id="feature_eligibility_refresh",
    start_date=datetime(2025, 1, 1, tzinfo=UTC),
    schedule="0 2 * * *",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["features", "eligibility", "ops"],
)

refresh_eligibility = PythonOperator(
    task_id="refresh_eligibility",
    python_callable=refresh_eligibility_task,
    dag=dag,
)
