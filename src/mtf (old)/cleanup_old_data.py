#!/usr/bin/env python3
"""
Скрипт для очистки старых MTF данных
Удаляет записи старше 24 часов из MTF таблиц
"""

import asyncio
import logging

# Добавляем корневую директорию в путь для импортов
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database import get_async_session
from src.logging_config import setup_logging

setup_logging("mtf_cleanup.log")
logger = logging.getLogger(__name__)


async def cleanup_old_mtf_data(hours_old: int = 24, dry_run: bool = False):
    """
    Очищает старые MTF данные

    Args:
        hours_old: Возраст данных в часах для удаления (по умолчанию 24)
        dry_run: Только проверка без удаления
    """
    try:
        logger.info(f"🧹 Запуск очистки MTF данных старше {hours_old} часов...")

        if dry_run:
            logger.info("🔍 Режим проверки (dry-run) - данные не будут удалены")

        # Вычисляем временную границу
        cutoff_time = datetime.now(UTC) - timedelta(hours=hours_old)
        logger.info(f"⏰ Удаляем данные старше: {cutoff_time}")

        # MTF таблицы для очистки
        tables = ["mtf.context", "mtf.triggers", "mtf.consensus"]

        total_deleted = 0

        async for session in get_async_session():
            try:
                for table in tables:
                    # Проверяем количество записей до очистки
                    count_query = text(f"SELECT COUNT(*) FROM {table}")
                    result = await session.execute(count_query)
                    total_count = result.scalar()

                    # Проверяем количество старых записей
                    old_count_query = text(
                        f"""
                        SELECT COUNT(*) FROM {table}
                        WHERE ts < :cutoff_time
                    """
                    )
                    result = await session.execute(
                        old_count_query, {"cutoff_time": cutoff_time}
                    )
                    old_count = result.scalar()

                    logger.info(f"📊 {table}:")
                    logger.info(f"   Всего записей: {total_count}")
                    logger.info(f"   Старых записей (>24h): {old_count}")

                    if old_count > 0:
                        if not dry_run:
                            # Удаляем старые записи
                            delete_query = text(
                                f"""
                                DELETE FROM {table}
                                WHERE ts < :cutoff_time
                            """
                            )
                            result = await session.execute(
                                delete_query, {"cutoff_time": cutoff_time}
                            )
                            deleted_count = result.rowcount

                            logger.info(f"   🗑️ Удалено: {deleted_count} записей")
                            total_deleted += deleted_count
                        else:
                            logger.info(
                                f"   🔍 Будет удалено: {old_count} записей (dry-run)"
                            )
                    else:
                        logger.info("   ✅ Старых записей не найдено")

                if not dry_run:
                    await session.commit()
                    logger.info(
                        f"🎉 Очистка завершена! Всего удалено: {total_deleted} записей"
                    )
                else:
                    logger.info("🔍 Проверка завершена (dry-run)")

            except Exception as e:
                if not dry_run:
                    await session.rollback()
                logger.error(f"❌ Ошибка при очистке: {e}")
                break

        return {
            "status": "completed",
            "deleted_count": total_deleted,
            "cutoff_time": cutoff_time.isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Ошибка в процессе очистки: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


async def cleanup_old_data_by_symbol(
    symbol: str, hours_old: int = 24, dry_run: bool = False
):
    """
    Очищает старые MTF данные для конкретного символа

    Args:
        symbol: Символ для очистки
        hours_old: Возраст данных в часах для удаления
        dry_run: Только проверка без удаления
    """
    try:
        logger.info(
            f"🧹 Запуск очистки MTF данных для {symbol} старше {hours_old} часов..."
        )

        if dry_run:
            logger.info("🔍 Режим проверки (dry-run)")

        cutoff_time = datetime.now(UTC) - timedelta(hours=hours_old)

        tables = ["mtf.context", "mtf.triggers", "mtf.consensus"]

        total_deleted = 0

        async for session in get_async_session():
            try:
                for table in tables:
                    # Проверяем количество записей для символа
                    count_query = text(
                        f"""
                        SELECT COUNT(*) FROM {table}
                        WHERE symbol = :symbol
                    """
                    )
                    result = await session.execute(count_query, {"symbol": symbol})
                    total_count = result.scalar()

                    # Проверяем количество старых записей для символа
                    old_count_query = text(
                        f"""
                        SELECT COUNT(*) FROM {table}
                        WHERE symbol = :symbol AND ts < :cutoff_time
                    """
                    )
                    result = await session.execute(
                        old_count_query, {"symbol": symbol, "cutoff_time": cutoff_time}
                    )
                    old_count = result.scalar()

                    logger.info(f"📊 {table} для {symbol}:")
                    logger.info(f"   Всего записей: {total_count}")
                    logger.info(f"   Старых записей (>24h): {old_count}")

                    if old_count > 0:
                        if not dry_run:
                            # Удаляем старые записи для символа
                            delete_query = text(
                                f"""
                                DELETE FROM {table}
                                WHERE symbol = :symbol AND ts < :cutoff_time
                            """
                            )
                            result = await session.execute(
                                delete_query,
                                {"symbol": symbol, "cutoff_time": cutoff_time},
                            )
                            deleted_count = result.rowcount

                            logger.info(f"   🗑️ Удалено: {deleted_count} записей")
                            total_deleted += deleted_count
                        else:
                            logger.info(
                                f"   🔍 Будет удалено: {old_count} записей (dry-run)"
                            )
                    else:
                        logger.info("   ✅ Старых записей не найдено")

                if not dry_run:
                    await session.commit()
                    logger.info(
                        f"🎉 Очистка для {symbol} завершена! Удалено: {total_deleted} записей"
                    )
                else:
                    logger.info(f"🔍 Проверка для {symbol} завершена (dry-run)")

            except Exception as e:
                if not dry_run:
                    await session.rollback()
                logger.error(f"❌ Ошибка при очистке {symbol}: {e}")
                break

        return {
            "status": "completed",
            "symbol": symbol,
            "deleted_count": total_deleted,
            "cutoff_time": cutoff_time.isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Ошибка в процессе очистки {symbol}: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Очистка старых MTF данных")
    parser.add_argument(
        "--hours", type=int, default=24, help="Возраст данных в часах (по умолчанию 24)"
    )
    parser.add_argument("--symbol", type=str, help="Конкретный символ для очистки")
    parser.add_argument(
        "--dry-run", action="store_true", help="Только проверка без удаления"
    )

    args = parser.parse_args()

    async def main():
        if args.symbol:
            await cleanup_old_data_by_symbol(args.symbol, args.hours, args.dry_run)
        else:
            await cleanup_old_mtf_data(args.hours, args.dry_run)

    asyncio.run(main())
