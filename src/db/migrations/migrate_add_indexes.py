#!/usr/bin/env python3
"""
Миграция для добавления индексов и оптимизации запросов
"""

import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database import get_async_session

logger = logging.getLogger(__name__)


async def migrate_add_indexes():
    """Добавляет индексы для оптимизации запросов"""

    print("🔧 МИГРАЦИЯ: Добавление индексов для оптимизации")
    print("=" * 60)

    async for session in get_async_session():
        try:
            # === OHLCV TABLE INDEXES ===
            print("\n📊 Создаем индексы для таблицы ohlcv...")

            ohlcv_indexes = [
                # Основной индекс для поиска по символу и таймфрейму
                "CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_timeframe ON ohlcv(symbol, timeframe)",
                # Индекс для сортировки по времени
                "CREATE INDEX IF NOT EXISTS idx_ohlcv_ts ON ohlcv(ts)",
                # Составной индекс для быстрого поиска данных
                "CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_timeframe_ts ON ohlcv(symbol, timeframe, ts)",
                # Индекс для поиска по символу
                "CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol ON ohlcv(symbol)",
                # Индекс для поиска по таймфрейму
                "CREATE INDEX IF NOT EXISTS idx_ohlcv_timeframe ON ohlcv(timeframe)",
            ]

            for index_query in ohlcv_indexes:
                await session.execute(text(index_query))
                print(f"  ✅ {index_query}")

            # === INDICATORS TABLE INDEXES ===
            print("\n📈 Создаем индексы для таблицы indicators...")

            indicators_indexes = [
                # Основной индекс для поиска по символу и таймфрейму
                "CREATE INDEX IF NOT EXISTS idx_indicators_symbol_timeframe ON indicators(symbol, timeframe)",
                # Индекс для сортировки по времени
                "CREATE INDEX IF NOT EXISTS idx_indicators_ts ON indicators(ts)",
                # Составной индекс для быстрого поиска данных
                "CREATE INDEX IF NOT EXISTS idx_indicators_symbol_timeframe_ts ON indicators(symbol, timeframe, ts)",
                # Индекс для поиска по символу
                "CREATE INDEX IF NOT EXISTS idx_indicators_symbol ON indicators(symbol)",
                # Индекс для поиска по таймфрейму
                "CREATE INDEX IF NOT EXISTS idx_indicators_timeframe ON indicators(timeframe)",
                # Индексы для часто используемых индикаторов
                "CREATE INDEX IF NOT EXISTS idx_indicators_rsi14 ON indicators(rsi14) WHERE rsi14 IS NOT NULL",
                "CREATE INDEX IF NOT EXISTS idx_indicators_macd ON indicators(macd) WHERE macd IS NOT NULL",
                "CREATE INDEX IF NOT EXISTS idx_indicators_ema21 ON indicators(ema21) WHERE ema21 IS NOT NULL",
                "CREATE INDEX IF NOT EXISTS idx_indicators_sma50 ON indicators(sma50) WHERE sma50 IS NOT NULL",
                "CREATE INDEX IF NOT EXISTS idx_indicators_sma200 ON indicators(sma200) WHERE sma200 IS NOT NULL",
                # Индекс для времени расчета
                "CREATE INDEX IF NOT EXISTS idx_indicators_calculated_at ON indicators(calculated_at)",
            ]

            for index_query in indicators_indexes:
                await session.execute(text(index_query))
                print(f"  ✅ {index_query}")

            # === SIGNALS TABLE INDEXES ===
            print("\n🚦 Создаем индексы для таблицы signals...")

            signals_indexes = [
                # Основной индекс для поиска по символу и таймфрейму
                "CREATE INDEX IF NOT EXISTS idx_signals_symbol_timeframe ON signals(symbol, timeframe)",
                # Индекс для сортировки по времени
                "CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(ts)",
                # Составной индекс для быстрого поиска данных
                "CREATE INDEX IF NOT EXISTS idx_signals_symbol_timeframe_ts ON signals(symbol, timeframe, ts)",
                # Индекс для поиска по типу сигнала
                "CREATE INDEX IF NOT EXISTS idx_signals_signal ON signals(signal)",
                # Индекс для времени создания
                "CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals(created_at)",
            ]

            for index_query in signals_indexes:
                await session.execute(text(index_query))
                print(f"  ✅ {index_query}")

            # === SIGNALS_DETAILED TABLE INDEXES ===
            print("\n📋 Создаем индексы для таблицы signals_detailed...")

            signals_detailed_indexes = [
                # Основной индекс для поиска по символу и таймфрейму
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_symbol_timeframe ON signals_detailed(symbol, timeframe)",
                # Индекс для сортировки по времени
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_ts ON signals_detailed(ts)",
                # Составной индекс для быстрого поиска данных
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_symbol_timeframe_ts ON signals_detailed(symbol, timeframe, ts)",
                # Индекс для поиска по типу сигнала
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_signal ON signals_detailed(signal)",
                # Индексы для числовых scores
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_total_score ON signals_detailed(total_score) WHERE total_score IS NOT NULL",
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_macd_score ON signals_detailed(macd_score) WHERE macd_score IS NOT NULL",
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_rsi14_score ON signals_detailed(rsi14_score) WHERE rsi14_score IS NOT NULL",
                # Индекс для времени создания
                "CREATE INDEX IF NOT EXISTS idx_signals_detailed_created_at ON signals_detailed(created_at)",
            ]

            for index_query in signals_detailed_indexes:
                await session.execute(text(index_query))
                print(f"  ✅ {index_query}")

            # === COMBINATION_RESULTS TABLE INDEXES ===
            print("\n🔗 Создаем индексы для таблицы combination_results...")

            combination_indexes = [
                # Основной индекс для поиска по символу и таймфрейму
                "CREATE INDEX IF NOT EXISTS idx_combination_results_symbol_timeframe ON combination_results(symbol, timeframe)",
                # Индекс для сортировки по времени
                "CREATE INDEX IF NOT EXISTS idx_combination_results_ts ON combination_results(ts)",
                # Составной индекс для быстрого поиска данных
                "CREATE INDEX IF NOT EXISTS idx_combination_results_symbol_timeframe_ts ON combination_results(symbol, timeframe, ts)",
                # Индекс для поиска по названию комбинации
                "CREATE INDEX IF NOT EXISTS idx_combination_results_combination_name ON combination_results(combination_name)",
                # Индекс для силы сигнала
                "CREATE INDEX IF NOT EXISTS idx_combination_results_signal_strength ON combination_results(signal_strength) WHERE signal_strength IS NOT NULL",
                # Индекс для времени расчета
                "CREATE INDEX IF NOT EXISTS idx_combination_results_calculated_at ON combination_results(calculated_at)",
            ]

            for index_query in combination_indexes:
                await session.execute(text(index_query))
                print(f"  ✅ {index_query}")

            # === INSTRUMENTS TABLE INDEXES ===
            print("\n📋 Создаем индексы для таблицы instruments...")

            # Проверяем существование таблицы instruments
            check_table_query = text(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'instruments'
                )
            """
            )
            result = await session.execute(check_table_query)
            table_exists = result.scalar()

            if table_exists:
                # Проверяем существующие колонки
                columns_query = text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'instruments'
                    AND table_schema = 'public'
                """
                )
                result = await session.execute(columns_query)
                columns = [row[0] for row in result.fetchall()]

                instruments_indexes = []

                # Добавляем индексы только для существующих колонок
                if "insttype" in columns:
                    instruments_indexes.append(
                        "CREATE INDEX IF NOT EXISTS idx_instruments_insttype ON instruments(insttype)"
                    )

                if "state" in columns:
                    instruments_indexes.append(
                        "CREATE INDEX IF NOT EXISTS idx_instruments_state ON instruments(state)"
                    )

                if "listtime" in columns:
                    instruments_indexes.append(
                        "CREATE INDEX IF NOT EXISTS idx_instruments_listtime ON instruments(listtime)"
                    )

                for index_query in instruments_indexes:
                    await session.execute(text(index_query))
                    print(f"  ✅ {index_query}")

                if not instruments_indexes:
                    print(
                        "  ℹ️ Нет подходящих колонок для индексов в таблице instruments"
                    )
            else:
                print("  ℹ️ Таблица instruments не существует, пропускаем")

            await session.commit()
            print("\n✅ Все индексы созданы успешно!")

            # === АНАЛИЗ ПРОИЗВОДИТЕЛЬНОСТИ ===
            print("\n📊 Анализируем производительность...")

            # Проверяем количество записей в таблицах
            tables = [
                "ohlcv",
                "indicators",
                "signals",
                "signals_detailed",
                "combination_results",
            ]

            for table in tables:
                count_query = text(f"SELECT COUNT(*) FROM {table}")
                result = await session.execute(count_query)
                count = result.scalar()
                print(f"  📈 {table}: {count:,} записей")

            # Проверяем существующие индексы
            print("\n🔍 Проверяем созданные индексы...")

            for table in tables:
                indexes_query = text(
                    f"""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = '{table}'
                    ORDER BY indexname
                """
                )
                result = await session.execute(indexes_query)
                indexes = result.fetchall()

                print(f"  📋 {table}: {len(indexes)} индексов")
                for idx in indexes:
                    print(f"    - {idx.indexname}")

            print("\n🎉 Миграция индексов завершена успешно!")

        except Exception as e:
            logger.error(f"❌ Ошибка при создании индексов: {e}")
            await session.rollback()
            raise


async def analyze_query_performance():
    """Анализирует производительность запросов"""

    print("\n🔍 АНАЛИЗ ПРОИЗВОДИТЕЛЬНОСТИ ЗАПРОСОВ")
    print("=" * 60)

    async for session in get_async_session():
        try:
            # Тестируем производительность основных запросов
            test_queries = [
                {
                    "name": "Поиск символов",
                    "query": "SELECT DISTINCT symbol FROM indicators",
                    "params": {},
                },
                {
                    "name": "Поиск таймфреймов для символа",
                    "query": "SELECT DISTINCT timeframe FROM indicators WHERE symbol = :symbol",
                    "params": {"symbol": "BTC-USDT"},
                },
                {
                    "name": "Последние записи индикаторов",
                    "query": """
                        SELECT * FROM indicators
                        WHERE symbol = :symbol AND timeframe = :timeframe
                        ORDER BY ts DESC LIMIT 100
                    """,
                    "params": {"symbol": "BTC-USDT", "timeframe": "1m"},
                },
                {
                    "name": "Подсчет записей по символу",
                    "query": "SELECT COUNT(*) FROM indicators WHERE symbol = :symbol",
                    "params": {"symbol": "BTC-USDT"},
                },
            ]

            for test in test_queries:
                print(f"\n🧪 Тест: {test['name']}")

                # Выполняем запрос с EXPLAIN ANALYZE
                explain_query = text(f"EXPLAIN (ANALYZE, BUFFERS) {test['query']}")

                try:
                    result = await session.execute(explain_query, test["params"])
                    plan = result.fetchall()

                    # Извлекаем время выполнения
                    execution_time = None
                    for row in plan:
                        if "Execution Time:" in str(row[0]):
                            execution_time = (
                                str(row[0]).split("Execution Time:")[1].split()[0]
                            )
                            break

                    if execution_time:
                        print(f"  ⏱️ Время выполнения: {execution_time} мс")
                    else:
                        print("  ⏱️ Время выполнения: не определено")

                except Exception as e:
                    print(f"  ❌ Ошибка при анализе: {e}")

            print("\n✅ Анализ производительности завершен!")

        except Exception as e:
            logger.error(f"❌ Ошибка при анализе производительности: {e}")
            raise


async def optimize_table_settings():
    """Оптимизирует настройки таблиц для PostgreSQL"""

    print("\n⚙️ ОПТИМИЗАЦИЯ НАСТРОЕК ТАБЛИЦ")
    print("=" * 60)

    async for session in get_async_session():
        try:
            # Настройки для оптимизации производительности
            optimizations = [
                # Увеличиваем размер shared_buffers для кэширования
                "ALTER SYSTEM SET shared_buffers = '256MB'",
                # Настройка work_mem для операций сортировки
                "ALTER SYSTEM SET work_mem = '4MB'",
                # Настройка maintenance_work_mem для операций обслуживания
                "ALTER SYSTEM SET maintenance_work_mem = '64MB'",
                # Включаем параллельные запросы
                "ALTER SYSTEM SET max_parallel_workers_per_gather = 2",
                # Настройка эффективности WAL
                "ALTER SYSTEM SET wal_buffers = '16MB'",
                # Настройка checkpoint
                "ALTER SYSTEM SET checkpoint_completion_target = 0.9",
            ]

            print("📝 Применяем оптимизации PostgreSQL...")

            for opt in optimizations:
                try:
                    await session.execute(text(opt))
                    print(f"  ✅ {opt}")
                except Exception as e:
                    print(f"  ⚠️ Не удалось применить: {opt} - {e}")

            await session.commit()
            print("\n✅ Оптимизации применены!")
            print("💡 Перезапустите PostgreSQL для применения изменений")

        except Exception as e:
            logger.error(f"❌ Ошибка при оптимизации: {e}")
            await session.rollback()
            raise


async def main():
    """Основная функция миграции"""
    try:
        # Создаем индексы
        await migrate_add_indexes()

        # Анализируем производительность
        await analyze_query_performance()

        # Оптимизируем настройки (опционально)
        # await optimize_table_settings()

        print("\n🎉 Миграция индексов и оптимизации завершена!")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка в миграции: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
