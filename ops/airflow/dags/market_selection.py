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
import sys
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

# Add project to path for imports (same as features_calc DAG)
if "/opt/airflow/project" not in sys.path:
    sys.path.insert(0, "/opt/airflow/project")

from airflow import DAG
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sensors.external_task import ExternalTaskSensor

try:
    from airflow.operators.empty import EmptyOperator
except ImportError:
    from airflow.operators.dummy import DummyOperator as EmptyOperator

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


def _build_log_context(context: dict[str, Any]) -> str:
    """Build a compact context string for task logs."""
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


def _safe_execution_time(value: Any) -> str:
    """Format execution time safely for logging."""
    try:
        if value is None:
            return "n/a"
        return f"{float(value):.2f}s"
    except (TypeError, ValueError):
        return "n/a"


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


def setup_env(env: Mapping[str, str | None]) -> None:
    """Set environment variables."""
    for key, value in env.items():
        if value is not None:
            os.environ[key] = value

    Path("/tmp/pklpo").mkdir(parents=True, exist_ok=True)  # noqa: S108


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
    log_ctx = _build_log_context(context)
    logger.info("run_migrations start %s", log_ctx)
    env = get_dag_env()
    setup_env(env)

    try:
        loop = get_or_create_event_loop()
        result = loop.run_until_complete(_run_migrations_async(env["DATABASE_URL"]))
    except Exception:
        logger.exception("run_migrations failed %s", log_ctx)
        raise

    logger.info("run_migrations finish %s migrations_ok=%s", log_ctx, result)

    return {"migrations_ok": result}


async def _run_pipeline_async(
    database_url: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Run market selection pipeline."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from src.market_selection.application.pipeline import MarketSelectionPipeline
    from src.market_selection.config import MarketSelectionConfig

    engine = create_async_engine(database_url, echo=False)

    # Build config with overrides from params
    config = MarketSelectionConfig()
    if params.get("top_n") is not None:
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
    log_ctx = _build_log_context(context)
    logger.info("run_pipeline start %s", log_ctx)

    env = get_dag_env()
    setup_env(env)

    params = dict(context.get("params", {}))
    dag_run = context.get("dag_run")
    dag_run_conf = getattr(dag_run, "conf", None) or {}
    params.update(dag_run_conf)

    loop = get_or_create_event_loop()
    result = cast(
        "dict[str, Any]",
        loop.run_until_complete(_run_pipeline_async(env["DATABASE_URL"], params)),
    )

    if not result["success"]:
        logger.error(f"Pipeline failed: {result.get('error_message')}")
        raise RuntimeError(f"Market selection failed: {result.get('error_message')}")

    execution_time = _safe_execution_time(result.get("execution_time_seconds"))
    logger.info(
        "run_pipeline finish %s success=%s universe_size=%s regime=%s time=%s status=%s",
        log_ctx,
        result["success"],
        result["universe_size"],
        result["global_regime"],
        execution_time,
        result["status"],
    )

    return result


async def _validate_universe_async(database_url: str) -> dict[str, Any]:
    """Validate the published universe."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    engine = create_async_engine(database_url, echo=False)

    async with AsyncSession(engine) as session:
        # Check latest version
        result = await session.execute(
            text(
                """
            SELECT ts_version, status, universe_size, global_regime, config_hash
            FROM market_universe_versions
            ORDER BY ts_version DESC
            LIMIT 1
        """
            )
        )
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
        symbols_result = await session.execute(
            text(
                """
            SELECT symbol, final_score, rank
            FROM market_universe
            WHERE ts_version = :ts_version
            ORDER BY rank
            LIMIT 10
        """
            ),
            {"ts_version": ts_version},
        )

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
    log_ctx = _build_log_context(context)
    logger.info("validate_universe start %s", log_ctx)

    env = get_dag_env()
    setup_env(env)

    loop = get_or_create_event_loop()
    result = cast(
        "dict[str, Any]",
        loop.run_until_complete(_validate_universe_async(env["DATABASE_URL"])),
    )

    if not result["valid"]:
        logger.warning(f"Universe validation warning: {result.get('reason')}")

    logger.info(
        "validate_universe finish %s valid=%s size=%s regime=%s status=%s",
        log_ctx,
        result["valid"],
        result.get("universe_size"),
        result.get("global_regime"),
        result.get("status"),
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
        result = await session.execute(
            text(
                """
            SELECT ts_version FROM market_universe_versions
            WHERE status IN ('published', 'fallback_prev')
            ORDER BY ts_version DESC
            LIMIT 1
        """
            )
        )
        row = result.fetchone()

        if not row:
            return []

        ts_version = row[0]

        # Get symbols
        symbols_result = await session.execute(
            text(
                """
            SELECT symbol FROM market_universe
            WHERE ts_version = :ts_version
            ORDER BY rank
        """
            ),
            {"ts_version": ts_version},
        )

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


def branch_skip_or_trigger(**context) -> str:
    """Branch: skip features_calc trigger when universe is empty."""
    ti = context["ti"]
    result = ti.xcom_pull(task_ids="prepare_features_calc_trigger") or {}
    skip = result.get("skip_trigger", True)
    selected_branch = "skip_features_calc_trigger" if skip else "trigger_features_calc"
    logger.info(
        "branch_skip_or_trigger decision %s selected_branch=%s skip=%s symbols_count=%s",
        _build_log_context(context),
        selected_branch,
        skip,
        len(result.get("symbols", [])),
    )
    if skip:
        return "skip_features_calc_trigger"
    return "trigger_features_calc"


def cleanup_old_data_task(**context) -> dict[str, Any]:
    """Airflow task: cleanup old market selection data."""
    log_ctx = _build_log_context(context)
    logger.info("cleanup_old_data start %s", log_ctx)

    env = get_dag_env()
    setup_env(env)

    loop = get_or_create_event_loop()
    result = cast(
        "dict[str, Any]",
        loop.run_until_complete(_cleanup_old_data_async(env["DATABASE_URL"])),
    )

    logger.info(
        "cleanup_old_data finish %s scores_deleted=%s universe_deleted=%s",
        log_ctx,
        result["scores_deleted"],
        result["universe_deleted"],
    )

    return result


def branch_cleanup_daily(**context) -> str:
    """Branch: run cleanup only once per day at 00:00 schedule slot."""
    logical_date = context.get("logical_date")
    selected_branch = (
        "cleanup_old_data" if logical_date and logical_date.hour == 0 else "skip_cleanup_old_data"
    )
    logger.info(
        "branch_cleanup_daily decision %s selected_branch=%s",
        _build_log_context(context),
        selected_branch,
    )
    if logical_date and logical_date.hour == 0:
        return "cleanup_old_data"
    return "skip_cleanup_old_data"


# DAG definition
with DAG(
    dag_id="market_selection",
    default_args=default_args,
    description="Select trading pairs based on quality, metrics, and regime",
    schedule="0 */4 * * *",  # Every 4 hours
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["market_selection", "scoring", "universe"],
    params={
        "top_n": 30,
        "force_run": False,
    },
) as dag:

    # Wait for features_calc_short to complete (last task of that DAG)
    wait_for_features = ExternalTaskSensor(
        task_id="wait_for_features_calc_short",
        external_dag_id="features_calc_short",
        external_task_id="features_calc_short_validate",
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

    branch_cleanup = BranchPythonOperator(
        task_id="branch_cleanup_daily",
        python_callable=branch_cleanup_daily,
    )

    skip_cleanup_old_data = EmptyOperator(
        task_id="skip_cleanup_old_data",
    )

    # Prepare config for features_calc trigger
    prepare_trigger = PythonOperator(
        task_id="prepare_features_calc_trigger",
        python_callable=prepare_features_calc_config,
    )

    # Branch: skip trigger when universe is empty
    branch_skip_or_trigger_task = BranchPythonOperator(
        task_id="branch_skip_or_trigger",
        python_callable=branch_skip_or_trigger,
    )

    # Dummy task when universe is empty (do not trigger features_calc)
    skip_features_calc_trigger = EmptyOperator(
        task_id="skip_features_calc_trigger",
    )

    # Trigger features_calc DAG with universe symbols (only when universe non-empty)
    trigger_features_calc = TriggerDagRunOperator(
        task_id="trigger_features_calc",
        trigger_dag_id="features_calc",
        conf={
            "symbols": "{{ (ti.xcom_pull(task_ids='prepare_features_calc_trigger', key='universe_symbols') or []) | join(',') }}",
            "triggered_by": "market_selection",
            "ts_version": "{{ (ti.xcom_pull(task_ids='run_pipeline') or {}).get('ts_version', '') }}",
        },
        wait_for_completion=False,  # Don't block, let it run async
        reset_dag_run=True,  # Allow re-running if already exists
    )

    # Task dependencies
    wait_for_features >> run_migrations >> run_pipeline >> validate_universe

    # After validation, prepare trigger config; branch on empty universe
    validate_universe >> prepare_trigger >> branch_skip_or_trigger_task
    branch_skip_or_trigger_task >> [skip_features_calc_trigger, trigger_features_calc]

    # Cleanup runs once a day (00:00 slot) to reduce background load
    validate_universe >> branch_cleanup
    branch_cleanup >> [cleanup_old_data, skip_cleanup_old_data]
