#!/usr/bin/env python3
"""
Миграция для добавления политики удаления данных старше 2 дней.
Создает функцию и триггер для автоматической очистки старых данных.
"""

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_add_data_retention() -> None:
    """
    Добавляет политику удаления данных старше 2 дней.
    """
    logger.info("🗑️ Добавляем политику удаления данных старше 2 дней...")

    async with get_db_session() as session:
        try:
            # 0. Создаем таблицу для настроек системы
            logger.info("🔄 Создаем таблицу system_settings...")
            create_settings_table_q = text(
                """
                CREATE TABLE IF NOT EXISTS system_settings (
                    key VARCHAR(100) PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """
            )
            await session.execute(create_settings_table_q)
            logger.info("✅ Таблица system_settings создана")

            # 1. Создаем функцию для удаления старых данных
            logger.info("🔄 Создаем функцию очистки старых данных...")
            create_function_q = text(
                """
                CREATE OR REPLACE FUNCTION cleanup_old_swap_data()
                RETURNS void AS $$
                DECLARE
                    cutoff_timestamp BIGINT;
                    deleted_count INTEGER;
                BEGIN
                    -- swap_ohlcv_p хранит timestamp в миллисекундах
                    cutoff_timestamp := (EXTRACT(EPOCH FROM NOW() - INTERVAL '2 days') * 1000)::BIGINT;

                    -- Удаляем данные старше 2 дней
                    DELETE FROM swap_ohlcv_p
                    WHERE timestamp < cutoff_timestamp;

                    GET DIAGNOSTICS deleted_count = ROW_COUNT;

                    -- Логируем результат
                    RAISE NOTICE 'Удалено % записей старше 2 дней (timestamp < %)',
                        deleted_count, cutoff_timestamp;
                END;
                $$ LANGUAGE plpgsql;
            """
            )
            await session.execute(create_function_q)
            logger.info("✅ Функция очистки создана")

            # 2. Создаем триггер для автоматической очистки
            logger.info("🔄 Создаем триггер для автоматической очистки...")
            create_trigger_q = text(
                """
                CREATE OR REPLACE FUNCTION trigger_cleanup_old_data()
                RETURNS trigger AS $$
                DECLARE
                    last_cleanup_time TIMESTAMP;
                    current_ts TIMESTAMP;
                BEGIN
                    -- Получаем время последней очистки
                    SELECT COALESCE(
                        (SELECT value::TIMESTAMP FROM system_settings WHERE key = 'last_cleanup_time'),
                        '1970-01-01'::TIMESTAMP
                    ) INTO last_cleanup_time;

                    current_ts := NOW();

                    -- Запускаем очистку раз в час
                    IF current_ts - last_cleanup_time > INTERVAL '1 hour' THEN
                        PERFORM cleanup_old_swap_data();

                        -- Обновляем время последней очистки
                        INSERT INTO system_settings (key, value)
                        VALUES ('last_cleanup_time', current_ts::TEXT)
                        ON CONFLICT (key) DO UPDATE SET value = current_ts::TEXT;
                    END IF;

                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """
            )
            await session.execute(create_trigger_q)
            logger.info("✅ Функция триггера создана")

            # 3. Создаем сам триггер
            logger.info("🔄 Создаем триггер...")
            await session.execute(
                text(
                    "DROP TRIGGER IF EXISTS trigger_cleanup_swap_data ON swap_ohlcv_p;"
                )
            )
            await session.execute(
                text(
                    """
                    CREATE TRIGGER trigger_cleanup_swap_data
                    AFTER INSERT ON swap_ohlcv_p
                    FOR EACH ROW
                    EXECUTE FUNCTION trigger_cleanup_old_data();
                    """
                )
            )
            logger.info("✅ Триггер создан")

            # 4. Создаем функцию для ручной очистки
            logger.info("🔄 Создаем функцию для ручной очистки...")
            create_manual_cleanup_q = text(
                """
                CREATE OR REPLACE FUNCTION manual_cleanup_swap_data(days_old INTEGER DEFAULT 2)
                RETURNS TABLE(deleted_count BIGINT, cutoff_timestamp BIGINT) AS $$
                DECLARE
                    cutoff_ts BIGINT;
                    deleted_cnt BIGINT;
                BEGIN
                    -- swap_ohlcv_p хранит timestamp в миллисекундах
                    cutoff_ts := (EXTRACT(EPOCH FROM NOW() - INTERVAL '1 day' * days_old) * 1000)::BIGINT;

                    -- Удаляем данные
                    DELETE FROM swap_ohlcv_p
                    WHERE timestamp < cutoff_ts;

                    GET DIAGNOSTICS deleted_cnt = ROW_COUNT;

                    -- Возвращаем результат
                    RETURN QUERY SELECT deleted_cnt, cutoff_ts;

                    -- Логируем результат
                    RAISE NOTICE 'Ручная очистка: удалено % записей старше % дней (timestamp < %)',
                        deleted_cnt, days_old, cutoff_ts;
                END;
                $$ LANGUAGE plpgsql;
            """
            )
            await session.execute(create_manual_cleanup_q)
            logger.info("✅ Функция ручной очистки создана")

            # 5. Запускаем первоначальную очистку
            logger.info("🔄 Запускаем первоначальную очистку...")
            initial_cleanup_q = text("SELECT * FROM manual_cleanup_swap_data(2)")
            result = await session.execute(initial_cleanup_q)
            cleanup_result = result.fetchone()

            if cleanup_result:
                logger.info(
                    f"✅ Первоначальная очистка: удалено {cleanup_result[0]} записей"
                )

            await session.commit()
            logger.info("🎉 Политика удаления данных добавлена успешно!")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка при добавлении политики удаления: {e}")
            raise


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)
    asyncio.run(migrate_add_data_retention())
