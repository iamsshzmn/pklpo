#!/usr/bin/env python
"""
Тестовый скрипт для проверки исправления greenlet_spawn ошибки.
Проверяет, что async вставка в БД работает корректно.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


async def test_basic_query():
    """Проверяет базовый SELECT запрос."""
    logger.info("🧪 TEST 1: Basic SELECT query...")
    try:
        async with get_db_session() as session:
            result = await session.execute(text("SELECT 1 as test"))
            row = result.first()
            assert row[0] == 1
            logger.info("✅ Basic query works!")
            return True
    except Exception as e:
        logger.error(f"❌ Basic query failed: {e}")
        return False


async def test_indicators_table():
    """Проверяет наличие таблицы indicators."""
    logger.info("🧪 TEST 2: Check indicators table...")
    try:
        async with get_db_session() as session:
            result = await session.execute(
                text(
                    """
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name = 'indicators' AND table_schema = 'public'
            """
                )
            )
            count = result.scalar()
            if count > 0:
                logger.info("✅ Indicators table exists!")
                return True
            logger.warning("⚠️ Indicators table not found")
            return False
    except Exception as e:
        logger.error(f"❌ Table check failed: {e}")
        return False


async def test_insert_dummy_record():
    """Проверяет вставку тестовой записи."""
    logger.info("🧪 TEST 3: Insert dummy record...")
    try:
        async with get_db_session() as session:
            # Вставляем тестовую запись
            await session.execute(
                text(
                    """
                INSERT INTO indicators (symbol, timeframe, timestamp, calculated_at, ema_8)
                VALUES ('TEST', '1m', :ts, NOW(), 100.0)
                ON CONFLICT (symbol, timeframe, timestamp)
                DO UPDATE SET ema_8 = EXCLUDED.ema_8
            """
                ),
                {"ts": 1234567890000},
            )

            # Проверяем, что запись вставилась
            result = await session.execute(
                text(
                    """
                SELECT ema_8 FROM indicators
                WHERE symbol = 'TEST' AND timeframe = '1m' AND timestamp = :ts
            """
                ),
                {"ts": 1234567890000},
            )

            row = result.first()
            if row and row[0] == 100.0:
                logger.info("✅ Insert and UPSERT work!")

                # Cleanup
                await session.execute(
                    text(
                        """
                    DELETE FROM indicators
                    WHERE symbol = 'TEST' AND timeframe = '1m' AND timestamp = :ts
                """
                    ),
                    {"ts": 1234567890000},
                )

                return True
            logger.error("❌ Record not found after insert")
            return False
    except Exception as e:
        logger.error(f"❌ Insert test failed: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


async def main():
    """Запускает все тесты."""
    logger.info("=" * 80)
    logger.info("🚀 TESTING ASYNC DB SESSION AND INSERT")
    logger.info("=" * 80)

    results = []

    # Test 1: Basic query
    results.append(await test_basic_query())

    # Test 2: Table existence
    results.append(await test_indicators_table())

    # Test 3: Insert/UPSERT
    if results[1]:  # Only if table exists
        results.append(await test_insert_dummy_record())
    else:
        logger.warning("⚠️ Skipping insert test (table doesn't exist)")
        results.append(False)

    logger.info("=" * 80)
    logger.info("📊 TEST RESULTS")
    logger.info("=" * 80)
    logger.info(f"Test 1 (Basic Query): {'✅ PASS' if results[0] else '❌ FAIL'}")
    logger.info(f"Test 2 (Table Check): {'✅ PASS' if results[1] else '❌ FAIL'}")
    logger.info(f"Test 3 (Insert/UPSERT): {'✅ PASS' if results[2] else '❌ FAIL'}")
    logger.info("=" * 80)

    if all(results):
        logger.info("🎉 ALL TESTS PASSED! greenlet_spawn issue is fixed.")
        return 0
    logger.error("❌ SOME TESTS FAILED! Check logs above.")
    return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
