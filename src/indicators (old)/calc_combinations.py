#!/usr/bin/env python3
"""
Модуль для расчёта комбинаций индикаторов (оптимизированная версия)
Интегрирован в основной цикл системы
"""

import asyncio
import json
import logging
import multiprocessing
import time
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import insert, select, text
from tqdm import tqdm

from src.database import get_async_session
from src.models import CombinationResult, Indicator

from .combinations.calculator import CombinationCalculator

logger = logging.getLogger(__name__)
# Настраиваем логгер для записи только в файл, а не в консоль
logger.setLevel(logging.DEBUG)
# Удаляем все существующие обработчики
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
# Добавляем только файловый обработчик
file_handler = logging.FileHandler("combinations_calculator.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


# Функции для управления логированием
def enable_verbose_logging():
    """Включает подробное логирование в консоль"""
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def disable_verbose_logging():
    """Отключает подробное логирование в консоль"""
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            logger.removeHandler(handler)


BATCH_SIZE = 1000  # размер пакета для обработки
MAX_WORKERS = min(multiprocessing.cpu_count(), 12)  # количество параллельных потоков
CHUNK_SIZE = 10  # размер пакета для параллельной обработки


async def fetch_indicators_data(
    symbol: str, timeframe: str, limit: int = 500
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
    async for session in get_async_session():
        try:
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
                logger.warning(f"Нет данных индикаторов для {symbol} {timeframe}")
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

            logger.debug(
                f"Загружено {len(df)} записей индикаторов для {symbol} {timeframe}"
            )
            return df

        except Exception as e:
            logger.error(f"Ошибка при загрузке данных индикаторов: {e}")
            return pd.DataFrame()
    return None


async def get_symbols_to_process(symbol=None) -> list[str]:
    """
    Получить список символов для обработки комбинаций.

    Args:
        symbol: Конкретный символ (если None, обрабатываются все)

    Returns:
        List[str]: Список символов для обработки
    """
    async for session in get_async_session():
        try:
            if symbol:
                # Обрабатываем конкретный символ
                symbols = [symbol]
            else:
                # Получаем список всех символов
                query = text("SELECT DISTINCT symbol FROM indicators")
                result = await session.execute(query)
                symbols = [row[0] for row in result.fetchall()]

            # Логируем только в файл для отладки
            logger.debug(f"📊 Найдено {len(symbols)} символов для обработки комбинаций")
            return symbols

        except Exception as e:
            logger.error(f"❌ Ошибка при получении символов: {e}")
            return []
    return None


async def get_timeframes_for_symbol(session, symbol: str) -> list[str]:
    """
    Получить таймфреймы для символа.

    Args:
        session: Сессия БД
        symbol: Символ

    Returns:
        List[str]: Список таймфреймов
    """
    try:
        query = text("SELECT DISTINCT timeframe FROM indicators WHERE symbol = :symbol")
        result = await session.execute(query, {"symbol": symbol})
        return [row[0] for row in result.fetchall()]
    except Exception as e:
        logger.error(f"❌ Ошибка при получении таймфреймов для {symbol}: {e}")
        return []


async def process_single_symbol_timeframe(
    symbol: str, timeframe: str
) -> tuple[bool, int, float, list[str]]:
    """
    Обработать один символ-таймфрейм с улучшенной обработкой ошибок.

    Args:
        symbol: Символ
        timeframe: Таймфрейм

    Returns:
        Tuple[bool, int, float, List[str]]: (успех, количество комбинаций, время, ошибки)
    """
    start_time = time.time()
    errors = []

    try:
        # Отключаем подробное логирование для консоли во время расчетов
        disable_verbose_logging()

        result = await calculate_combinations_for_symbol(symbol, timeframe)
        combinations_count = result.get("total_combinations", 0) if result else 0
        calculation_time = time.time() - start_time
        return True, combinations_count, calculation_time, errors

    except Exception as e:
        errors.append(str(e))
        calculation_time = time.time() - start_time
        return False, 0, calculation_time, errors


async def process_chunk_parallel(
    chunk: list[tuple[str, str]],
) -> list[tuple[bool, int, float, list[str]]]:
    """
    Обработать пакет пар параллельно.

    Args:
        chunk: Список пар (symbol, timeframe) для обработки

    Returns:
        List[Tuple[bool, int, float, List[str]]]: Результаты обработки
    """

    async def process_with_session(symbol: str, timeframe: str):
        return await process_single_symbol_timeframe(symbol, timeframe)

    # Создаём задачи для параллельного выполнения
    tasks = [process_with_session(symbol, timeframe) for symbol, timeframe in chunk]

    # Выполняем параллельно
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Обрабатываем результаты
    processed_results = []
    for _i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append((False, 0, 0.0, [str(result)]))
        else:
            processed_results.append(result)

    return processed_results


async def calculate_combinations_for_symbol(symbol: str, timeframe: str) -> dict:
    """
    Рассчитывает комбинации индикаторов для конкретного символа и таймфрейма

    Args:
        symbol: Символ для анализа
        timeframe: Таймфрейм

    Returns:
        Словарь с результатами анализа комбинаций
    """
    # Логируем только в файл для отладки
    logger.debug(f"🔍 Расчёт комбинаций для {symbol} {timeframe}")

    # Загружаем данные индикаторов из БД
    df = await fetch_indicators_data(symbol, timeframe)
    if df.empty:
        logger.debug(f"Нет данных для анализа комбинаций {symbol} {timeframe}")
        return {}

    # Создаем калькулятор комбинаций
    calculator = CombinationCalculator()

    # Рассчитываем все комбинации
    results = calculator.calculate_all_combinations(df)

    if not results:
        logger.debug(f"Не удалось рассчитать комбинации для {symbol} {timeframe}")
        return {}

    # Формируем отчёт
    report = {
        "symbol": symbol,
        "timeframe": timeframe,
        "total_combinations": len(results),
        "best_combinations": [],
        "summary": {},
    }

    # Добавляем лучшие комбинации
    for i, result in enumerate(results[:5], 1):
        report["best_combinations"].append(
            {
                "rank": i,
                "name": result.combination_name,
                "signal_strength": result.signal_strength,
                "agreements": result.agreement_count,
                "conflicts": result.conflict_count,
                "recommendation": result.recommendation,
            }
        )

    # Добавляем общую статистику
    strengths = [r.signal_strength for r in results]
    report["summary"] = {
        "avg_strength": sum(strengths) / len(strengths) if strengths else 0,
        "max_strength": max(strengths) if strengths else 0,
        "strong_signals": len([s for s in strengths if s >= 0.7]),
        "weak_signals": len([s for s in strengths if s < 0.4]),
    }

    logger.debug(f"✅ Рассчитано {len(results)} комбинаций для {symbol} {timeframe}")

    # Сохраняем результаты в базу данных
    await save_combination_results(symbol, timeframe, results, df)

    return report


async def save_combination_results(
    symbol: str, timeframe: str, results: list, df: pd.DataFrame
):
    """
    Сохраняет результаты комбинаций в базу данных (оптимизированная версия с batch операциями)

    Args:
        symbol: Символ
        timeframe: Таймфрейм
        results: Список результатов комбинаций
        df: DataFrame с индикаторами
    """
    if not results:
        return

    async for session in get_async_session():
        try:
            # Получаем последний timestamp
            latest_ts = df.iloc[-1]["ts"] if not df.empty else 0

            # Удаляем старые результаты для этого символа/таймфрейма
            delete_query = text(
                """
                DELETE FROM combination_results
                WHERE symbol = :symbol AND timeframe = :timeframe
            """
            )
            await session.execute(
                delete_query, {"symbol": symbol, "timeframe": timeframe}
            )

            # Подготавливаем данные для batch вставки
            records_to_insert = []
            for result in results:
                record = {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "ts": latest_ts,
                    "combination_name": result.combination_name,
                    "signal_strength": float(result.signal_strength),
                    "agreement_count": result.agreement_count,
                    "conflict_count": result.conflict_count,
                    "recommendation": result.recommendation,
                    "trading_action": "Анализ завершен",
                    "risk_assessment": "Требует дополнительного анализа",
                    "timeframe_advice": f"Таймфрейм: {timeframe}",
                    "confidence_level": f"{result.signal_strength:.1%}",
                    "indicators_used": json.dumps(result.indicators),
                    "calculated_at": datetime.now(UTC),
                }
                records_to_insert.append(record)

            # Batch вставка для улучшения производительности
            if records_to_insert:
                # Разбиваем на пакеты если много записей
                batch_size = BATCH_SIZE
                for i in range(0, len(records_to_insert), batch_size):
                    batch = records_to_insert[i : i + batch_size]
                    await session.execute(insert(CombinationResult), batch)

                await session.commit()
                logger.debug(
                    f"💾 Сохранено {len(records_to_insert)} результатов комбинаций в БД"
                )

        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении результатов комбинаций: {e}")
            await session.rollback()


async def get_symbols_timeframes_to_analyze(
    symbol: str | None = None,
) -> list[tuple]:
    """
    Получает список пар (symbol, timeframe) для анализа комбинаций

    Args:
        symbol: Конкретный символ (если None, все символы)

    Returns:
        Список кортежей (symbol, timeframe)
    """
    async for session in get_async_session():
        try:
            if symbol:
                # Получаем таймфреймы для конкретного символа
                query = text(
                    "SELECT DISTINCT timeframe FROM indicators WHERE symbol = :symbol"
                )
                result = await session.execute(query, {"symbol": symbol})
                timeframes = [row[0] for row in result.fetchall()]
                return [(symbol, tf) for tf in timeframes]
            # Получаем все пары symbol-timeframe
            query = text("SELECT DISTINCT symbol, timeframe FROM indicators")
            result = await session.execute(query)
            return [(row[0], row[1]) for row in result.fetchall()]

        except Exception as e:
            logger.error(f"Ошибка при получении списка символов: {e}")
            return []
    return None


async def calculate_combinations_for_all(symbol: str | None = None) -> dict:
    """
    Рассчитывает комбинации для всех символов с улучшенной статистикой.

    Args:
        symbol: Конкретный символ (если None, обрабатываются все)

    Returns:
        dict: Статистика обработки
    """
    logger.info("🚀 Запуск расчёта комбинаций индикаторов...")
    # Включаем подробное логирование для основных сообщений
    enable_verbose_logging()

    # Получаем символы для обработки
    symbols = await get_symbols_to_process(symbol)
    if not symbols:
        logger.warning("⚠️ Нет символов для обработки")
        return {"status": "no_symbols", "processed": 0, "combinations": 0, "errors": 0}

    # Получаем таймфреймы для каждого символа
    symbol_timeframes = []
    async for session in get_async_session():
        try:
            for sym in symbols:
                timeframes = await get_timeframes_for_symbol(session, sym)
                for tf in timeframes:
                    symbol_timeframes.append((sym, tf))
            break
        except Exception as e:
            logger.error(f"❌ Ошибка при получении таймфреймов: {e}")
            return {"status": "error", "processed": 0, "combinations": 0, "errors": 1}

    if not symbol_timeframes:
        logger.warning("⚠️ Нет пар symbol-timeframe для обработки")
        return {"status": "no_data", "processed": 0, "combinations": 0, "errors": 0}

    logger.debug(
        f"📊 Найдено {len(symbol_timeframes)} пар symbol-timeframe для обработки"
    )

    total_combinations = 0
    total_processed = 0
    total_errors = 0
    all_reports = []

    with tqdm(
        total=len(symbol_timeframes),
        desc="🔗 Обработка комбинаций",
        ncols=120,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        position=0,
        leave=True,
        dynamic_ncols=True,
    ) as pbar:
        for symbol, timeframe in symbol_timeframes:
            # Обрабатываем пару с улучшенной обработкой ошибок
            (
                success,
                combinations_count,
                calculation_time,
                errors,
            ) = await process_single_symbol_timeframe(symbol, timeframe)

            if success:
                total_processed += 1
                total_combinations += combinations_count
                # Убираем избыточное логирование для ускорения и видимости прогресс бара
                # logger.info(f"✅ {symbol} {timeframe}: {combinations_count} комбинаций за {calculation_time:.2f}с")
            else:
                total_errors += 1
                logger.error(f"❌ Ошибка при обработке {symbol} {timeframe}: {errors}")

            pbar.update(1)
            pbar.set_postfix(
                {
                    "Обработано": f"{total_processed}/{len(symbol_timeframes)}",
                    "Комбинаций": total_combinations,
                    "Ошибок": total_errors,
                }
            )

    # Итоговая статистика
    logger.info("=" * 60)
    logger.info("📊 ИТОГОВАЯ СТАТИСТИКА ОБРАБОТКИ КОМБИНАЦИЙ:")
    logger.info(f"📋 Всего пар symbol-timeframe: {len(symbol_timeframes)}")
    logger.info(f"✅ Успешно обработано: {total_processed}")
    logger.info(f"🔗 Всего комбинаций создано: {total_combinations}")
    logger.info(f"❌ Ошибок: {total_errors}")

    if total_processed > 0:
        success_rate = total_processed / len(symbol_timeframes) * 100
        logger.info(f"📈 Успешность: {success_rate:.1f}%")

        # Дополнительная статистика
        if all_reports:
            avg_strength = sum(r["summary"]["avg_strength"] for r in all_reports) / len(
                all_reports
            )
            logger.info(f"📊 Средняя сила сигнала: {avg_strength:.2f}")

    logger.info("🎉 Расчёт комбинаций завершён успешно!")

    return {
        "status": "completed",
        "processed": total_processed,
        "combinations": total_combinations,
        "errors": total_errors,
        "total_pairs": len(symbol_timeframes),
        "reports": all_reports,
    }


async def calculate_combinations_for_all_parallel(symbol: str | None = None) -> dict:
    """
    Рассчитывает комбинации для всех символов с параллельной обработкой.

    Args:
        symbol: Конкретный символ (если None, обрабатываются все)

    Returns:
        dict: Статистика обработки
    """
    logger.info("🚀 Запуск параллельного расчёта комбинаций...")
    logger.info(f"⚡ Используем {MAX_WORKERS} параллельных потоков")
    # Включаем подробное логирование для основных сообщений
    enable_verbose_logging()

    # Получаем символы для обработки
    symbols = await get_symbols_to_process(symbol)
    if not symbols:
        logger.warning("⚠️ Нет символов для обработки")
        return {"status": "no_symbols", "processed": 0, "combinations": 0, "errors": 0}

    # Получаем таймфреймы для каждого символа
    symbol_timeframes = []
    async for session in get_async_session():
        try:
            for sym in symbols:
                timeframes = await get_timeframes_for_symbol(session, sym)
                for tf in timeframes:
                    symbol_timeframes.append((sym, tf))
            break
        except Exception as e:
            logger.error(f"❌ Ошибка при получении таймфреймов: {e}")
            return {"status": "error", "processed": 0, "combinations": 0, "errors": 1}

    if not symbol_timeframes:
        logger.warning("⚠️ Нет пар symbol-timeframe для обработки")
        return {"status": "no_data", "processed": 0, "combinations": 0, "errors": 0}

    logger.debug(
        f"📊 Найдено {len(symbol_timeframes)} пар symbol-timeframe для обработки"
    )

    # Разбиваем на пакеты для параллельной обработки
    chunks = [
        symbol_timeframes[i : i + CHUNK_SIZE]
        for i in range(0, len(symbol_timeframes), CHUNK_SIZE)
    ]

    total_combinations = 0
    total_processed = 0
    total_errors = 0
    all_reports = []

    with tqdm(
        total=len(symbol_timeframes),
        desc="🔗 Параллельная обработка комбинаций",
        ncols=120,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        position=0,
        leave=True,
        dynamic_ncols=True,
        disable=False,
    ) as pbar:
        for chunk_idx, chunk in enumerate(chunks):
            # Обрабатываем пакет параллельно
            chunk_results = await process_chunk_parallel(chunk)

            # Обрабатываем результаты пакета
            for i, (
                success,
                combinations_count,
                _calculation_time,
                errors,
            ) in enumerate(chunk_results):
                symbol, timeframe = chunk[i]

                if success:
                    total_processed += 1
                    total_combinations += combinations_count
                    # Убираем избыточное логирование для ускорения и видимости прогресс бара
                    # logger.info(f"✅ {symbol} {timeframe}: {combinations_count} комбинаций за {calculation_time:.2f}с")
                else:
                    total_errors += 1
                    logger.error(
                        f"❌ Ошибка при обработке {symbol} {timeframe}: {errors}"
                    )

                pbar.update(1)
                pbar.set_postfix(
                    {
                        "Обработано": f"{total_processed}/{len(symbol_timeframes)}",
                        "Комбинаций": total_combinations,
                        "Ошибок": total_errors,
                        "Пакет": f"{chunk_idx + 1}/{len(chunks)}",
                    }
                )

    # Итоговая статистика
    logger.info("=" * 60)
    logger.info("📊 ИТОГОВАЯ СТАТИСТИКА ПАРАЛЛЕЛЬНОЙ ОБРАБОТКИ КОМБИНАЦИЙ:")
    logger.info(f"📋 Всего пар symbol-timeframe: {len(symbol_timeframes)}")
    logger.info(f"✅ Успешно обработано: {total_processed}")
    logger.info(f"🔗 Всего комбинаций создано: {total_combinations}")
    logger.info(f"❌ Ошибок: {total_errors}")

    if total_processed > 0:
        success_rate = total_processed / len(symbol_timeframes) * 100
        logger.info(f"📈 Успешность: {success_rate:.1f}%")

    logger.info("🎉 Параллельный расчёт комбинаций завершён успешно!")

    return {
        "status": "completed",
        "processed": total_processed,
        "combinations": total_combinations,
        "errors": total_errors,
        "total_pairs": len(symbol_timeframes),
        "reports": all_reports,
    }


async def main(symbol: str | None = None):
    """
    Основная функция для расчёта комбинаций индикаторов (оптимизированная версия)

    Args:
        symbol: Конкретный символ для анализа (если None, анализируются все)
    """
    try:
        result = await calculate_combinations_for_all(symbol)

        if result.get("status") == "completed":
            logger.info("🎉 Анализ комбинаций завершён успешно!")
        elif result.get("status") == "no_data":
            logger.info("ℹ️ Нет данных для анализа комбинаций")
        else:
            logger.warning(f"⚠️ Анализ завершился со статусом: {result.get('status')}")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при расчёте комбинаций: {e}")
        raise


async def main_parallel(symbol: str | None = None):
    """
    Основная функция для расчёта комбинаций индикаторов (параллельная версия)

    Args:
        symbol: Конкретный символ для анализа (если None, анализируются все)
    """
    try:
        result = await calculate_combinations_for_all_parallel(symbol)

        if result.get("status") == "completed":
            logger.info("🎉 Параллельный анализ комбинаций завершён успешно!")
        elif result.get("status") == "no_data":
            logger.info("ℹ️ Нет данных для анализа комбинаций")
        else:
            logger.warning(f"⚠️ Анализ завершился со статусом: {result.get('status')}")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при расчёте комбинаций: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
