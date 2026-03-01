#!/usr/bin/env python3
"""
CLI для управления синхронизацией swap свечей.
Предоставляет команды для синхронизации, мониторинга и управления swap данными.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import text

from src.candles.sync_swap_candles import sync_swap_candles
from src.utils.session_utils import get_db_session


async def sync_all_swap(
    symbols: list[str] | None = None,
    timeframes: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """Синхронизация всех swap свечей."""
    print("🚀 Запуск синхронизации swap свечей...")

    try:
        stats = await sync_swap_candles(symbols, timeframes, config)

        print("✅ Синхронизация завершена!")
        print("📊 Статистика:")
        print(f"   • Символов обработано: {stats['total_symbols']}")
        print(f"   • Свечей синхронизировано: {stats['total_candles_synced']}")
        print(f"   • Ошибок: {stats['errors_count']}")
        print(f"   • Время выполнения: {stats['duration_seconds']:.2f} сек")
        print(f"   • Скорость: {stats['candles_per_second']:.2f} свечей/сек")

    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")
        sys.exit(1)


async def sync_specific_symbols(
    symbols: list[str], timeframes: list[str] | None = None
) -> None:
    """Синхронизация конкретных символов."""
    print(f"🎯 Синхронизация символов: {', '.join(symbols)}")

    try:
        stats = await sync_swap_candles(symbols, timeframes)

        print("✅ Синхронизация завершена!")
        print("📊 Результаты по символам:")

        for symbol, result in stats["results_by_symbol"].items():
            total_candles = sum(result.values())
            print(f"   • {symbol}: {total_candles} свечей")

    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")
        sys.exit(1)


async def show_swap_status() -> None:
    """Показывает статус swap данных в базе."""
    async with get_db_session() as session:
        try:
            # Общая статистика
            stats_query = text(
                """
                SELECT
                    COUNT(DISTINCT symbol) as total_symbols,
                    COUNT(DISTINCT timeframe) as total_timeframes,
                    COUNT(*) as total_records,
                    MIN(timestamp) as earliest_timestamp,
                    MAX(timestamp) as latest_timestamp,
                    MIN(fetched_at) as earliest_fetch,
                    MAX(fetched_at) as latest_fetch
                FROM swap_ohlcv_p
            """
            )

            result = await session.execute(stats_query)
            stats = result.fetchone()

            if not stats or stats[0] == 0:
                print("📭 Swap данных в базе не найдено")
                return

            print("📊 СТАТУС SWAP ДАННЫХ")
            print("=" * 60)
            print(f"Символов: {stats[0]}")
            print(f"Таймфреймов: {stats[1]}")
            print(f"Всего записей: {stats[2]:,}")

            if stats[3] and stats[4]:
                earliest = datetime.fromtimestamp(stats[3] / 1000)
                latest = datetime.fromtimestamp(stats[4] / 1000)
                print(
                    f"Период данных: {earliest.strftime('%Y-%m-%d %H:%M')} - {latest.strftime('%Y-%m-%d %H:%M')}"
                )

            if stats[5] and stats[6]:
                print(f"Последнее обновление: {stats[6].strftime('%Y-%m-%d %H:%M:%S')}")

            # Статистика по символам
            symbols_query = text(
                """
                SELECT
                    symbol,
                    COUNT(*) as records,
                    COUNT(DISTINCT timeframe) as timeframes,
                    MAX(fetched_at) as last_update
                FROM swap_ohlcv_p
                GROUP BY symbol
                ORDER BY records DESC
                LIMIT 10
            """
            )

            result = await session.execute(symbols_query)
            symbols = result.fetchall()

            print("\n🏆 ТОП-10 СИМВОЛОВ ПО КОЛИЧЕСТВУ ЗАПИСЕЙ")
            print("-" * 60)
            print(
                f"{'Символ':<15} {'Записей':<10} {'Таймфреймов':<12} {'Последнее обновление'}"
            )
            print("-" * 60)

            for symbol in symbols:
                print(
                    f"{symbol[0]:<15} {symbol[1]:<10,} {symbol[2]:<12} {symbol[3].strftime('%Y-%m-%d %H:%M')}"
                )

            # Статистика по таймфреймам
            timeframes_query = text(
                """
                SELECT
                    timeframe,
                    COUNT(*) as records,
                    COUNT(DISTINCT symbol) as symbols
                FROM swap_ohlcv_p
                GROUP BY timeframe
                ORDER BY records DESC
            """
            )

            result = await session.execute(timeframes_query)
            timeframes = result.fetchall()

            print("\n⏰ СТАТИСТИКА ПО ТАЙМФРЕЙМАМ")
            print("-" * 40)
            print(f"{'Таймфрейм':<12} {'Записей':<10} {'Символов'}")
            print("-" * 40)

            for tf in timeframes:
                print(f"{tf[0]:<12} {tf[1]:<10,} {tf[2]}")

        except Exception as e:
            print(f"❌ Ошибка при получении статуса: {e}")


async def show_symbol_details(symbol: str) -> None:
    """Показывает детальную информацию по символу."""
    async with get_db_session() as session:
        try:
            # Основная информация
            info_query = text(
                """
                SELECT
                    symbol,
                    COUNT(DISTINCT timeframe) as timeframes,
                    COUNT(*) as total_records,
                    MIN(timestamp) as earliest_ts,
                    MAX(timestamp) as latest_ts,
                    MIN(fetched_at) as earliest_fetch,
                    MAX(fetched_at) as latest_fetch,
                    AVG(volume) as avg_volume,
                    AVG(COALESCE(funding_rate, 0)) as avg_funding_rate,
                    COUNT(CASE WHEN funding_rate IS NOT NULL THEN 1 END) as funding_rate_records,
                    COUNT(CASE WHEN open_interest IS NOT NULL THEN 1 END) as open_interest_records
                FROM swap_ohlcv_p
                WHERE symbol = :symbol
                GROUP BY symbol
            """
            )

            result = await session.execute(info_query, {"symbol": symbol})
            info = result.fetchone()

            if not info:
                print(f"📭 Данные для символа {symbol} не найдены")
                return

            print(f"📊 ДЕТАЛЬНАЯ ИНФОРМАЦИЯ: {symbol}")
            print("=" * 60)
            print(f"Таймфреймов: {info[1]}")
            print(f"Всего записей: {info[2]:,}")

            if info[3] and info[4]:
                earliest = datetime.fromtimestamp(info[3] / 1000)
                latest = datetime.fromtimestamp(info[4] / 1000)
                print(
                    f"Период данных: {earliest.strftime('%Y-%m-%d %H:%M')} - {latest.strftime('%Y-%m-%d %H:%M')}"
                )

            if info[5] and info[6]:
                print(f"Последнее обновление: {info[6].strftime('%Y-%m-%d %H:%M:%S')}")

            print(f"Средний объем: {info[7]:.2f}")
            print(f"Средний funding rate: {info[8]:.6f}")
            print(f"Записей с funding rate: {info[9]:,}")
            print(f"Записей с open interest: {info[10]:,}")

            # Информация по таймфреймам
            timeframes_query = text(
                """
                SELECT
                    timeframe,
                    COUNT(*) as records,
                    MIN(timestamp) as earliest_ts,
                    MAX(timestamp) as latest_ts,
                    MAX(fetched_at) as last_update
                FROM swap_ohlcv_p
                WHERE symbol = :symbol
                GROUP BY timeframe
                ORDER BY timeframe
            """
            )

            result = await session.execute(timeframes_query, {"symbol": symbol})
            timeframes = result.fetchall()

            print("\n⏰ ДАННЫЕ ПО ТАЙМФРЕЙМАМ")
            print("-" * 70)
            print(
                f"{'Таймфрейм':<12} {'Записей':<10} {'Период':<30} {'Последнее обновление'}"
            )
            print("-" * 70)

            for tf in timeframes:
                earliest = datetime.fromtimestamp(tf[2] / 1000)
                latest = datetime.fromtimestamp(tf[3] / 1000)
                period = (
                    f"{earliest.strftime('%Y-%m-%d')} - {latest.strftime('%Y-%m-%d')}"
                )
                print(
                    f"{tf[0]:<12} {tf[1]:<10,} {period:<30} {tf[4].strftime('%Y-%m-%d %H:%M')}"
                )

        except Exception as e:
            print(f"❌ Ошибка при получении деталей: {e}")


async def cleanup_old_data(days: int = 30) -> None:
    """Очищает старые данные."""
    async with get_db_session() as session:
        try:
            cutoff_timestamp = int(
                (datetime.now() - timedelta(days=days)).timestamp() * 1000
            )

            # Подсчитываем количество записей для удаления
            count_query = text(
                """
                SELECT COUNT(*) FROM swap_ohlcv_p
                WHERE timestamp < :cutoff_timestamp
            """
            )

            result = await session.execute(
                count_query, {"cutoff_timestamp": cutoff_timestamp}
            )
            count = result.scalar()

            if count == 0:
                print(f"📭 Нет данных старше {days} дней для удаления")
                return

            print(f"🗑️ Удаление {count:,} записей старше {days} дней...")

            # Удаляем старые данные
            delete_query = text(
                """
                DELETE FROM swap_ohlcv_p
                WHERE timestamp < :cutoff_timestamp
            """
            )

            result = await session.execute(
                delete_query, {"cutoff_timestamp": cutoff_timestamp}
            )
            await session.commit()

            print(f"✅ Удалено {result.rowcount:,} записей")

        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при очистке данных: {e}")


async def export_symbol_data(
    symbol: str, output_file: str, timeframes: list[str] | None = None
) -> None:
    """Экспортирует данные символа в JSON файл."""
    async with get_db_session() as session:
        try:
            # Формируем запрос
            query = """
                SELECT
                    symbol, timeframe, timestamp, open, high, low, close, volume,
                    vol_ccy, vol_usd, funding_rate, open_interest,
                    long_short_ratio, long_account_ratio, short_account_ratio,
                    top_long_short_ratio, top_long_account_ratio, top_short_account_ratio,
                    fetched_at
                FROM swap_ohlcv_p
                WHERE symbol = :symbol
            """

            params = {"symbol": symbol}

            if timeframes:
                placeholders = ",".join([f"'{tf}'" for tf in timeframes])
                query += f" AND timeframe IN ({placeholders})"

            query += " ORDER BY timeframe, timestamp"

            result = await session.execute(text(query), params)
            rows = result.fetchall()

            if not rows:
                print(f"📭 Данные для символа {symbol} не найдены")
                return

            # Преобразуем в JSON
            data = []
            for row in rows:
                data.append(
                    {
                        "symbol": row[0],
                        "timeframe": row[1],
                        "timestamp": row[2],
                        "open": float(row[3]),
                        "high": float(row[4]),
                        "low": float(row[5]),
                        "close": float(row[6]),
                        "volume": float(row[7]),
                        "vol_ccy": float(row[8]) if row[8] else None,
                        "vol_usd": float(row[9]) if row[9] else None,
                        "funding_rate": float(row[10]) if row[10] else None,
                        "open_interest": float(row[11]) if row[11] else None,
                        "long_short_ratio": float(row[12]) if row[12] else None,
                        "long_account_ratio": float(row[13]) if row[13] else None,
                        "short_account_ratio": float(row[14]) if row[14] else None,
                        "top_long_short_ratio": float(row[15]) if row[15] else None,
                        "top_long_account_ratio": float(row[16]) if row[16] else None,
                        "top_short_account_ratio": float(row[17]) if row[17] else None,
                        "fetched_at": row[18].isoformat() if row[18] else None,
                    }
                )

            # Сохраняем в файл
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            print(f"✅ Экспортировано {len(data):,} записей в {output_file}")

        except Exception as e:
            print(f"❌ Ошибка при экспорте данных: {e}")


def main():
    """Главная функция CLI."""
    parser = argparse.ArgumentParser(description="CLI для управления swap свечами")
    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    # Команда sync
    sync_parser = subparsers.add_parser("sync", help="Синхронизация swap свечей")
    sync_parser.add_argument(
        "--symbols", nargs="+", help="Конкретные символы для синхронизации"
    )
    sync_parser.add_argument("--timeframes", nargs="+", help="Конкретные таймфреймы")
    sync_parser.add_argument("--config", help="Файл конфигурации JSON")

    # Команда status
    subparsers.add_parser("status", help="Показать статус swap данных")

    # Команда details
    details_parser = subparsers.add_parser(
        "details", help="Детальная информация по символу"
    )
    details_parser.add_argument("symbol", help="Символ для анализа")

    # Команда cleanup
    cleanup_parser = subparsers.add_parser("cleanup", help="Очистка старых данных")
    cleanup_parser.add_argument(
        "--days", type=int, default=30, help="Количество дней (по умолчанию: 30)"
    )

    # Команда export
    export_parser = subparsers.add_parser("export", help="Экспорт данных символа")
    export_parser.add_argument("symbol", help="Символ для экспорта")
    export_parser.add_argument("output", help="Выходной файл")
    export_parser.add_argument("--timeframes", nargs="+", help="Конкретные таймфреймы")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Загружаем конфигурацию если указана
    config = None
    if hasattr(args, "config") and args.config:
        try:
            with open(args.config) as f:
                config = json.load(f)
        except Exception as e:
            print(f"❌ Ошибка загрузки конфигурации: {e}")
            return

    # Выполняем команду
    if args.command == "sync":
        if args.symbols:
            asyncio.run(sync_specific_symbols(args.symbols, args.timeframes))
        else:
            asyncio.run(sync_all_swap(None, args.timeframes, config))
    elif args.command == "status":
        asyncio.run(show_swap_status())
    elif args.command == "details":
        asyncio.run(show_symbol_details(args.symbol))
    elif args.command == "cleanup":
        asyncio.run(cleanup_old_data(args.days))
    elif args.command == "export":
        asyncio.run(export_symbol_data(args.symbol, args.output, args.timeframes))


if __name__ == "__main__":
    main()
