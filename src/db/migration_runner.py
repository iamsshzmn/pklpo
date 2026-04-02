import logging
import time

from sqlalchemy import exc as sa_exc, text

from src.db.migration_registry import get_migrations
from src.db.migration_reports import (
    generate_migration_report,
    generate_system_health_report,
)
from src.db.schema_validation import validate_schema_expectations
from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


def _is_missing_migration_logs_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "migration_logs" in message and "does not exist" in message


async def _drop_broken_migration_logging_trigger(session) -> None:
    await session.execute(
        text("DROP TRIGGER IF EXISTS trigger_log_migration_changes ON schema_migrations")
    )
    await session.commit()


async def _object_exists(query: str, params: dict[str, object]) -> bool:
    async with get_db_session() as session:
        res = await session.execute(text(query), params)
        return bool(res.scalar())


async def _table_exists(table_name: str) -> bool:
    return await _object_exists(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table_name
        )
        """,
        {"table_name": table_name},
    )


async def _partitioned_table_exists(table_name: str) -> bool:
    return await _object_exists(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_partitioned_table pt
            JOIN pg_class c ON c.oid = pt.partrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = :table_name
        )
        """,
        {"table_name": table_name},
    )


async def _index_exists(index_name: str) -> bool:
    return await _object_exists(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public' AND indexname = :index_name
        )
        """,
        {"index_name": index_name},
    )


async def _function_exists(function_name: str) -> bool:
    return await _object_exists(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND p.proname = :function_name
        )
        """,
        {"function_name": function_name},
    )


async def _trigger_exists(trigger_name: str) -> bool:
    return await _object_exists(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.triggers
            WHERE trigger_schema = 'public' AND trigger_name = :trigger_name
        )
        """,
        {"trigger_name": trigger_name},
    )


async def _matview_exists(view_name: str) -> bool:
    return await _object_exists(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_matviews
            WHERE schemaname = 'public' AND matviewname = :view_name
        )
        """,
        {"view_name": view_name},
    )


async def _column_is_wide_numeric(table_name: str, column_name: str) -> bool:
    async with get_db_session() as session:
        res = await session.execute(
            text(
                """
                SELECT data_type, numeric_precision
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        )
        row = res.fetchone()
        if row is None:
            return False
        data_type, numeric_precision = row
        return data_type == "numeric" and (
            numeric_precision is None or numeric_precision >= 38
        )


async def _column_is_timestamptz(table_name: str, column_name: str) -> bool:
    async with get_db_session() as session:
        res = await session.execute(
            text(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        )
        row = res.fetchone()
        return bool(row and row[0] == "timestamp with time zone")


async def _is_effectively_applied(migration_id: str) -> bool:
    detectors: dict[str, callable] = {
        "150_data_cleanup": lambda: _index_exists("idx_ohlcv_p_symbol_timeframe"),
        "160_materialized_views": lambda: _matview_exists("mv_symbol_stats"),
        "170_monitoring_metrics": lambda: _table_exists("migration_logs"),
        "180_swap_ohlcv": lambda: _table_exists("swap_ohlcv_p"),
        "190_features_table": lambda: _table_exists("features"),
        "210_data_retention": lambda: _trigger_exists("trigger_cleanup_swap_data"),
        "230_expand_indicators_precision": lambda: _column_is_wide_numeric(
            "indicators_p", "obv"
        ),
        "240_combination_features": lambda: _table_exists("combination_features"),
        "250_market_data_ext": lambda: _table_exists("market_data_ext"),
        "260_market_selection": lambda: _table_exists("market_scores_tf"),
        "270_swap_ohlcv_partitioned": lambda: _partitioned_table_exists(
            "swap_ohlcv_p"
        ),
        "290_swap_ohlcv_timestamptz": lambda: _swap_ohlcv_timestamp_columns_are_timestamptz(),
    }
    detector = detectors.get(migration_id)
    if detector is None:
        return False
    return await detector()


async def _swap_ohlcv_timestamp_columns_are_timestamptz() -> bool:
    fetched_at_ok = await _column_is_timestamptz("swap_ohlcv_p", "fetched_at")
    created_at_ok = await _column_is_timestamptz("swap_ohlcv_p", "created_at")
    return fetched_at_ok and created_at_ok


async def reconcile_applied_migrations() -> list[str]:
    reconciled: list[str] = []
    for migration in get_migrations():
        if migration.id == "000_base_migrations_table":
            continue
        if await _already_applied(migration.id):
            continue
        if not await _is_effectively_applied(migration.id):
            continue

        started = time.time()
        await _record_status(migration.id, migration.name, "applied", started, attempt=0)
        reconciled.append(migration.id)
        logger.info(
            "reconciled migration record for %s (%s)",
            migration.id,
            migration.name,
        )
    return reconciled


async def _already_applied(migration_id: str) -> bool:
    async with get_db_session() as session:
        q = text(
            "SELECT 1 FROM schema_migrations WHERE id = :id AND status = 'applied' LIMIT 1"
        )
        res = await session.execute(q, {"id": migration_id})
        return res.scalar() is not None


async def _record_status(
    migration_id: str,
    name: str,
    status: str,
    started_at: float,
    error: str | None = None,
    attempt: int = 1,
) -> None:
    duration_ms = int((time.time() - started_at) * 1000)
    async with get_db_session() as session:
        q = text(
            """
            INSERT INTO schema_migrations(id, name, applied_at, duration_ms, status, attempt, error)
            VALUES (:id, :name, :applied_at, :duration_ms, :status, :attempt, :error)
            ON CONFLICT (id) DO UPDATE SET
                applied_at = EXCLUDED.applied_at,
                duration_ms = EXCLUDED.duration_ms,
                status = EXCLUDED.status,
                attempt = schema_migrations.attempt + 1,
                error = EXCLUDED.error
            """
        )
        params = {
            "id": migration_id,
            "name": name,
            "applied_at": int(time.time()),
            "duration_ms": duration_ms,
            "status": status,
            "attempt": attempt,
            "error": error,
        }
        try:
            await session.execute(q, params)
            await session.commit()
        except sa_exc.DBAPIError as exc:
            if not _is_missing_migration_logs_error(exc):
                raise
            logger.warning(
                "schema_migrations trigger references missing migration_logs; "
                "dropping trigger and retrying status write"
            )
            await session.rollback()
            await _drop_broken_migration_logging_trigger(session)
            await session.execute(q, params)
            await session.commit()


async def run_all(dry_run: bool = False) -> None:
    # Pre-validation
    try:
        await validate_schema_expectations()
    except Exception as e:
        logger.warning(f"⚠️ Pre-validation skipped: {e}")

    migrations = get_migrations()
    for m in migrations:
        if m.id != "000_base_migrations_table":
            # ensure table exists before we start using it
            from src.db.migrations.migrate_create_schema_migrations import (
                migrate_create_schema_migrations,
            )

            await migrate_create_schema_migrations()
            break

    reconciled = await reconcile_applied_migrations()
    if reconciled:
        logger.info("reconciled applied migrations: %s", ", ".join(reconciled))

    for m in migrations:
        if m.id != "000_base_migrations_table" and await _already_applied(m.id):
            logger.info(f"Skipped migration {m.id} ({m.name}) — already applied")
            continue
        logger.info(f"Migration {m.id}: {m.name}")
        started = time.time()
        if dry_run:
            await _record_status(
                m.id, m.name, "planned", started, error=None, attempt=0
            )
            logger.info(f"DRY-RUN: {m.id} ({m.name}) planned")
            continue
        try:
            await m.func()
            duration_ms = int((time.time() - started) * 1000)
            await _record_status(m.id, m.name, "applied", started)
            logger.info(f"Applied {m.id} ({m.name})")

            # Generate migration report
            try:
                report = await generate_migration_report(
                    m.id, duration_ms, save_file=True
                )
                report.print_summary()
            except Exception as report_error:
                logger.warning(f"Failed to generate report: {report_error}")

        except Exception as e:
            await _record_status(m.id, m.name, "failed", started, error=str(e))
            logger.error(f"Migration error {m.id}: {e}")
            raise

    # Post-validation
    try:
        await validate_schema_expectations()
    except Exception as e:
        logger.warning(f"Post-validation skipped: {e}")

    # Generate system health report
    try:
        health_report = await generate_system_health_report()
        if health_report.get("overall_status") == "healthy":
            logger.info("System is healthy")
        else:
            logger.warning("System needs attention")
    except Exception as e:
        logger.warning(f"Failed to generate health report: {e}")
