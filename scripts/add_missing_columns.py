"""
Скрипт для добавления недостающих колонок в таблицу indicators.

Использование:
    python scripts/add_missing_columns.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_missing_columns():
    """Добавляет недостающие колонки в таблицу indicators."""
    async with get_db_session() as session:
        try:
            # Bollinger Bands (если используются bb_* вместо bbands_*)
            logger.info("Проверка и добавление bb_* колонок...")
            check_bb = text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'indicators'
                  AND column_name = 'bb_upper'
            """
            )
            result = await session.execute(check_bb)
            has_bb = result.scalar() is not None

            if not has_bb:
                add_bb = text(
                    """
                    ALTER TABLE public.indicators
                    ADD COLUMN bb_upper DOUBLE PRECISION,
                    ADD COLUMN bb_middle DOUBLE PRECISION,
                    ADD COLUMN bb_lower DOUBLE PRECISION
                """
                )
                await session.execute(add_bb)
                logger.info("✅ Добавлены колонки bb_upper, bb_middle, bb_lower")
            else:
                logger.info("ℹ️ Колонки bb_* уже существуют")

            # Переименование bbands_* в bb_* (если есть)
            logger.info("Проверка наличия bbands_* колонок для переименования...")
            check_bbands = text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'indicators'
                  AND column_name = 'bbands_upper'
            """
            )
            result = await session.execute(check_bbands)
            has_bbands = result.scalar() is not None

            if has_bbands:
                rename_bbands = text(
                    """
                    ALTER TABLE public.indicators
                    RENAME COLUMN bbands_upper TO bb_upper;
                    ALTER TABLE public.indicators
                    RENAME COLUMN bbands_middle TO bb_middle;
                    ALTER TABLE public.indicators
                    RENAME COLUMN bbands_lower TO bb_lower;
                """
                )
                await session.execute(rename_bbands)
                logger.info("✅ Переименованы bbands_* в bb_*")
            else:
                logger.info("ℹ️ Колонки bbands_* не найдены")

            # Overlap индикаторы
            logger.info("Проверка и добавление overlap колонок...")
            check_overlap = text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'indicators'
                  AND column_name = 'hl2'
            """
            )
            result = await session.execute(check_overlap)
            has_overlap = result.scalar() is not None

            if not has_overlap:
                add_overlap = text(
                    """
                    ALTER TABLE public.indicators
                    ADD COLUMN hl2 DOUBLE PRECISION,
                    ADD COLUMN hlc3 DOUBLE PRECISION,
                    ADD COLUMN ohlc4 DOUBLE PRECISION
                """
                )
                await session.execute(add_overlap)
                logger.info("✅ Добавлены колонки hl2, hlc3, ohlc4")
            else:
                logger.info("ℹ️ Колонки overlap уже существуют")

            # Ichimoku индикаторы
            logger.info("Проверка и добавление ichimoku колонок...")
            check_ichimoku = text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'indicators'
                  AND column_name = 'ichimoku_tenkan'
            """
            )
            result = await session.execute(check_ichimoku)
            has_ichimoku = result.scalar() is not None

            if not has_ichimoku:
                add_ichimoku = text(
                    """
                    ALTER TABLE public.indicators
                    ADD COLUMN ichimoku_tenkan DOUBLE PRECISION,
                    ADD COLUMN ichimoku_kijun DOUBLE PRECISION,
                    ADD COLUMN ichimoku_senkou_a DOUBLE PRECISION,
                    ADD COLUMN ichimoku_senkou_b DOUBLE PRECISION,
                    ADD COLUMN ichimoku_chikou DOUBLE PRECISION
                """
                )
                await session.execute(add_ichimoku)
                logger.info("✅ Добавлены колонки ichimoku_*")
            else:
                logger.info("ℹ️ Колонки ichimoku_* уже существуют")

            # Проверка результата
            logger.info("Проверка результата...")
            check_result = text(
                """
                SELECT
                    column_name,
                    data_type,
                    is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'indicators'
                  AND column_name IN (
                    'bb_upper', 'bb_middle', 'bb_lower',
                    'hl2', 'hlc3', 'ohlc4',
                    'ichimoku_tenkan', 'ichimoku_kijun',
                    'ichimoku_senkou_a', 'ichimoku_senkou_b', 'ichimoku_chikou'
                  )
                ORDER BY column_name
            """
            )
            result = await session.execute(check_result)
            columns = result.all()

            logger.info(f"\n✅ Найдено {len(columns)} колонок:")
            for col_name, data_type, is_nullable in columns:
                logger.info(f"  - {col_name}: {data_type} (nullable: {is_nullable})")

            await session.commit()
            logger.info("\n✅ Миграция успешно завершена!")

        except Exception as e:
            logger.error(f"❌ Ошибка при выполнении миграции: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(add_missing_columns())
