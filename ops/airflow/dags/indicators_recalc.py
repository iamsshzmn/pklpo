"""DAG: indicators_recalc.

Drain persisted feature recalculation requests from ``ops.indicator_recalc_queue``.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from airflow import DAG
from airflow.operators.python import PythonOperator
from sqlalchemy import text

if "/opt/airflow/project" not in sys.path:
    sys.path.insert(0, "/opt/airflow/project")

from src.config import get_settings
from src.core.run_context import RunContext
from src.features.api import (
    FEATURE_SPECS,
    compute_features,
    create_feature_application_bootstrap,
)
from src.features.application import RecalcFeaturesInRange
from src.features.application.save import save_batch
from src.pklpo_platform.observability import airflow_log_context
from src.utils.session_utils import get_db_session


def _to_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _queue_row_detail(row: dict[str, Any]) -> dict[str, Any]:
    detail = row.get("detail")
    if isinstance(detail, dict):
        return detail
    if isinstance(detail, str) and detail:
        parsed = json.loads(detail)
        return parsed if isinstance(parsed, dict) else {}
    return {}


async def _claim_indicator_recalc_rows(
    *,
    limit: int,
    stale_after_minutes: int,
) -> list[dict[str, Any]]:
    statement = text(
        """
        WITH candidate AS (
            SELECT id
            FROM ops.indicator_recalc_queue
            WHERE
                status = 'queued'
                OR (
                    status = 'claimed'
                    AND claimed_at < now()
                        - (CAST(:stale_after_minutes AS integer) * interval '1 minute')
                )
            ORDER BY enqueued_at, id
            LIMIT :limit
            FOR UPDATE SKIP LOCKED
        )
        UPDATE ops.indicator_recalc_queue q
        SET status = 'claimed',
            claimed_at = now()
        FROM candidate
        WHERE q.id = candidate.id
        RETURNING
            q.id,
            q.symbol,
            q.timeframe,
            q.range_start_ts,
            q.range_end_ts,
            q.warmup_bars,
            q.detail
        """
    )
    async with get_db_session() as session:
        result = await session.execute(
            statement,
            {
                "limit": limit,
                "stale_after_minutes": stale_after_minutes,
            },
        )
        return [dict(row) for row in result.mappings().all()]


async def _mark_indicator_recalc_row(
    row_id: int,
    *,
    status: str,
    detail: dict[str, Any],
) -> None:
    statement = text(
        """
        UPDATE ops.indicator_recalc_queue
        SET status = :status,
            completed_at = CASE
                WHEN :status = 'completed' THEN now()
                ELSE completed_at
            END,
            detail = COALESCE(detail, '{}'::jsonb) || CAST(:detail AS jsonb)
        WHERE id = :row_id
        """
    )
    async with get_db_session() as session:
        await session.execute(
            statement,
            {
                "row_id": row_id,
                "status": status,
                "detail": json.dumps(detail),
            },
        )


async def _process_indicator_recalc_row(
    row: dict[str, Any],
    *,
    run_id: str,
) -> dict[str, Any]:
    symbol = str(row["symbol"])
    timeframe = str(row["timeframe"])
    start_ts_ms = int(row["range_start_ts"])
    end_ts_ms = int(row["range_end_ts"])
    warmup_bars = int(row.get("warmup_bars") or get_settings().features.recommended_warmup_bars)
    detail = _queue_row_detail(row)
    specs = [str(item) for item in detail.get("specs", []) if str(item)]
    if not specs:
        specs = list(FEATURE_SPECS)

    bootstrap = create_feature_application_bootstrap()
    run_context = RunContext.create(
        {
            "use_case": "indicator_recalc_queue",
            "queue_row_id": row["id"],
            "symbol": symbol,
            "timeframe": timeframe,
            "start_ts_ms": start_ts_ms,
            "end_ts_ms": end_ts_ms,
            "specs": specs,
            "airflow_run_id": run_id,
        }
    )

    async with get_db_session() as session:
        deps = bootstrap.save_dependencies_factory(session)

        async def _fetch_ohlcv_df(**kwargs: Any) -> Any:
            return await bootstrap.storage_gateway.fetch_ohlcv_df(session, **kwargs)

        async def _save_features_df(df: Any, item_symbol: str, tf: str) -> int:
            result = await save_batch(
                session,
                df,
                item_symbol,
                tf,
                repository=deps.repository,
                observer=deps.observer,
                commit=False,
            )
            return int(result["rows_saved"])

        use_case = RecalcFeaturesInRange(
            fetch_ohlcv_df=_fetch_ohlcv_df,
            save_features_df=_save_features_df,
            compute_features_fn=lambda df, selected: compute_features(
                df,
                specs=selected,
                symbol=symbol,
                timeframe=timeframe,
            ),
            specs=specs,
            warmup_bars=warmup_bars,
        )
        outcome = await use_case.run(
            symbol=symbol,
            tf=timeframe,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
            run_context=run_context,
        )

    status = "completed" if outcome.rows_written > 0 else "blocked"
    result = {
        "status": status,
        "rows_written": outcome.rows_written,
        "run_id": outcome.run_id,
        "algo_version": outcome.algo_version,
        "params_hash": outcome.params_hash,
    }
    if status == "blocked":
        result["blocked_reason"] = "coverage_gate_failed_or_empty"
    return result


async def _drain_indicator_recalc_queue(
    *,
    run_id: str,
    limit: int,
    stale_after_minutes: int,
) -> dict[str, int]:
    rows = await _claim_indicator_recalc_rows(
        limit=limit,
        stale_after_minutes=stale_after_minutes,
    )
    summary = {
        "claimed": len(rows),
        "completed": 0,
        "blocked": 0,
        "failed": 0,
    }
    for row in rows:
        row_id = int(row["id"])
        try:
            result = await _process_indicator_recalc_row(row, run_id=run_id)
            status = str(result["status"])
        except Exception as exc:
            status = "failed"
            result = {"status": status, "error": str(exc), "run_id": run_id}
        await _mark_indicator_recalc_row(row_id, status=status, detail=result)
        if status in {"completed", "blocked"}:
            summary[status] += 1
        else:
            summary["failed"] += 1
    return summary


def drain_indicator_recalc_queue_task(**context: Any) -> dict[str, int]:
    with airflow_log_context(context, component="indicators_recalc"):
        dag_run = context.get("dag_run")
        conf = (getattr(dag_run, "conf", None) or {}) if dag_run else {}
        run_id = getattr(dag_run, "run_id", None) or "indicators_recalc"
        return asyncio.run(
            _drain_indicator_recalc_queue(
                run_id=run_id,
                limit=_to_int(conf.get("limit"), 25),
                stale_after_minutes=_to_int(conf.get("stale_after_minutes"), 60),
            )
        )


os.environ.setdefault("FEATURES_LOG_FILE", "/tmp/pklpo/features.log")  # noqa: S108

default_args = {
    "owner": "features",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

dag = DAG(
    dag_id="indicators_recalc",
    start_date=datetime(2025, 1, 1, tzinfo=UTC),
    schedule="*/10 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["features", "recalc", "ops"],
)

drain_indicator_recalc_queue = PythonOperator(
    task_id="drain_indicator_recalc_queue",
    python_callable=drain_indicator_recalc_queue_task,
    dag=dag,
    pool="compute_pool",
    pool_slots=1,
)
