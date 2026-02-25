"""
DAG: market_selection

Назначение:
- Выбор торговых пар на основе Data Quality, Pair Metrics, Global Regime
- Запускается после features_calc_short каждые 4 часа
- Результат: market_universe с top-N парами для features_calc_full

Параметры запуска (через dag_run.conf):
- top_n: int (default: 30) - количество пар в universe
- force_run: bool (default: false) - игнорировать freshness check

Таблицы:
- market_scores_tf: per-symbol per-TF scores
- market_universe: selected trading pairs
- market_universe_versions: versioning and audit
- market_regime_history: global regime history
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sensors.external_task import ExternalTaskSensor

logger = logging.getLogger(__name__)

# Default args
default_args = {
    "owner": "pklpo",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def get_or_create_event_loop():
    """Gets existing event loop or creates new one."""
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
    """Get environment from Airflow Connections/Variables."""
    from airflow.hooks.base import BaseHook
    from airflow.models import Variable

    env = {}

    # DATABASE_URL from Airflow Connection
    try:
        conn = BaseHook.get_connection("pklpo_db")
        if not conn:
            raise RuntimeError("Airflow connection 'pklpo_db' is not configured")

        uri = conn.get_uri()
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql+asyncpg://", 1)
        env["DATABASE_URL"] = uri
    except Exception as e:
        raise RuntimeError(
            "DATABASE_URL not configured. Set Airflow Connection 'pklpo_db'"
        ) from e

    env["DATABASE_SSL"] = Variable.get("pklpo_database_ssl", default_var="disable")

    return env


def setup_env(env: dict[str, str | None]) -> None:
    """Set environment variables."""
    for key, value in env.items():
        if value is not None:
            os.environ[key] = value

    Path("/tmp/pklpo").mkdir(parents=True, exist_ok=True)


async def _run_migrations_async(database_url: str) -> bool:
    """Run market_selection migrations."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from src.market_selection.migrations import run_market_selection_migrations

    engine = create_async_engine(database_url, echo=False)

    async with AsyncSession(engine) as session:
        await run_market_selection_migrations(session)
        return True


def run_migrations_task(**context) -> dict[str, Any]:
    """Airflow task: run database migrations."""
    env = get_dag_env()
    setup_env(env)

    loop = get_or_create_event_loop()
    result = loop.run_until_complete(_run_migrations_async(env["DATABASE_URL"]))

    return {"migrations_ok": result}


async def _run_pipeline_async(database_url: str, params: dict) -> dict[str, Any]:
    """Run market selection pipeline."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from src.market_selection.application.pipeline import MarketSelectionPipeline
    from src.market_selection.config import MarketSelectionConfig

    engine = create_async_engine(database_url, echo=False)

    # Build config with overrides from params
    config = MarketSelectionConfig()
    if "top_n" in params:
        config.universe.top_n = int(params["top_n"])

    async with AsyncSession(engine) as session:
        pipeline = MarketSelectionPipeline(session, config)
        result = await pipeline.run()

    return {
        "success": result.success,
        "ts_version": result.ts_version,
        "ts_eval": result.ts_eval,
        "universe_size": result.universe_size,
        "status": result.status.value,
        "global_regime": result.global_regime.value if result.global_regime else None,
        "eligible_counts": result.eligible_counts,
        "execution_time_seconds": result.execution_time_seconds,
        "config_hash": result.config_hash,
        "error_message": result.error_message,
    }


def run_pipeline_task(**context) -> dict[str, Any]:
    """Airflow task: run market selection pipeline."""
    env = get_dag_env()
    setup_env(env)

    params = context.get("params", {})
    dag_run_conf = context.get("dag_run").conf or {}
    params.update(dag_run_conf)

    loop = get_or_create_event_loop()
    result = loop.run_until_complete(_run_pipeline_async(env["DATABASE_URL"], params))

    if not result["success"]:
        logger.error(f"Pipeline failed: {result.get('error_message')}")
        raise RuntimeError(f"Market selection failed: {result.get('error_message')}")

    logger.info(
        f"Market selection completed: {result['universe_size']} symbols, "
        f"regime={result['global_regime']}, "
        f"time={result['execution_time_seconds']:.2f}s"
    )

    return result


async def _validate_universe_async(database_url: str) -> dict[str, Any]:
    """Validate the published universe."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    engine = create_async_engine(database_url, echo=False)

    async with AsyncSession(engine) as session:
        # Check latest version
        result = await session.execute(text("""
            SELECT ts_version, status, universe_size, global_regime, config_hash
            FROM market_universe_versions
            ORDER BY ts_version DESC
            LIMIT 1
        """))
        row = result.fetchone()

        if not row:
            return {"valid": False, "reason": "No universe version found"}

        ts_version, status, universe_size, regime, config_hash = row

        if status not in ("published", "fallback_prev"):
            return {
                "valid": False,
                "reason": f"Latest version status is {status}",
                "ts_version": ts_version,
            }

        if universe_size < 5:
            return {
                "valid": False,
                "reason": f"Universe too small: {universe_size}",
                "ts_version": ts_version,
            }

        # Get symbols
        symbols_result = await session.execute(text("""
            SELECT symbol, final_score, rank
            FROM market_universe
            WHERE ts_version = :ts_version
            ORDER BY rank
            LIMIT 10
        """), {"ts_version": ts_version})

        top_symbols = [
            {"symbol": r[0], "score": r[1], "rank": r[2]}
            for r in symbols_result.fetchall()
        ]

        return {
            "valid": True,
            "ts_version": ts_version,
            "status": status,
            "universe_size": universe_size,
            "global_regime": regime,
            "config_hash": config_hash,
            "top_symbols": top_symbols,
        }


def validate_universe_task(**context) -> dict[str, Any]:
    """Airflow task: validate published universe."""
    env = get_dag_env()
    setup_env(env)

    loop = get_or_create_event_loop()
    result = loop.run_until_complete(_validate_universe_async(env["DATABASE_URL"]))

    if not result["valid"]:
        logger.warning(f"Universe validation warning: {result.get('reason')}")

    logger.info(
        f"Universe validation: valid={result['valid']}, "
        f"size={result.get('universe_size')}, "
        f"regime={result.get('global_regime')}"
    )

    return result


async def _cleanup_old_data_async(database_url: str) -> dict[str, Any]:
    """Cleanup old market selection data."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from src.market_selection.config import MarketSelectionConfig
    from src.market_selection.infrastructure.persistence import (
        MarketSelectionPersistence,
    )

    engine = create_async_engine(database_url, echo=False)
    config = MarketSelectionConfig()

    async with AsyncSession(engine) as session:
        persistence = MarketSelectionPersistence(session)
        scores_deleted, universe_deleted = await persistence.cleanup_old_data(
            scores_retention_days=config.universe.scores_retention_days,
            universe_retention_days=config.universe.universe_retention_days,
        )
        await session.commit()

    return {
        "scores_deleted": scores_deleted,
        "universe_deleted": universe_deleted,
    }


async def _get_universe_symbols_async(database_url: str) -> list[str]:
    """Get symbols from current universe for features_calc_full."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    engine = create_async_engine(database_url, echo=False)

    async with AsyncSession(engine) as session:
        # Get latest published universe
        result = await session.execute(text("""
            SELECT ts_version FROM market_universe_versions
            WHERE status IN ('published', 'fallback_prev')
            ORDER BY ts_version DESC
            LIMIT 1
        """))
        row = result.fetchone()

        if not row:
            return []

        ts_version = row[0]

        # Get symbols
        symbols_result = await session.execute(text("""
            SELECT symbol FROM market_universe
            WHERE ts_version = :ts_version
            ORDER BY rank
        """), {"ts_version": ts_version})

        return [r[0] for r in symbols_result.fetchall()]


def prepare_features_calc_config(**context) -> dict[str, Any]:
    """Prepare config for features_calc DAG trigger."""
    env = get_dag_env()
    setup_env(env)

    loop = get_or_create_event_loop()
    symbols = loop.run_until_complete(_get_universe_symbols_async(env["DATABASE_URL"]))

    if not symbols:
        logger.warning("No symbols in universe, skipping features_calc trigger")
        return {"skip_trigger": True, "symbols": []}

    logger.info(f"Prepared {len(symbols)} symbols for features_calc: {symbols[:5]}...")

    # Store in XCom for TriggerDagRunOperator
    context["ti"].xcom_push(key="universe_symbols", value=symbols)

    return {
        "skip_trigger": False,
        "symbols": symbols,
        "symbols_count": len(symbols),
    }


def cleanup_old_data_task(**context) -> dict[str, Any]:
    """Airflow task: cleanup old market selection data."""
    env = get_dag_env()
    setup_env(env)

    loop = get_or_create_event_loop()
    result = loop.run_until_complete(_cleanup_old_data_async(env["DATABASE_URL"]))

    logger.info(
        f"Cleanup completed: {result['scores_deleted']} scores, "
        f"{result['universe_deleted']} universe entries deleted"
    )

    return result


# DAG definition
with DAG(
    dag_id="market_selection",
    default_args=default_args,
    description="Select trading pairs based on quality, metrics, and regime",
    schedule_interval="0 */4 * * *",  # Every 4 hours
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["market_selection", "scoring", "universe"],
    params={
        "top_n": 30,
        "force_run": False,
    },
) as dag:

    # Wait for features_calc_short to complete
    wait_for_features = ExternalTaskSensor(
        task_id="wait_for_features_calc_short",
        external_dag_id="features_calc_short",
        external_task_id=None,  # Wait for entire DAG
        mode="reschedule",
        timeout=3600,  # 1 hour
        poke_interval=60,  # Check every minute
        allowed_states=["success"],
    )

    # Run migrations (idempotent)
    run_migrations = PythonOperator(
        task_id="run_migrations",
        python_callable=run_migrations_task,
    )

    # Run pipeline
    run_pipeline = PythonOperator(
        task_id="run_pipeline",
        python_callable=run_pipeline_task,
    )

    # Validate result
    validate_universe = PythonOperator(
        task_id="validate_universe",
        python_callable=validate_universe_task,
    )

    # Cleanup old data (runs daily, not every 4 hours)
    cleanup_old_data = PythonOperator(
        task_id="cleanup_old_data",
        python_callable=cleanup_old_data_task,
    )

    # Prepare config for features_calc trigger
    prepare_trigger = PythonOperator(
        task_id="prepare_features_calc_trigger",
        python_callable=prepare_features_calc_config,
    )

    # Trigger features_calc DAG with universe symbols
    trigger_features_calc = TriggerDagRunOperator(
        task_id="trigger_features_calc",
        trigger_dag_id="features_calc",
        conf={
            "symbols": "{{ ti.xcom_pull(task_ids='prepare_features_calc_trigger', key='universe_symbols') | join(',') }}",
            "triggered_by": "market_selection",
            "ts_version": "{{ ti.xcom_pull(task_ids='run_pipeline')['ts_version'] }}",
        },
        wait_for_completion=False,  # Don't block, let it run async
        reset_dag_run=True,  # Allow re-running if already exists
    )

    # Task dependencies
    wait_for_features >> run_migrations >> run_pipeline >> validate_universe

    # After validation, prepare trigger config and trigger features_calc
    validate_universe >> prepare_trigger >> trigger_features_calc

    # Cleanup runs independently (can be scheduled separately)
    # For now, run it after validation (but it's idempotent)
    validate_universe >> cleanup_old_data
