import asyncio
import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, TimeoutError

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def set_default_timeouts() -> None:
    """
    Устанавливает дефолтные timeout'ы для операций.
    """
    logger.info("🔄 Устанавливаем дефолтные timeout'ы...")

    async with get_db_session() as session:
        # Устанавливаем statement_timeout (30 секунд)
        stmt_timeout_q = text("SET statement_timeout = '30s';")
        await session.execute(stmt_timeout_q)

        # Устанавливаем lock_timeout (10 секунд)
        lock_timeout_q = text("SET lock_timeout = '10s';")
        await session.execute(lock_timeout_q)

        # Устанавливаем idle_in_transaction_session_timeout (5 минут)
        idle_timeout_q = text("SET idle_in_transaction_session_timeout = '5min';")
        await session.execute(idle_timeout_q)

        logger.info("✅ Timeout'ы установлены")


async def create_backup_utilities() -> None:
    """
    Создает функции для создания бэкапов критичных таблиц.
    """
    logger.info("🔄 Создаем функции для бэкапов...")

    async with get_db_session() as session:
        # Функция для создания снапшота таблицы
        backup_function_q = text(
            """
            CREATE OR REPLACE FUNCTION create_table_backup(
                table_name text,
                backup_suffix text DEFAULT NULL
            ) RETURNS text AS $$
            DECLARE
                backup_table_name text;
                backup_sql text;
            BEGIN
                -- Генерируем имя бэкап таблицы
                IF backup_suffix IS NULL THEN
                    backup_suffix := to_char(now(), 'YYYYMMDD_HH24MISS');
                END IF;
                backup_table_name := table_name || '_backup_' || backup_suffix;

                -- Создаем бэкап
                backup_sql := 'CREATE TABLE ' || backup_table_name || ' AS SELECT * FROM ' || table_name;
                EXECUTE backup_sql;

                -- Создаем индексы на бэкапе (адаптивно)
                BEGIN
                    -- Пытаемся создать составной индекс для таблиц с timeframe
                    EXECUTE 'CREATE INDEX IF NOT EXISTS idx_' || backup_table_name || '_symbol_timeframe_ts
                            ON ' || backup_table_name || '(symbol, timeframe, timestamp)';
                EXCEPTION
                    WHEN undefined_column THEN
                        BEGIN
                            -- Для таблиц без timeframe, но с timestamp
                            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_' || backup_table_name || '_symbol_ts
                                    ON ' || backup_table_name || '(symbol, timestamp)';
                        EXCEPTION
                            WHEN undefined_column THEN
                                -- Для таблиц только с symbol (например, instruments)
                                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_' || backup_table_name || '_symbol
                                        ON ' || backup_table_name || '(symbol)';
                        END;
                END;

                RETURN backup_table_name;
            END;
            $$ LANGUAGE plpgsql;
        """
        )

        await session.execute(backup_function_q)
        logger.info("✅ Функция create_table_backup создана")

        # Функция для очистки старых бэкапов
        cleanup_function_q = text(
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

                    -- Извлекаем дату из имени таблицы
                    IF to_timestamp(
                        substring(backup_table from table_name || '_backup_([0-9]{8}_[0-9]{6})$'),
                        'YYYYMMDD_HH24MISS'
                    ) < now() - interval '1 day' * days_to_keep THEN
                        EXECUTE 'DROP TABLE IF EXISTS ' || backup_table;
                        dropped_count := dropped_count + 1;
                        RAISE NOTICE 'Dropped old backup: %', backup_table;
                    END IF;
                END LOOP;

                RETURN dropped_count;
            END;
            $$ LANGUAGE plpgsql;
        """
        )

        await session.execute(cleanup_function_q)
        logger.info("✅ Функция cleanup_old_backups создана")

        await session.commit()


async def create_migration_control_functions() -> None:
    """
    Создает функции для контроля миграций по диапазону.
    """
    logger.info("🔄 Создаем функции контроля миграций...")

    async with get_db_session() as session:
        # Функция для получения списка миграций в диапазоне
        migration_range_function_q = text(
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

        await session.execute(migration_range_function_q)
        logger.info("✅ Функция get_migrations_in_range создана")

        # Функция для проверки готовности к миграции
        readiness_check_function_q = text(
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
                -- Проверяем существование критичных таблиц
                SELECT COUNT(*) INTO table_count
                FROM information_schema.tables
                WHERE table_name IN ('ohlcv_p', 'indicators_p', 'instruments');

                RETURN QUERY SELECT
                    'Critical tables exist'::text,
                    CASE WHEN table_count >= 3 THEN 'OK' ELSE 'FAIL' END::text,
                    'Found ' || table_count || ' critical tables'::text;

                -- Проверяем индексы
                SELECT COUNT(*) INTO index_count
                FROM pg_indexes
                WHERE tablename IN ('ohlcv_p', 'indicators_p');

                RETURN QUERY SELECT
                    'Indexes exist'::text,
                    CASE WHEN index_count > 0 THEN 'OK' ELSE 'WARNING' END::text,
                    'Found ' || index_count || ' indexes'::text;

                -- Проверяем ограничения
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

        await session.execute(readiness_check_function_q)
        logger.info("✅ Функция check_migration_readiness создана")

        await session.commit()


async def create_monitoring_views() -> None:
    """
    Создает VIEW для мониторинга состояния базы данных.
    """
    logger.info("🔄 Создаем VIEW для мониторинга...")

    async with get_db_session() as session:
        # VIEW для мониторинга размера таблиц
        table_size_view_q = text(
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

        await session.execute(table_size_view_q)
        logger.info("✅ VIEW table_size_monitoring создан")

        # VIEW для мониторинга индексов
        index_monitoring_view_q = text(
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

        await session.execute(index_monitoring_view_q)
        logger.info("✅ VIEW index_monitoring создан")

        # VIEW для мониторинга партиций
        partition_monitoring_view_q = text(
            """
            CREATE OR REPLACE VIEW partition_monitoring AS
            SELECT
                schemaname,
                tablename,
                partition_name,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||partition_name)) as size_pretty,
                pg_total_relation_size(schemaname||'.'||partition_name) as size_bytes,
                pg_get_expr(relpartbound, rel.oid) as partition_expression
            FROM pg_partitioned_table pt
            JOIN pg_class pc ON pt.partrelid = pc.oid
            JOIN pg_class rel ON rel.relispartition = true AND rel.relpartbound IS NOT NULL
            WHERE pc.relname IN ('ohlcv_p', 'indicators_p')
            ORDER BY pg_total_relation_size(schemaname||'.'||partition_name) DESC;
        """
        )

        try:
            await session.execute(partition_monitoring_view_q)
            logger.info("✅ VIEW partition_monitoring создан")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось создать partition_monitoring: {e}")

        await session.commit()


async def retry_with_backoff(
    func: Callable[[], Any], max_retries: int = 3, base_delay: float = 1.0
) -> Any:
    """
    Выполняет функцию с retry и exponential backoff.
    """
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except (OperationalError, TimeoutError) as e:
            if attempt == max_retries:
                logger.error(f"❌ Максимальное количество попыток достигнуто: {e}")
                raise

            delay = base_delay * (2**attempt)
            logger.warning(
                f"⚠️ Попытка {attempt + 1} не удалась, повтор через {delay}s: {e}"
            )
            await asyncio.sleep(delay)
    return None


async def test_operational_reliability() -> None:
    """
    Тестирует операционную надежность.
    """
    logger.info("🧪 Тестируем операционную надежность...")

    async with get_db_session() as session:
        # Тест 1: Проверяем timeout'ы
        try:
            # Пытаемся выполнить долгую операцию
            long_query = text("SELECT pg_sleep(35);")  # Больше чем statement_timeout
            await session.execute(long_query)
            logger.warning("⚠️ Timeout не сработал как ожидалось")
        except Exception as e:
            if "timeout" in str(e).lower():
                logger.info("✅ Timeout работает корректно")
            else:
                logger.warning(f"⚠️ Неожиданная ошибка при тесте timeout: {e}")

        # Тест 2: Проверяем функции бэкапа
        try:
            backup_result = await session.execute(
                text("SELECT create_table_backup('instruments', 'test');")
            )
            backup_table = backup_result.scalar()
            logger.info(f"✅ Тестовый бэкап создан: {backup_table}")

            # Удаляем тестовый бэкап
            await session.execute(text(f"DROP TABLE IF EXISTS {backup_table};"))
            logger.info("✅ Тестовый бэкап удален")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при тесте бэкапа: {e}")

        # Тест 3: Проверяем мониторинг
        try:
            size_result = await session.execute(
                text("SELECT COUNT(*) FROM table_size_monitoring;")
            )
            size_count = size_result.scalar()
            logger.info(f"✅ Мониторинг размера таблиц работает: {size_count} записей")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при тесте мониторинга: {e}")

        await session.commit()


async def run_operational_reliability_migration() -> None:
    """
    Основная функция для выполнения миграции операционной надежности.
    """
    logger.info("🚀 Начинаем миграцию операционной надежности...")

    try:
        # Устанавливаем timeout'ы
        await set_default_timeouts()

        # Создаем утилиты для бэкапов
        await create_backup_utilities()

        # Создаем функции контроля миграций
        await create_migration_control_functions()

        # Создаем VIEW для мониторинга
        await create_monitoring_views()

        # Тестируем операционную надежность
        await test_operational_reliability()

        logger.info("✅ Миграция операционной надежности завершена успешно!")

    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении миграции операционной надежности: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_operational_reliability_migration())
