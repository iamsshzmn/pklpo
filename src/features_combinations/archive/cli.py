#!/usr/bin/env python3
"""
CLI интерфейс для работы с комбинациями индикаторов
"""

import argparse
import asyncio
from pathlib import Path

import pandas as pd
from sqlalchemy import select

try:
    from src.database import get_async_session
    from src.models import Indicator
except Exception:
    # В автономном режиме CLI может работать без БД (через CSV/Parquet провайдер)
    get_async_session = None  # type: ignore
    Indicator = None  # type: ignore

# Импорты из локального пакета
from .calculator import CombinationCalculator, analyze_combination_performance
from .providers import FileIndicatorProvider
from .recommendations import RecommendationGenerator


async def fetch_indicators_data(
    symbol: str,
    timeframe: str,
    limit: int = 500,
    provider: FileIndicatorProvider | None = None,
) -> pd.DataFrame:
    """
    Получает данные индикаторов из базы данных

    Args:
        symbol: Символ (например, BTC-USDT)
        timeframe: Таймфрейм (например, 1m)
        limit: Количество последних записей

    Returns:
        DataFrame с индикаторами
    """
    if provider is not None:
        try:
            return provider.load(symbol, timeframe, limit)
        except Exception as e:
            print(f"❌ Ошибка загрузки из файлового провайдера: {e}")
            return pd.DataFrame()

    if get_async_session is None or Indicator is None:
        print(
            "❌ Провайдер БД недоступен. Либо укажите --provider file, либо запустите в окружении проекта."
        )
        return pd.DataFrame()

    async for session in get_async_session():
        # Получаем последние записи индикаторов
        query = (
            select(Indicator)
            .where(Indicator.symbol == symbol, Indicator.timeframe == timeframe)
            .order_by(Indicator.ts.desc())
            .limit(limit)
        )

        result = await session.execute(query)
        indicators = result.scalars().all()

        if not indicators:
            print(f"❌ Нет данных индикаторов для {symbol} {timeframe}")
            return pd.DataFrame()

        # Конвертируем в DataFrame
        data = []
        for ind in indicators:
            row = {"ts": ind.ts, "symbol": ind.symbol, "timeframe": ind.timeframe}

            # Добавляем все индикаторы
            for column in Indicator.__table__.columns:
                if column.name not in [
                    "id",
                    "ts",
                    "symbol",
                    "timeframe",
                    "calculated_at",
                ]:
                    value = getattr(ind, column.name)
                    if value is not None:
                        row[column.name] = float(value)

            data.append(row)

        df = pd.DataFrame(data)
        df = df.sort_values("ts").reset_index(drop=True)

        print(f"✅ Загружено {len(df)} записей индикаторов для {symbol} {timeframe}")
        return df
    return None


async def analyze_combinations(
    symbol: str,
    timeframe: str,
    combination_name: str | None = None,
    provider: FileIndicatorProvider | None = None,
):
    """
    Анализирует комбинации индикаторов

    Args:
        symbol: Символ для анализа
        timeframe: Таймфрейм
        combination_name: Конкретная комбинация (если None, анализирует все)
    """
    print(f"🔍 Анализ комбинаций для {symbol} {timeframe}")

    # Загружаем данные
    df = await fetch_indicators_data(symbol, timeframe, provider=provider)
    if df.empty:
        return

    # Создаем калькулятор
    calculator = CombinationCalculator()

    if combination_name:
        # Анализируем конкретную комбинацию
        print(f"\n📊 Анализ комбинации: {combination_name}")
        result = calculator.calculate_combination(df, combination_name)

        if result:
            print(f"✅ Сила сигнала: {result.signal_strength:.2f}")
            print(f"📈 Согласованные сигналы: {result.agreement_count}")
            print(f"⚠️ Конфликты: {result.conflict_count}")
            print(f"💡 Рекомендация: {result.recommendation}")

            # Генерируем комплексную рекомендацию
            comprehensive = (
                RecommendationGenerator.generate_comprehensive_recommendation(
                    result.indicators,
                    result.signal_strength,
                    result.conflict_count,
                    result.correlation_matrix,
                    timeframe,
                )
            )

            print(f"\n🎯 Торговая рекомендация: {comprehensive['trading_action']}")
            print(f"⚠️ Оценка риска: {comprehensive['risk_assessment']}")
            print(f"⏰ Совет по таймфрейму: {comprehensive['timeframe_advice']}")
            print(f"📊 Уровень уверенности: {comprehensive['confidence_level']}")

            # Показываем корреляционную матрицу
            print("\n📊 Корреляционная матрица:")
            print(result.correlation_matrix.round(3))
        else:
            print(f"❌ Не удалось рассчитать комбинацию {combination_name}")
    else:
        # Анализируем все комбинации
        print("\n📊 Анализ всех комбинаций:")
        results = calculator.calculate_all_combinations(df)

        if results:
            # Экспортируем в DataFrame для красивого вывода
            analysis_df = calculator.export_combination_analysis(results)
            print(analysis_df.to_string(index=False))

            # Показываем лучшие комбинации
            print("\n🏆 Топ-3 лучшие комбинации:")
            for i, result in enumerate(results[:3], 1):
                print(
                    f"{i}. {result.combination_name}: {result.signal_strength:.2f} - {result.recommendation}"
                )
        else:
            print("❌ Не удалось рассчитать ни одной комбинации")


async def performance_analysis(
    symbol: str,
    timeframe: str,
    combination_name: str,
    periods: int = 100,
    provider: FileIndicatorProvider | None = None,
):
    """
    Анализирует производительность комбинации на исторических данных

    Args:
        symbol: Символ для анализа
        timeframe: Таймфрейм
        combination_name: Название комбинации
        periods: Количество периодов для анализа
    """
    print(f"📈 Анализ производительности {combination_name} для {symbol} {timeframe}")

    # Загружаем данные
    df = await fetch_indicators_data(
        symbol, timeframe, limit=periods + 50, provider=provider
    )
    if df.empty:
        return

    # Анализируем производительность
    performance = analyze_combination_performance(df, combination_name, periods)

    if "error" in performance:
        print(f"❌ Ошибка: {performance['error']}")
        return

    print("\n📊 Результаты анализа производительности:")
    print(f"📈 Всего сигналов: {performance['total_signals']}")
    print(f"🟢 Сильных сигналов: {performance['strong_signals']}")
    print(f"🔴 Слабых сигналов: {performance['weak_signals']}")
    print(f"📊 Средняя сила сигнала: {performance['avg_strength']:.2f}")
    print(f"🎯 Процент успешных сигналов: {performance['success_rate']:.1%}")


async def list_combinations():
    """Показывает список всех доступных комбинаций"""
    calculator = CombinationCalculator()

    print("📋 Доступные комбинации индикаторов:")
    print("=" * 80)

    for name, config in calculator.combinations.items():
        print(f"\n🔹 {name}")
        print(f"   Индикаторы: {', '.join(config['indicators'])}")
        print(f"   Роли: {', '.join(config['roles'])}")
        print(f"   Описание: {config['description']}")
        print("-" * 80)


def main():
    """Основная функция CLI"""
    parser = argparse.ArgumentParser(
        description="Анализ комбинаций технических индикаторов"
    )

    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    # Общие опции провайдера файлов
    def add_provider_flags(p):
        p.add_argument(
            "--provider", choices=["db", "file"], default="file", help="Источник данных"
        )
        p.add_argument("--input-path", help="Путь к директории с файлами индикаторов")
        p.add_argument("--format", choices=["csv", "parquet"], default="parquet")
        p.add_argument("--ts-col", default="ts")

    # Команда анализа
    analyze_parser = subparsers.add_parser("analyze", help="Анализ комбинаций")
    analyze_parser.add_argument("symbol", help="Символ (например, BTC-USDT)")
    analyze_parser.add_argument("timeframe", help="Таймфрейм (например, 1m)")
    analyze_parser.add_argument("--combination", "-c", help="Конкретная комбинация")
    add_provider_flags(analyze_parser)

    # Команда производительности
    perf_parser = subparsers.add_parser("performance", help="Анализ производительности")
    perf_parser.add_argument("symbol", help="Символ")
    perf_parser.add_argument("timeframe", help="Таймфрейм")
    perf_parser.add_argument("combination", help="Название комбинации")
    perf_parser.add_argument(
        "--periods", "-p", type=int, default=100, help="Количество периодов"
    )
    add_provider_flags(perf_parser)

    # Команда списка
    subparsers.add_parser("list", help="Список доступных комбинаций")

    args = parser.parse_args()

    def build_provider(args) -> FileIndicatorProvider | None:
        if getattr(args, "provider", "file") == "file":
            if not args.input_path:
                return None
            return FileIndicatorProvider(
                Path(args.input_path), file_format=args.format, ts_col=args.ts_col
            )
        return None

    if args.command == "analyze":
        provider = build_provider(args)
        asyncio.run(
            analyze_combinations(
                args.symbol, args.timeframe, args.combination, provider
            )
        )
    elif args.command == "performance":
        provider = build_provider(args)
        asyncio.run(
            performance_analysis(
                args.symbol, args.timeframe, args.combination, args.periods, provider
            )
        )
    elif args.command == "list":
        asyncio.run(list_combinations())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
