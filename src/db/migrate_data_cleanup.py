#!/usr/bin/env python3
"""
Миграция для очистки и нормализации данных.
Удаляет дубликаты, исправляет неверные таймфреймы, валидирует данные.
"""

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_data_cleanup() -> None:
    """
    Выполняет очистку и нормализацию данных.
    """
    logger.info("🧹 Начинаем очистку и нормализацию данных...")

    async with get_db_session() as session:
        try:
            # 1. Удаляем дубликаты из ohlcv_p
            logger.info("🔄 Удаляем дубликаты из ohlcv_p...")
            dedup_ohlcv_q = text(
                """
                DELETE FROM ohlcv_p
                WHERE ctid NOT IN (
                    SELECT MIN(ctid)
                    FROM ohlcv_p
                    GROUP BY symbol, timeframe, timestamp
                );
            """
            )
            result = await session.execute(dedup_ohlcv_q)
            ohlcv_deleted = result.rowcount
            logger.info(f"✅ Удалено {ohlcv_deleted} дубликатов из ohlcv_p")

            # 2. Удаляем дубликаты из indicators_p
            logger.info("🔄 Удаляем дубликаты из indicators_p...")
            dedup_indicators_q = text(
                """
                DELETE FROM indicators_p
                WHERE ctid NOT IN (
                    SELECT MIN(ctid)
                    FROM indicators_p
                    GROUP BY symbol, timeframe, timestamp
                );
            """
            )
            result = await session.execute(dedup_indicators_q)
            indicators_deleted = result.rowcount
            logger.info(f"✅ Удалено {indicators_deleted} дубликатов из indicators_p")

            # 3. Исправляем неверные таймфреймы
            logger.info("🔄 Исправляем неверные таймфреймы...")
            fix_timeframes_q = text(
                """
                UPDATE ohlcv_p
                SET timeframe = CASE
                    WHEN timeframe = '1Mutc' THEN '1M'
                    WHEN timeframe = '1Dutc' THEN '1D'
                    WHEN timeframe = '1Wutc' THEN '1W'
                    WHEN timeframe = '1Hutc' THEN '1H'
                    WHEN timeframe = '4Hutc' THEN '4H'
                    ELSE timeframe
                END
                WHERE timeframe IN ('1Mutc', '1Dutc', '1Wutc', '1Hutc', '4Hutc');
            """
            )
            result = await session.execute(fix_timeframes_q)
            timeframes_fixed = result.rowcount
            logger.info(f"✅ Исправлено {timeframes_fixed} неверных таймфреймов")

            # 4. Валидируем цены (должны быть положительными)
            logger.info("🔄 Валидируем цены...")
            validate_prices_q = text(
                """
                DELETE FROM ohlcv_p
                WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                   OR high < low
                   OR open > high OR open < low
                   OR close > high OR close < low;
            """
            )
            result = await session.execute(validate_prices_q)
            invalid_prices_deleted = result.rowcount
            logger.info(
                f"✅ Удалено {invalid_prices_deleted} записей с неверными ценами"
            )

            # 5. Валидируем объемы (должны быть неотрицательными)
            logger.info("🔄 Валидируем объемы...")
            validate_volumes_q = text(
                """
                UPDATE ohlcv_p
                SET volume = 0
                WHERE volume < 0;
            """
            )
            result = await session.execute(validate_volumes_q)
            volumes_fixed = result.rowcount
            logger.info(f"✅ Исправлено {volumes_fixed} отрицательных объемов")

            # 6. Удаляем записи с NULL timestamp
            logger.info("🔄 Удаляем записи с NULL timestamp...")

            # Удаляем из ohlcv_p
            null_timestamp_ohlcv_q = text("DELETE FROM ohlcv_p WHERE timestamp IS NULL")
            result = await session.execute(null_timestamp_ohlcv_q)
            ohlcv_null_deleted = result.rowcount

            # Удаляем из indicators_p
            null_timestamp_indicators_q = text(
                "DELETE FROM indicators_p WHERE timestamp IS NULL"
            )
            result = await session.execute(null_timestamp_indicators_q)
            indicators_null_deleted = result.rowcount

            null_timestamps_deleted = ohlcv_null_deleted + indicators_null_deleted
            logger.info(
                f"✅ Удалено {null_timestamps_deleted} записей с NULL timestamp"
            )

            # 7. Создаем индексы для оптимизации
            logger.info("🔄 Создаем дополнительные индексы...")

            # Индекс для ohlcv_p
            create_index_ohlcv_q = text(
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlcv_p_symbol_timeframe
                ON ohlcv_p (symbol, timeframe)
            """
            )
            await session.execute(create_index_ohlcv_q)

            # Индекс для indicators_p
            create_index_indicators_q = text(
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_indicators_p_symbol_timeframe
                ON indicators_p (symbol, timeframe)
            """
            )
            await session.execute(create_index_indicators_q)

            # Индекс для диапазона времени
            create_index_timestamp_q = text(
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ohlcv_p_timestamp_range
                ON ohlcv_p (timestamp) WHERE timestamp >= '2024-01-01'
            """
            )
            await session.execute(create_index_timestamp_q)

            logger.info("✅ Дополнительные индексы созданы")

            # 8. Анализируем таблицы для оптимизации
            logger.info("🔄 Анализируем таблицы...")

            # Анализируем каждую таблицу отдельно
            await session.execute(text("ANALYZE ohlcv_p"))
            await session.execute(text("ANALYZE indicators_p"))
            await session.execute(text("ANALYZE instruments"))

            logger.info("✅ Анализ таблиц завершен")

            await session.commit()

            # Статистика
            total_cleaned = (
                ohlcv_deleted
                + indicators_deleted
                + invalid_prices_deleted
                + null_timestamps_deleted
            )
            logger.info("🎉 Очистка данных завершена!")
            logger.info("📊 Статистика:")
            logger.info(
                f"   • Дубликатов удалено: {ohlcv_deleted + indicators_deleted}"
            )
            logger.info(f"   • Таймфреймов исправлено: {timeframes_fixed}")
            logger.info(f"   • Неверных цен удалено: {invalid_prices_deleted}")
            logger.info(f"   • Объемов исправлено: {volumes_fixed}")
            logger.info(f"   • NULL timestamp удалено: {null_timestamps_deleted}")
            logger.info(f"   • Всего записей обработано: {total_cleaned}")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка при очистке данных: {e}")
            raise
