#!/usr/bin/env python3
"""
Миграция для создания таблицы features.

Создает таблицу для хранения результатов расчёта технических индикаторов
с поддержкой версионирования и качества данных.
"""

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_create_features_table() -> None:
    """
    Создает таблицу features для хранения результатов расчёта технических индикаторов.
    """
    logger.info("📊 Создаем таблицу features...")

    async with get_db_session() as session:
        try:
            # Создаем основную таблицу features
            logger.info("🔄 Создаем основную таблицу features...")
            create_table_q = text(
                """
                CREATE TABLE IF NOT EXISTS features (
                    id SERIAL PRIMARY KEY,
                    run_id VARCHAR(36) NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    timeframe VARCHAR(10) NOT NULL,
                    timestamp BIGINT NOT NULL,

                    -- Основные OHLCV данные (для воспроизводимости)
                    open DECIMAL(20,8) NOT NULL,
                    high DECIMAL(20,8) NOT NULL,
                    low DECIMAL(20,8) NOT NULL,
                    close DECIMAL(20,8) NOT NULL,
                    volume DECIMAL(30,8) NOT NULL,

                    -- Рассчитанные индикаторы (JSONB для гибкости)
                    features_json JSONB NOT NULL,

                    -- Метаданные расчёта
                    feature_specs JSONB NOT NULL,  -- Спецификации использованных индикаторов
                    volatility_normalized BOOLEAN NOT NULL DEFAULT FALSE,
                    normalize_window INTEGER,
                    normalize_method VARCHAR(20),

                    -- Качество данных
                    data_quality_status VARCHAR(20) NOT NULL DEFAULT 'unknown',
                    nan_count INTEGER DEFAULT 0,
                    valid_rate DECIMAL(5,4) DEFAULT 1.0,

                    -- Версионирование
                    schema_version VARCHAR(10) NOT NULL DEFAULT 'v1',
                    algo_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
                    params_hash VARCHAR(16) NOT NULL,

                    -- Метаданные
                    warnings TEXT[],
                    errors TEXT[],

                    -- Временные метки
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
            """
            )
            await session.execute(create_table_q)
            logger.info("✅ Основная таблица features создана")

            # Создаем индексы
            logger.info("🔄 Создаем индексы...")

            # Основной индекс для быстрого поиска
            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_features_symbol_timeframe_timestamp
                ON features (symbol, timeframe, timestamp DESC);
            """
                )
            )

            # Индекс по run_id для группировки результатов
            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_features_run_id
                ON features (run_id);
            """
                )
            )

            # Индекс по качеству данных
            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_features_quality
                ON features (data_quality_status);
            """
                )
            )

            # Уникальное ограничение
            await session.execute(
                text(
                    """
                ALTER TABLE features ADD CONSTRAINT uq_features_unique
                UNIQUE (symbol, timeframe, timestamp, run_id);
            """
                )
            )

            logger.info("✅ Индексы созданы")

            # Создаем представление для последних результатов
            logger.info("🔄 Создаем представление latest_features...")
            await session.execute(
                text(
                    """
                CREATE OR REPLACE VIEW latest_features AS
                SELECT DISTINCT ON (symbol, timeframe)
                    symbol,
                    timeframe,
                    timestamp,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    features_json,
                    feature_specs,
                    volatility_normalized,
                    data_quality_status,
                    algo_version,
                    created_at
                FROM features
                ORDER BY symbol, timeframe, timestamp DESC;
            """
                )
            )

            logger.info("✅ Представление latest_features создано")

            # Создаем представление для статистики
            logger.info("🔄 Создаем представление features_stats...")
            await session.execute(
                text(
                    """
                CREATE OR REPLACE VIEW features_stats AS
                SELECT
                    symbol,
                    timeframe,
                    COUNT(*) as total_records,
                    COUNT(DISTINCT run_id) as total_runs,
                    MIN(timestamp) as first_timestamp,
                    MAX(timestamp) as last_timestamp,
                    AVG(nan_count) as avg_nan_count,
                    AVG(valid_rate) as avg_valid_rate,
                    COUNT(CASE WHEN data_quality_status = 'good' THEN 1 END) as good_quality_count,
                    COUNT(CASE WHEN data_quality_status = 'warning' THEN 1 END) as warning_quality_count,
                    COUNT(CASE WHEN data_quality_status = 'error' THEN 1 END) as error_quality_count
                FROM features
                GROUP BY symbol, timeframe
                ORDER BY symbol, timeframe;
            """
                )
            )

            logger.info("✅ Представление features_stats создано")

            await session.commit()
            logger.info("🎉 Миграция features_table завершена успешно!")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка при создании таблицы features: {e}")
            raise


if __name__ == "__main__":
    import asyncio

    asyncio.run(migrate_create_features_table())
