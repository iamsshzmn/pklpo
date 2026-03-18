#!/usr/bin/env python3
"""
Миграция для создания таблицы combination_features (numeric-only).

Таблица хранит числовые фичи комбинаций индикаторов без текстовых рекомендаций.
Все "сигналы" и "направления" кодируются числами в JSONB поле features.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_create_combination_features() -> None:
    """Создает таблицу combination_features с numeric-only контрактом."""
    async with get_db_session() as session:
        try:
            # Проверяем, существует ли таблица
            check_query = text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name = 'combination_features'
                AND table_schema = 'public'
            """
            )

            result = await session.execute(check_query)
            exists = result.fetchone()

            if not exists:
                # Создаем таблицу согласно плану
                create_table_query = text(
                    """
                    CREATE TABLE combination_features (
                        symbol TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        timestamp BIGINT NOT NULL,
                        combination_id TEXT NOT NULL,
                        features JSONB NOT NULL,
                        meta JSONB,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW(),
                        PRIMARY KEY (symbol, timeframe, timestamp, combination_id)
                    )
                """
                )

                await session.execute(create_table_query)

                # Создаем уникальный индекс (как в плане)
                create_index_query = text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS ux_combination_features
                    ON combination_features (symbol, timeframe, timestamp, combination_id)
                """
                )

                await session.execute(create_index_query)

                # Индекс для быстрого поиска по combination_id
                create_combo_idx_query = text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_combination_features_combo_id
                    ON combination_features (combination_id)
                """
                )

                await session.execute(create_combo_idx_query)

                # Индекс для временных запросов
                create_ts_idx_query = text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_combination_features_timestamp
                    ON combination_features (symbol, timeframe, timestamp DESC)
                """
                )

                await session.execute(create_ts_idx_query)

                # GIN индекс для JSONB features (для быстрого поиска по ключам)
                create_gin_idx_query = text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_combination_features_features_gin
                    ON combination_features USING GIN (features)
                """
                )

                await session.execute(create_gin_idx_query)

                logger.info("✅ Создана таблица combination_features с индексами")
            else:
                logger.info("ℹ️ Таблица combination_features уже существует")

            logger.info("🎉 Миграция combination_features завершена")

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в миграции: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(migrate_create_combination_features())
