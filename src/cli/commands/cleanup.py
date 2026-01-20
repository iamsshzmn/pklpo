#!/usr/bin/env python3
"""
CLI команда для управления очисткой данных в swap_ohlcv_p
"""

import asyncio
import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


def register(subparsers):
    """Регистрирует команду в CLI"""
    p = subparsers.add_parser("cleanup", help="Управление очисткой данных")
    p.add_argument(
        "--days",
        type=int,
        default=2,
        help="Удалить данные старше N дней (по умолчанию 2)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Показать что будет удалено без выполнения",
    )
    p.add_argument("--stats", action="store_true", help="Показать статистику данных")
    p.set_defaults(_handler=handle)


async def handle(args):
    """Обработчик CLI команды"""
    if args.stats:
        await show_stats()
    elif args.dry_run:
        await dry_run_cleanup(args.days)
    else:
        await perform_cleanup(args.days)


async def show_stats():
    """Показывает статистику данных"""
    async with get_db_session() as session:
        # Общая статистика
        result = await session.execute(
            text(
                """
            SELECT
                COUNT(*) as total_rows,
                COUNT(DISTINCT symbol) as unique_symbols,
                COUNT(DISTINCT timeframe) as unique_timeframes,
                MIN(timestamp) as oldest_timestamp,
                MAX(timestamp) as newest_timestamp
            FROM swap_ohlcv_p
        """
            )
        )
        stats = result.fetchone()

        print("📊 СТАТИСТИКА ТАБЛИЦЫ swap_ohlcv_p:")
        print(f"   • Всего записей: {stats[0]:,}")
        print(f"   • Уникальных символов: {stats[1]}")
        print(f"   • Уникальных таймфреймов: {stats[2]}")

        if stats[3] and stats[4]:
            from datetime import datetime

            oldest = datetime.fromtimestamp(stats[3])
            newest = datetime.fromtimestamp(stats[4])
            print(f"   • Самые старые данные: {oldest}")
            print(f"   • Самые новые данные: {newest}")

        # Статистика по дням
        result = await session.execute(
            text(
                """
            SELECT
                DATE(to_timestamp(timestamp)) as date,
                COUNT(*) as count
            FROM swap_ohlcv_p
            GROUP BY DATE(to_timestamp(timestamp))
            ORDER BY date DESC
            LIMIT 10
        """
            )
        )
        daily_stats = result.fetchall()

        print("\n📅 ДАННЫЕ ПО ДНЯМ (последние 10):")
        for date, count in daily_stats:
            print(f"   • {date}: {count:,} записей")


async def dry_run_cleanup(days: int):
    """Показывает что будет удалено без выполнения"""
    async with get_db_session() as session:
        cutoff_timestamp = int(asyncio.get_event_loop().time()) - (days * 24 * 60 * 60)

        # Подсчитываем записи для удаления
        result = await session.execute(
            text(
                """
            SELECT COUNT(*) as count_to_delete
            FROM swap_ohlcv_p
            WHERE timestamp < :cutoff_timestamp
        """
            ),
            {"cutoff_timestamp": cutoff_timestamp},
        )

        count_to_delete = result.fetchone()[0]

        print("🔍 DRY RUN: Что будет удалено")
        print(f"   • Удалятся данные старше {days} дней")
        print(f"   • Timestamp cutoff: {cutoff_timestamp}")
        print(f"   • Записей для удаления: {count_to_delete:,}")

        if count_to_delete > 0:
            # Показываем примеры записей которые будут удалены
            result = await session.execute(
                text(
                    """
                SELECT symbol, timeframe, timestamp, to_timestamp(timestamp) as date
                FROM swap_ohlcv_p
                WHERE timestamp < :cutoff_timestamp
                ORDER BY timestamp DESC
                LIMIT 5
            """
                ),
                {"cutoff_timestamp": cutoff_timestamp},
            )

            examples = result.fetchall()
            print("\n📋 Примеры записей для удаления:")
            for symbol, timeframe, timestamp, date in examples:
                print(f"   • {symbol} {timeframe}: {date} (ts: {timestamp})")


async def perform_cleanup(days: int):
    """Выполняет очистку данных"""
    async with get_db_session() as session:
        try:
            logger.info(f"🗑️ Запускаем очистку данных старше {days} дней...")

            # Вызываем функцию очистки
            result = await session.execute(
                text(
                    """
                SELECT * FROM manual_cleanup_swap_data(:days_old)
            """
                ),
                {"days_old": days},
            )

            cleanup_result = result.fetchone()

            if cleanup_result:
                deleted_count, cutoff_timestamp = cleanup_result
                logger.info(f"✅ Очистка завершена: удалено {deleted_count:,} записей")
                logger.info(f"   • Timestamp cutoff: {cutoff_timestamp}")
            else:
                logger.info("ℹ️ Нет данных для удаления")

            await session.commit()

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка при очистке: {e}")
            raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Управление очисткой данных")
    parser.add_argument(
        "--days", type=int, default=2, help="Удалить данные старше N дней"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Показать что будет удалено"
    )
    parser.add_argument("--stats", action="store_true", help="Показать статистику")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.stats:
        asyncio.run(show_stats())
    elif args.dry_run:
        asyncio.run(dry_run_cleanup(args.days))
    else:
        asyncio.run(perform_cleanup(args.days))
