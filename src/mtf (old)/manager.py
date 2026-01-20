#!/usr/bin/env python3
"""
Управляющий файл для MTF (Multi-Timeframe) модуля
Выполняет полный цикл: context → triggers → consensus → анализ решений
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent.parent))

from datetime import UTC

from sqlalchemy import text

from src.database import get_async_session
from src.logging_config import setup_logging
from src.mtf.cleanup_old_data import cleanup_old_data_by_symbol, cleanup_old_mtf_data
from src.mtf.decision_maker import MTFDecisionMaker
from src.mtf.etl.consensus_writer import consensus_writer
from src.mtf.etl.context_loader import context_loader
from src.mtf.etl.trigger_loader import trigger_loader

setup_logging("mtf.log")
logger = logging.getLogger(__name__)


async def run_mtf_full_cycle(symbol: str | None = None, dry_run: bool = False):
    """
    Запускает полный цикл MTF: ETL → анализ решений

    Args:
        symbol: Конкретный символ (если None, обрабатываются все)
        dry_run: Только проверка без выполнения действий
    """
    try:
        logger.info("🚀 Запуск полного цикла MTF...")

        if dry_run:
            logger.info("🔍 Режим проверки (dry-run)")

        # Этап 1: Запуск ETL процесса
        logger.info("📊 Этап 1: Запуск MTF ETL процесса...")

        if not dry_run:
            # Запускаем все три этапа ETL
            if symbol:
                await context_loader.load_context_for_symbol(symbol)
                await trigger_loader.load_triggers_for_symbol(symbol)
                await consensus_writer.write_consensus_for_symbol(symbol)
            else:
                await context_loader.load_context_for_all_symbols()
                await trigger_loader.load_triggers_for_all_symbols()
                await consensus_writer.write_consensus_for_all_symbols()

            logger.info("✅ MTF ETL процесс завершен успешно!")
        else:
            logger.info("🔍 Пропущен ETL процесс (dry-run)")

        # Этап 2: Анализ результатов
        logger.info("🎯 Этап 2: Анализ MTF результатов...")

        decision_maker = MTFDecisionMaker()

        # Получаем обзор рынка
        market_overview = await decision_maker.get_market_overview(limit=10)

        if market_overview:
            logger.info(f"📊 Найдено {len(market_overview)} активных сигналов")

            # Выводим топ сигналы
            logger.info("🏆 Топ сигналы:")
            for i, signal in enumerate(market_overview[:5], 1):
                signal_type = (
                    "LONG"
                    if signal["side"] == 1
                    else "SHORT"
                    if signal["side"] == -1
                    else "FLAT"
                )
                logger.info(
                    f"  {i}. {signal['symbol']} {signal['horizon']} {signal_type} (score: {signal['score']:.3f})"
                )
        else:
            logger.warning("⚠️ Нет активных сигналов")

        # Получаем swing возможности
        swing_opportunities = await decision_maker.get_swing_opportunities()
        if swing_opportunities:
            logger.info(f"📈 Найдено {len(swing_opportunities)} swing возможностей")

        # Получаем внутридневные сигналы
        intraday_signals = await decision_maker.get_intraday_signals()
        if intraday_signals:
            logger.info(f"⚡ Найдено {len(intraday_signals)} внутридневных сигналов")

        logger.info("✅ Анализ MTF результатов завершен!")

        return {
            "status": "completed",
            "market_signals": len(market_overview) if market_overview else 0,
            "swing_opportunities": (
                len(swing_opportunities) if swing_opportunities else 0
            ),
            "intraday_signals": len(intraday_signals) if intraday_signals else 0,
        }

    except Exception as e:
        logger.error(f"❌ Ошибка в MTF цикле: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


async def run_mtf_etl_only(symbol: str | None = None, dry_run: bool = False):
    """
    Запускает только ETL процесс MTF

    Args:
        symbol: Конкретный символ (если None, обрабатываются все)
        dry_run: Только проверка без выполнения действий
    """
    try:
        logger.info("📊 Запуск MTF ETL процесса...")

        if not dry_run:
            # Запускаем все три этапа ETL
            if symbol:
                await context_loader.load_context_for_symbol(symbol)
                await trigger_loader.load_triggers_for_symbol(symbol)
                await consensus_writer.write_consensus_for_symbol(symbol)
            else:
                await context_loader.load_context_for_all_symbols()
                await trigger_loader.load_triggers_for_all_symbols()
                await consensus_writer.write_consensus_for_all_symbols()

            logger.info("✅ MTF ETL процесс завершен успешно!")
        else:
            logger.info("🔍 Пропущен ETL процесс (dry-run)")

        return {"status": "completed"}

    except Exception as e:
        logger.error(f"❌ Ошибка в MTF ETL: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


async def run_mtf_analysis_only(symbol: str | None = None, limit: int = 20):
    """
    Запускает только анализ MTF результатов

    Args:
        symbol: Конкретный символ (если None, анализируются все)
        limit: Ограничение количества сигналов
    """
    try:
        logger.info("🎯 Запуск анализа MTF результатов...")

        decision_maker = MTFDecisionMaker()

        # Получаем обзор рынка
        market_overview = await decision_maker.get_market_overview(limit=limit)

        if market_overview:
            logger.info(f"📊 Найдено {len(market_overview)} активных сигналов")

            # Выводим топ сигналы
            logger.info("🏆 Топ сигналы:")
            for i, signal in enumerate(market_overview[:10], 1):
                signal_type = (
                    "LONG"
                    if signal["side"] == 1
                    else "SHORT"
                    if signal["side"] == -1
                    else "FLAT"
                )
                logger.info(
                    f"  {i}. {signal['symbol']} {signal['horizon']} {signal_type} (score: {signal['score']:.3f})"
                )
        else:
            logger.warning("⚠️ Нет активных сигналов")

        # Получаем swing возможности
        swing_opportunities = await decision_maker.get_swing_opportunities()
        if swing_opportunities:
            logger.info(f"📈 Найдено {len(swing_opportunities)} swing возможностей")

        # Получаем внутридневные сигналы
        intraday_signals = await decision_maker.get_intraday_signals()
        if intraday_signals:
            logger.info(f"⚡ Найдено {len(intraday_signals)} внутридневных сигналов")

        logger.info("✅ Анализ MTF результатов завершен!")

        return {
            "status": "completed",
            "market_signals": len(market_overview) if market_overview else 0,
            "swing_opportunities": (
                len(swing_opportunities) if swing_opportunities else 0
            ),
            "intraday_signals": len(intraday_signals) if intraday_signals else 0,
        }

    except Exception as e:
        logger.error(f"❌ Ошибка в анализе MTF: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


async def validate_mtf_data(symbol: str | None = None):
    """
    Валидирует данные MTF системы

    Args:
        symbol: Конкретный символ для проверки
    """
    try:
        logger.info("🔍 Валидация MTF данных...")

        async for session in get_async_session():
            # Проверяем наличие данных в таблицах MTF
            tables = ["mtf.context", "mtf.triggers", "mtf.consensus"]

            for table in tables:
                try:
                    query = text(f"SELECT COUNT(*) FROM {table}")
                    if symbol:
                        query = text(
                            f"SELECT COUNT(*) FROM {table} WHERE symbol = :symbol"
                        )
                        result = await session.execute(query, {"symbol": symbol})
                    else:
                        result = await session.execute(query)

                    count = result.scalar()
                    logger.info(f"📊 {table}: {count} записей")

                except Exception as e:
                    logger.error(f"❌ Ошибка проверки {table}: {e}")

            # Проверяем свежесть данных
            try:
                if symbol:
                    query = text(
                        """
                        SELECT MAX(ts) as latest_ts
                        FROM mtf.consensus
                        WHERE symbol = :symbol
                    """
                    )
                    result = await session.execute(query, {"symbol": symbol})
                else:
                    query = text(
                        """
                        SELECT MAX(ts) as latest_ts
                        FROM mtf.consensus
                    """
                    )
                    result = await session.execute(query)

                latest_ts = result.scalar()

                if latest_ts:
                    from datetime import datetime

                    latest_dt = (
                        latest_ts
                        if isinstance(latest_ts, datetime)
                        else datetime.fromtimestamp(latest_ts, tz=UTC)
                    )
                    now_dt = datetime.now(UTC)
                    age_hours = (now_dt - latest_dt).total_seconds() / 3600

                    logger.info(f"🕐 Последнее обновление: {age_hours:.1f} часов назад")

                    if age_hours < 1:
                        logger.info("✅ Данные свежие")
                    elif age_hours < 24:
                        logger.warning("⚠️ Данные не очень свежие")
                    else:
                        logger.error("❌ Данные сильно устарели")
                else:
                    logger.warning("⚠️ Нет данных в consensus")

            except Exception as e:
                logger.error(f"❌ Ошибка проверки свежести данных: {e}")

        logger.info("✅ Валидация MTF данных завершена!")

        return {"status": "completed"}

    except Exception as e:
        logger.error(f"❌ Ошибка валидации MTF: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


async def cleanup_mtf_old_data(
    hours_old: int = 24, symbol: str | None = None, dry_run: bool = False
):
    """
    Очищает старые MTF данные

    Args:
        hours_old: Возраст данных в часах для удаления (по умолчанию 24)
        symbol: Конкретный символ (если None, очищаются все)
        dry_run: Только проверка без удаления
    """
    try:
        logger.info("🧹 Запуск очистки старых MTF данных...")

        if symbol:
            result = await cleanup_old_data_by_symbol(symbol, hours_old, dry_run)
        else:
            result = await cleanup_old_mtf_data(hours_old, dry_run)

        if result.get("status") == "completed":
            logger.info("✅ Очистка завершена успешно!")
            logger.info(f"   Удалено записей: {result.get('deleted_count', 0)}")
            logger.info(f"   Временная граница: {result.get('cutoff_time', 'N/A')}")
        else:
            logger.error(f"❌ Ошибка очистки: {result.get('error', 'Unknown error')}")

        return result

    except Exception as e:
        logger.error(f"❌ Ошибка в процессе очистки: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MTF управляющий файл")
    parser.add_argument(
        "--mode",
        choices=["full", "etl", "analysis", "validate", "cleanup"],
        default="full",
        help="Режим работы",
    )
    parser.add_argument("--symbol", type=str, help="Конкретный символ")
    parser.add_argument("--limit", type=int, default=20, help="Лимит сигналов")
    parser.add_argument(
        "--hours", type=int, default=24, help="Возраст данных в часах для очистки"
    )
    parser.add_argument("--dry-run", action="store_true", help="Только проверка")

    args = parser.parse_args()

    async def main():
        if args.mode == "full":
            await run_mtf_full_cycle(args.symbol, args.dry_run)
        elif args.mode == "etl":
            await run_mtf_etl_only(args.symbol, args.dry_run)
        elif args.mode == "analysis":
            await run_mtf_analysis_only(args.symbol, args.limit)
        elif args.mode == "validate":
            await validate_mtf_data(args.symbol)
        elif args.mode == "cleanup":
            await cleanup_mtf_old_data(args.hours, args.symbol, args.dry_run)

    asyncio.run(main())
