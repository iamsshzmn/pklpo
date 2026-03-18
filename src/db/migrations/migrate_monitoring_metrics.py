#!/usr/bin/env python3
"""
Миграция для системы мониторинга и метрик.
Создает логи по длительности/блокировкам, экспорт метрик, алерты.
"""

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_monitoring_metrics() -> None:
    """
    Создает систему мониторинга и метрик.
    """
    logger.info("📊 Создаем систему мониторинга и метрик...")

    async with get_db_session() as session:
        try:
            # 1. Таблица для логов миграций
            logger.info("🔄 Создаем таблицу логов миграций...")
            migration_logs_q = text(
                """
                CREATE TABLE IF NOT EXISTS migration_logs (
                    id SERIAL PRIMARY KEY,
                    migration_id VARCHAR(50) NOT NULL,
                    operation VARCHAR(20) NOT NULL, -- 'start', 'success', 'error'
                    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMP,
                    duration_ms INTEGER,
                    rows_affected INTEGER,
                    error_message TEXT,
                    additional_info JSONB
                );
            """
            )
            await session.execute(migration_logs_q)
            await session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_migration_logs_migration_id ON migration_logs (migration_id);"
                )
            )
            await session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_migration_logs_started_at ON migration_logs (started_at);"
                )
            )
            await session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_migration_logs_operation ON migration_logs (operation);"
                )
            )
            logger.info("✅ Таблица логов миграций создана")

            # 2. Таблица для логов блокировок
            logger.info("🔄 Создаем таблицу логов блокировок...")
            lock_logs_q = text(
                """
                CREATE TABLE IF NOT EXISTS lock_logs (
                    id SERIAL PRIMARY KEY,
                    detected_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    lock_type VARCHAR(50),
                    table_name VARCHAR(100),
                    lock_mode VARCHAR(20),
                    granted BOOLEAN,
                    duration_ms INTEGER,
                    query_text TEXT,
                    process_id INTEGER,
                    session_id INTEGER
                );
            """
            )
            await session.execute(lock_logs_q)
            await session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_lock_logs_detected_at ON lock_logs (detected_at);"
                )
            )
            await session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_lock_logs_granted ON lock_logs (granted);"
                )
            )
            await session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_lock_logs_duration ON lock_logs (duration_ms);"
                )
            )
            logger.info("✅ Таблица логов блокировок создана")

            # 3. Таблица для метрик производительности
            logger.info("🔄 Создаем таблицу метрик производительности...")
            performance_metrics_q = text(
                """
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id SERIAL PRIMARY KEY,
                    collected_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    metric_name VARCHAR(100) NOT NULL,
                    metric_value NUMERIC(15, 4),
                    metric_unit VARCHAR(20),
                    tags JSONB,
                    description TEXT
                );
            """
            )
            await session.execute(performance_metrics_q)
            await session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_performance_metrics_collected_at ON performance_metrics (collected_at);"
                )
            )
            await session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_performance_metrics_name ON performance_metrics (metric_name);"
                )
            )
            await session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_performance_metrics_tags ON performance_metrics USING GIN (tags);"
                )
            )
            logger.info("✅ Таблица метрик производительности создана")

            # 4. Таблица для алертов
            logger.info("🔄 Создаем таблицу алертов...")
            alerts_q = text(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    alert_type VARCHAR(50) NOT NULL, -- 'migration_failed', 'long_lock', 'high_memory', etc.
                    severity VARCHAR(20) NOT NULL, -- 'info', 'warning', 'error', 'critical'
                    title VARCHAR(200) NOT NULL,
                    message TEXT,
                    resolved_at TIMESTAMP,
                    resolved_by VARCHAR(100),
                    metadata JSONB
                );
            """
            )
            await session.execute(alerts_q)
            await session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts (created_at);"
                )
            )
            await session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts (alert_type);"
                )
            )
            await session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts (severity);"
                )
            )
            await session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts (resolved_at);"
                )
            )
            logger.info("✅ Таблица алертов создана")

            # 5. Функция для сбора метрик
            logger.info("🔄 Создаем функцию сбора метрик...")
            collect_metrics_q = text(
                """
                CREATE OR REPLACE FUNCTION collect_performance_metrics()
                RETURNS void AS $$
                DECLARE
                    table_size BIGINT;
                    index_size BIGINT;
                    active_connections INTEGER;
                    cache_hit_ratio NUMERIC;
                    slow_queries INTEGER;
                BEGIN
                    -- Размер таблиц
                    SELECT pg_total_relation_size('ohlcv_p') + pg_total_relation_size('indicators_p')
                    INTO table_size;

                    INSERT INTO performance_metrics (metric_name, metric_value, metric_unit, description)
                    VALUES ('table_size_bytes', table_size, 'bytes', 'Total size of main tables');

                    -- Размер индексов
                    SELECT COALESCE(SUM(pg_relation_size(indexrelid)), 0)
                    FROM pg_stat_user_indexes
                    WHERE schemaname = 'public' AND tablename IN ('ohlcv_p', 'indicators_p')
                    INTO index_size;

                    INSERT INTO performance_metrics (metric_name, metric_value, metric_unit, description)
                    VALUES ('index_size_bytes', index_size, 'bytes', 'Total size of indexes');

                    -- Активные подключения
                    SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active'
                    INTO active_connections;

                    INSERT INTO performance_metrics (metric_name, metric_value, metric_unit, description)
                    VALUES ('active_connections', active_connections, 'count', 'Number of active connections');

                    -- Cache hit ratio
                    SELECT
                        CASE
                            WHEN (heap_blks_hit + heap_blks_read) > 0
                            THEN (heap_blks_hit::NUMERIC / (heap_blks_hit + heap_blks_read)) * 100
                            ELSE 0
                        END
                    FROM pg_statio_user_tables
                    WHERE relname = 'ohlcv_p'
                    INTO cache_hit_ratio;

                    INSERT INTO performance_metrics (metric_name, metric_value, metric_unit, description)
                    VALUES ('cache_hit_ratio', cache_hit_ratio, 'percent', 'Cache hit ratio for main tables');

                    -- Медленные запросы (если pg_stat_statements доступен)
                    BEGIN
                        SELECT COUNT(*)
                        FROM pg_stat_statements
                        WHERE mean_time > 1000
                        INTO slow_queries;

                        INSERT INTO performance_metrics (metric_name, metric_value, metric_unit, description)
                        VALUES ('slow_queries_count', slow_queries, 'count', 'Number of queries with mean time > 1s');
                    EXCEPTION
                        WHEN undefined_table THEN
                            -- pg_stat_statements не установлен
                            NULL;
                    END;
                END;
                $$ LANGUAGE plpgsql;
            """
            )
            await session.execute(collect_metrics_q)
            logger.info("✅ Функция сбора метрик создана")

            # 6. Функция для мониторинга блокировок
            logger.info("🔄 Создаем функцию мониторинга блокировок...")
            monitor_locks_q = text(
                """
                CREATE OR REPLACE FUNCTION monitor_locks()
                RETURNS void AS $$
                DECLARE
                    lock_record RECORD;
                    lock_duration INTEGER;
                BEGIN
                    FOR lock_record IN
                        SELECT
                            l.locktype,
                            l.database,
                            l.relation::regclass as table_name,
                            l.mode,
                            l.granted,
                            l.pid,
                            l.virtualtransaction as session_id,
                            EXTRACT(EPOCH FROM (NOW() - a.query_start)) * 1000 as duration_ms,
                            a.query as query_text
                        FROM pg_locks l
                        LEFT JOIN pg_stat_activity a ON l.pid = a.pid
                        WHERE l.database = (SELECT oid FROM pg_database WHERE datname = current_database())
                        AND l.granted = false
                        AND EXTRACT(EPOCH FROM (NOW() - a.query_start)) > 5  -- Блокировки дольше 5 секунд
                    LOOP
                        INSERT INTO lock_logs (
                            lock_type, table_name, lock_mode, granted,
                            duration_ms, query_text, process_id, session_id
                        ) VALUES (
                            lock_record.locktype::VARCHAR,
                            lock_record.table_name::VARCHAR,
                            lock_record.mode::VARCHAR,
                            lock_record.granted,
                            lock_record.duration_ms::INTEGER,
                            lock_record.query_text,
                            lock_record.pid,
                            lock_record.session_id
                        );

                        -- Создаем алерт для длительных блокировок
                        IF lock_record.duration_ms > 30000 THEN  -- 30 секунд
                            INSERT INTO alerts (
                                alert_type, severity, title, message, metadata
                            ) VALUES (
                                'long_lock', 'warning',
                                'Длительная блокировка обнаружена',
                                'Блокировка длится более 30 секунд',
                                jsonb_build_object(
                                    'table_name', lock_record.table_name,
                                    'duration_ms', lock_record.duration_ms,
                                    'process_id', lock_record.pid
                                )
                            );
                        END IF;
                    END LOOP;
                END;
                $$ LANGUAGE plpgsql;
            """
            )
            await session.execute(monitor_locks_q)
            logger.info("✅ Функция мониторинга блокировок создана")

            # 7. Функция для создания алертов о неудачных миграциях
            logger.info("🔄 Создаем функцию алертов о миграциях...")
            migration_alerts_q = text(
                """
                CREATE OR REPLACE FUNCTION create_migration_alert(
                    migration_id VARCHAR,
                    error_message TEXT,
                    duration_ms INTEGER DEFAULT NULL
                )
                RETURNS void AS $$
                BEGIN
                    INSERT INTO alerts (
                        alert_type, severity, title, message, metadata
                    ) VALUES (
                        'migration_failed', 'error',
                        'Миграция завершилась с ошибкой',
                        error_message,
                        jsonb_build_object(
                            'migration_id', migration_id,
                            'duration_ms', duration_ms,
                            'failed_at', NOW()
                        )
                    );
                END;
                $$ LANGUAGE plpgsql;
            """
            )
            await session.execute(migration_alerts_q)
            logger.info("✅ Функция алертов о миграциях создана")

            # 8. Представление для Prometheus-совместимых метрик
            logger.info("🔄 Создаем представление для Prometheus метрик...")
            prometheus_metrics_q = text(
                """
                CREATE OR REPLACE VIEW prometheus_metrics AS
                SELECT
                    'db_migration_duration_seconds' as metric_name,
                    id as labels,
                    duration_ms / 1000.0 as value,
                    NOW() as timestamp
                FROM schema_migrations
                WHERE status = 'applied' AND duration_ms IS NOT NULL

                UNION ALL

                SELECT
                    'db_table_size_bytes' as metric_name,
                    tablename as labels,
                    pg_total_relation_size(schemaname||'.'||tablename) as value,
                    NOW() as timestamp
                FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename IN ('ohlcv_p', 'indicators_p', 'instruments')

                UNION ALL

                SELECT
                    'db_active_connections' as metric_name,
                    'total' as labels,
                    COUNT(*) as value,
                    NOW() as timestamp
                FROM pg_stat_activity
                WHERE state = 'active'

                UNION ALL

                SELECT
                    'db_lock_count' as metric_name,
                    CASE WHEN granted THEN 'granted' ELSE 'waiting' END as labels,
                    COUNT(*) as value,
                    NOW() as timestamp
                FROM pg_locks
                WHERE database = (SELECT oid FROM pg_database WHERE datname = current_database())
                GROUP BY granted;
            """
            )
            await session.execute(prometheus_metrics_q)
            logger.info("✅ Представление Prometheus метрик создано")

            # 9. Создаем функцию для экспорта метрик в JSON
            logger.info("🔄 Создаем функцию экспорта метрик...")
            export_metrics_q = text(
                """
                CREATE OR REPLACE FUNCTION export_metrics_json()
                RETURNS JSONB AS $$
                DECLARE
                    result JSONB;
                BEGIN
                    SELECT jsonb_build_object(
                        'timestamp', NOW(),
                        'database', current_database(),
                        'metrics', jsonb_agg(
                            jsonb_build_object(
                                'name', metric_name,
                                'value', metric_value,
                                'unit', metric_unit,
                                'description', description
                            ) ORDER BY collected_at DESC
                        )
                    )
                    INTO result
                    FROM performance_metrics
                    WHERE collected_at >= NOW() - INTERVAL '1 hour';

                    RETURN result;
                END;
                $$ LANGUAGE plpgsql;
            """
            )
            await session.execute(export_metrics_q)
            logger.info("✅ Функция экспорта метрик создана")

            # 10. Создаем триггер для автоматического логирования миграций
            logger.info("🔄 Создаем триггер для логирования миграций...")
            migration_trigger_q = text(
                """
                CREATE OR REPLACE FUNCTION log_migration_changes()
                RETURNS trigger AS $$
                BEGIN
                    IF TG_OP = 'INSERT' THEN
                        INSERT INTO migration_logs (
                            migration_id, operation, started_at,
                            completed_at, duration_ms, rows_affected
                        ) VALUES (
                            NEW.id, 'success',
                            to_timestamp(NEW.applied_at),
                            to_timestamp(NEW.applied_at),
                            NEW.duration_ms, 0
                        );
                    ELSIF TG_OP = 'UPDATE' AND NEW.status = 'failed' THEN
                        INSERT INTO migration_logs (
                            migration_id, operation, started_at,
                            completed_at, duration_ms, error_message
                        ) VALUES (
                            NEW.id, 'error',
                            to_timestamp(NEW.applied_at),
                            NOW(),
                            NEW.duration_ms, NEW.error
                        );

                        -- Создаем алерт
                        PERFORM create_migration_alert(NEW.id, NEW.error, NEW.duration_ms);
                    END IF;

                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """
            )
            await session.execute(migration_trigger_q)
            await session.execute(
                text(
                    "DROP TRIGGER IF EXISTS trigger_log_migration_changes ON schema_migrations;"
                )
            )
            await session.execute(
                text(
                    """
                    CREATE TRIGGER trigger_log_migration_changes
                        AFTER INSERT OR UPDATE ON schema_migrations
                        FOR EACH ROW
                        EXECUTE FUNCTION log_migration_changes();
                    """
                )
            )
            logger.info("✅ Триггер для логирования миграций создан")

            await session.commit()

            logger.info("🎉 Система мониторинга и метрик создана успешно!")
            logger.info("📊 Созданные компоненты:")
            logger.info("   • migration_logs - логи миграций")
            logger.info("   • lock_logs - логи блокировок")
            logger.info("   • performance_metrics - метрики производительности")
            logger.info("   • alerts - система алертов")
            logger.info("   • prometheus_metrics - Prometheus-совместимые метрики")
            logger.info("   • collect_performance_metrics() - функция сбора метрик")
            logger.info("   • monitor_locks() - функция мониторинга блокировок")
            logger.info("   • export_metrics_json() - функция экспорта метрик")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка при создании системы мониторинга: {e}")
            raise
