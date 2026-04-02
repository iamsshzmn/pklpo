import asyncio
import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, TimeoutError

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def set_default_timeouts() -> None:
    logger.info("Setting default DB timeouts...")
    async with get_db_session() as session:
        await session.execute(text("SET statement_timeout = '30s';"))
        await session.execute(text("SET lock_timeout = '10s';"))
        await session.execute(text("SET idle_in_transaction_session_timeout = '5min';"))
        logger.info("Default DB timeouts configured")


async def create_backup_utilities() -> None:
    logger.info("Creating backup utility functions...")
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION create_table_backup(
                    table_name text,
                    backup_suffix text DEFAULT NULL
                ) RETURNS text AS $$
                DECLARE
                    backup_table_name text;
                    backup_sql text;
                BEGIN
                    IF backup_suffix IS NULL THEN
                        backup_suffix := to_char(now(), 'YYYYMMDD_HH24MISS');
                    END IF;
                    backup_table_name := table_name || '_backup_' || backup_suffix;

                    backup_sql := 'CREATE TABLE ' || backup_table_name || ' AS SELECT * FROM ' || table_name;
                    EXECUTE backup_sql;

                    BEGIN
                        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_' || backup_table_name || '_symbol_timeframe_ts
                                ON ' || backup_table_name || '(symbol, timeframe, timestamp)';
                    EXCEPTION
                        WHEN undefined_column THEN
                            BEGIN
                                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_' || backup_table_name || '_symbol_ts
                                        ON ' || backup_table_name || '(symbol, timestamp)';
                            EXCEPTION
                                WHEN undefined_column THEN
                                    EXECUTE 'CREATE INDEX IF NOT EXISTS idx_' || backup_table_name || '_symbol
                                            ON ' || backup_table_name || '(symbol)';
                            END;
                    END;

                    RETURN backup_table_name;
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        await session.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION cleanup_old_backups(
                    table_name text,
                    days_to_keep integer DEFAULT 7
                ) RETURNS integer AS $$
                DECLARE
                    backup_table text;
                    dropped_count integer := 0;
                    backup_record record;
                BEGIN
                    FOR backup_record IN
                        SELECT tablename
                        FROM pg_tables
                        WHERE tablename LIKE table_name || '_backup_%'
                          AND tablename ~ table_name || '_backup_[0-9]{8}_[0-9]{6}$'
                    LOOP
                        backup_table := backup_record.tablename;
                        IF to_timestamp(
                            substring(backup_table from table_name || '_backup_([0-9]{8}_[0-9]{6})$'),
                            'YYYYMMDD_HH24MISS'
                        ) < now() - interval '1 day' * days_to_keep THEN
                            EXECUTE 'DROP TABLE IF EXISTS ' || backup_table;
                            dropped_count := dropped_count + 1;
                        END IF;
                    END LOOP;

                    RETURN dropped_count;
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        await session.commit()
        logger.info("Backup utility functions created")


async def create_migration_control_functions() -> None:
    logger.info("Creating migration control functions...")
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION get_migrations_in_range(
                    from_migration text DEFAULT NULL,
                    to_migration text DEFAULT NULL
                ) RETURNS TABLE(
                    migration_id text,
                    migration_name text,
                    applied_at timestamp,
                    status text
                ) AS $$
                BEGIN
                    RETURN QUERY
                    SELECT
                        sm.migration_id,
                        sm.migration_name,
                        sm.applied_at,
                        sm.status
                    FROM schema_migrations sm
                    WHERE (from_migration IS NULL OR sm.migration_id >= from_migration)
                      AND (to_migration IS NULL OR sm.migration_id <= to_migration)
                    ORDER BY sm.migration_id;
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        await session.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION check_migration_readiness(
                    migration_id text
                ) RETURNS TABLE(
                    check_name text,
                    status text,
                    details text
                ) AS $$
                DECLARE
                    table_count integer;
                    index_count integer;
                    constraint_count integer;
                BEGIN
                    SELECT COUNT(*) INTO table_count
                    FROM information_schema.tables
                    WHERE table_name IN ('ohlcv_p', 'indicators_p', 'instruments');

                    RETURN QUERY SELECT
                        'Critical tables exist'::text,
                        CASE WHEN table_count >= 3 THEN 'OK' ELSE 'FAIL' END::text,
                        'Found ' || table_count || ' critical tables'::text;

                    SELECT COUNT(*) INTO index_count
                    FROM pg_indexes
                    WHERE tablename IN ('ohlcv_p', 'indicators_p');

                    RETURN QUERY SELECT
                        'Indexes exist'::text,
                        CASE WHEN index_count > 0 THEN 'OK' ELSE 'WARNING' END::text,
                        'Found ' || index_count || ' indexes'::text;

                    SELECT COUNT(*) INTO constraint_count
                    FROM information_schema.table_constraints
                    WHERE table_name IN ('ohlcv_p', 'indicators_p', 'instruments');

                    RETURN QUERY SELECT
                        'Constraints exist'::text,
                        CASE WHEN constraint_count > 0 THEN 'OK' ELSE 'WARNING' END::text,
                        'Found ' || constraint_count || ' constraints'::text;
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        await session.commit()
        logger.info("Migration control functions created")


async def create_monitoring_views() -> None:
    logger.info("Creating monitoring views...")
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                CREATE OR REPLACE VIEW table_size_monitoring AS
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size_pretty,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes,
                    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size_pretty,
                    pg_relation_size(schemaname||'.'||tablename) as table_size_bytes
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
                """
            )
        )
        await session.execute(
            text(
                """
                CREATE OR REPLACE VIEW index_monitoring AS
                SELECT
                    schemaname,
                    relname as tablename,
                    indexrelname as indexname,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size_pretty,
                    pg_relation_size(indexrelid) as index_size_bytes,
                    idx_scan as scans,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                ORDER BY pg_relation_size(indexrelid) DESC;
                """
            )
        )
        await session.execute(
            text(
                """
                CREATE OR REPLACE VIEW partition_monitoring AS
                SELECT
                    parent_ns.nspname as schemaname,
                    parent.relname as tablename,
                    child.relname as partition_name,
                    pg_size_pretty(pg_total_relation_size(child.oid)) as size_pretty,
                    pg_total_relation_size(child.oid) as size_bytes,
                    pg_get_expr(child.relpartbound, child.oid) as partition_expression
                FROM pg_partitioned_table pt
                JOIN pg_class parent ON pt.partrelid = parent.oid
                JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
                JOIN pg_inherits inh ON inh.inhparent = parent.oid
                JOIN pg_class child ON child.oid = inh.inhrelid
                WHERE parent_ns.nspname = 'public'
                  AND parent.relname IN ('ohlcv_p', 'indicators_p', 'swap_ohlcv_p')
                ORDER BY pg_total_relation_size(child.oid) DESC;
                """
            )
        )
        await session.commit()
        logger.info("Monitoring views created")


async def retry_with_backoff(
    func: Callable[[], Any], max_retries: int = 3, base_delay: float = 1.0
) -> Any:
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except (OperationalError, TimeoutError) as e:
            if attempt == max_retries:
                logger.error("Maximum retry count reached: %s", e)
                raise
            delay = base_delay * (2**attempt)
            logger.warning("Retry %s in %ss after error: %s", attempt + 1, delay, e)
            await asyncio.sleep(delay)
    return None


async def test_operational_reliability() -> None:
    logger.info("Running lightweight operational reliability checks...")

    async with get_db_session() as session:
        try:
            await session.execute(text("SET statement_timeout = '1s';"))
            await session.execute(text("SELECT pg_sleep(2);"))
            logger.warning("statement_timeout test did not time out as expected")
        except Exception as e:
            if "timeout" in str(e).lower():
                logger.info("statement_timeout check passed")
            else:
                logger.warning("Unexpected timeout test error: %s", e)
            await session.rollback()

    async with get_db_session() as session:
        try:
            backup_result = await session.execute(
                text("SELECT create_table_backup('instruments', 'test');")
            )
            backup_table = backup_result.scalar()
            await session.execute(text(f"DROP TABLE IF EXISTS {backup_table};"))
            await session.commit()
            logger.info("backup utility check passed")
        except Exception as e:
            await session.rollback()
            logger.warning("Backup utility check failed: %s", e)

    async with get_db_session() as session:
        try:
            size_result = await session.execute(
                text("SELECT COUNT(*) FROM table_size_monitoring;")
            )
            logger.info("table_size_monitoring rows: %s", size_result.scalar())
        except Exception as e:
            await session.rollback()
            logger.warning("Monitoring view check failed: %s", e)


async def run_operational_reliability_migration() -> None:
    logger.info("Starting operational reliability migration...")
    try:
        await set_default_timeouts()
        await create_backup_utilities()
        await create_migration_control_functions()
        await create_monitoring_views()
        await test_operational_reliability()
        logger.info("Operational reliability migration completed")
    except Exception as e:
        logger.error("Operational reliability migration failed: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(run_operational_reliability_migration())
