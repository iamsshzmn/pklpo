import asyncio
import logging
import multiprocessing
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from tqdm import tqdm

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database import get_async_session
from src.db.db_schema_utils import ensure_columns
from src.models import OHLCV, Indicator

from .indicator_utils import calc_indicators
from .indicators_logging import (
    log_batch_progress,
    log_batch_start,
    log_indicator_calculation,
    log_session_summary,
    reset_session_stats,
)
from .registry import AVAILABLE_INDICATORS

BATCH_SIZE = 200  # Оптимизированный размер пакета (уменьшен с 500)
MAX_WORKERS = min(multiprocessing.cpu_count(), 12)  # количество параллельных потоков
CHUNK_SIZE = 20  # размер пакета для параллельной обработки


async def get_symbol_timeframes_to_update(session):
    """Получить все пары (symbol, timeframe) для обновления"""
    subq = (
        select(
            Indicator.symbol,
            Indicator.timeframe,
            func.max(Indicator.ts).label("max_ts"),
        )
        .group_by(Indicator.symbol, Indicator.timeframe)
        .subquery()
    )

    # Исправляем сравнение: ohlcv.ts в миллисекундах, indicators.ts в секундах
    # Конвертируем ohlcv.ts в секунды для корректного сравнения
    q = (
        select(OHLCV.symbol, OHLCV.timeframe)
        .outerjoin(
            subq,
            (OHLCV.symbol == subq.c.symbol) & (OHLCV.timeframe == subq.c.timeframe),
        )
        .where(OHLCV.ts / 1000 > func.coalesce(subq.c.max_ts, 0))
        .group_by(OHLCV.symbol, OHLCV.timeframe)
    )
    result = await session.execute(q)
    return result.all()


async def fetch_ohlcv_df(session, symbol, timeframe, since_ts=None, limit=BATCH_SIZE):
    """Получить OHLCV данные для символа и таймфрейма"""
    q = (
        select(OHLCV)
        .where(OHLCV.symbol == symbol, OHLCV.timeframe == timeframe)
        .order_by(OHLCV.ts.desc())
    )
    if since_ts:
        # since_ts в секундах, ohlcv.ts в миллисекундах
        q = q.where(OHLCV.ts > since_ts * 1000)
    q = q.limit(limit)
    result = await session.execute(q)
    rows = result.scalars().all()
    if not rows:
        return None

    df = pd.DataFrame(
        [
            {
                "ts": r.ts // 1000,  # Конвертируем миллисекунды в секунды
                "open": float(r.open),
                "high": float(r.high),
                "low": float(r.low),
                "close": float(r.close),
                "volume": float(r.volume),
            }
            for r in reversed(rows)
        ]
    )

    # Добавляем метаданные для лучшего логирования
    df.name = symbol
    df.timeframe = timeframe

    return df


async def upsert_indicators(session, symbol, timeframe, ind_df):
    """Сохранить индикаторы в базу данных (оптимизированная версия с batch UPSERT)"""
    import datetime

    # Подготавливаем все данные для batch insert
    batch_data = []
    for _, row in ind_df.iterrows():
        base_data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "ts": int(row["ts"]),
            "calculated_at": datetime.datetime.utcnow(),
        }

        # Добавляем все индикаторы
        indicator_data = {**base_data}
        for col in ind_df.columns:
            if col != "ts":
                value = row[col]
                # Проверяем на NaN, None и другие невалидные значения
                if pd.isna(value) or value is None:
                    continue
                try:
                    indicator_data[col] = float(value)
                except (ValueError, TypeError):
                    # Пропускаем невалидные значения
                    continue

        batch_data.append(indicator_data)

    # Batch UPSERT для улучшения производительности
    if batch_data:
        stmt = pg_insert(Indicator).values(batch_data)

        # Создаем словарь для обновления, исключая проблемные колонки
        update_dict = {}
        for k in batch_data[0]:
            if k not in ["symbol", "timeframe", "ts"]:
                update_dict[k] = stmt.excluded[k]

        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "timeframe", "ts"], set_=update_dict
        )
        await session.execute(stmt)
        await session.commit()


async def process_single_pair(
    session, symbol: str, timeframe: str
) -> tuple[bool, int, float, list[str]]:
    """Обработать одну пару symbol-timeframe с улучшенной обработкой ошибок"""
    start_time = time.time()
    errors = []

    try:
        # Получить max(ts) для этой пары из indicators
        subq = select(func.max(Indicator.ts)).where(
            Indicator.symbol == symbol, Indicator.timeframe == timeframe
        )
        result = await session.execute(subq)
        max_ts = result.scalar() or 0

        # Получить OHLCV данные
        df = await fetch_ohlcv_df(session, symbol, timeframe, since_ts=max_ts)
        if df is None or len(df) < 20:
            return False, 0, time.time() - start_time, ["Недостаточно данных"]

        # Рассчитать индикаторы
        ind_df = calc_indicators(df, AVAILABLE_INDICATORS)

        # Убедиться что все колонки существуют
        await ensure_columns(session, "indicators", ind_df.columns)

        # Сохранить индикаторы
        await upsert_indicators(session, symbol, timeframe, ind_df)

        calculation_time = time.time() - start_time
        return True, len(ind_df), calculation_time, errors

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
        async for session in get_async_session():
            return await process_single_pair(session, symbol, timeframe)
        return None

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


async def main(symbol=None, cleanup_old=True, cleanup_hours=24):
    """Основная функция с оптимизированной обработкой"""
    # Сбрасываем статистику сессии
    reset_session_stats()

    # Используем только новый логгер indicators
    indicators_logger = logging.getLogger("indicators")
    indicators_logger.info("🚀 Запуск расчёта технических индикаторов...")

    # Очистка старых данных перед расчетом
    if cleanup_old:
        await cleanup_old_indicators(cleanup_hours)

    async for session in get_async_session():
        if symbol:
            # Если указан конкретный символ, получаем только его таймфреймы
            pairs = await get_symbol_timeframes_to_update(session)
            pairs = [(s, tf) for s, tf in pairs if s == symbol]
            indicators_logger.info(
                f"📊 Найдено {len(pairs)} пар (symbol, timeframe) для обновления индикаторов символа {symbol}."
            )
        else:
            pairs = await get_symbol_timeframes_to_update(session)
            indicators_logger.info(
                f"📊 Найдено {len(pairs)} пар (symbol, timeframe) для обновления индикаторов."
            )

        if not pairs:
            indicators_logger.info("✅ Нет данных для обновления индикаторов.")
            return

        # Сортируем по алфавиту (symbol, timeframe)
        pairs = sorted(pairs, key=lambda x: (x[0], x[1]))

        # Логируем начало пакетной обработки
        symbols = list({p[0] for p in pairs})
        log_batch_start(len(pairs), symbols)

        # Добавляем прогресс-бар
        total_processed = 0
        total_indicators = 0
        total_errors = 0

        with tqdm(
            total=len(pairs), desc="📈 Обработка пар symbol-timeframe", ncols=100
        ) as pbar:
            for symbol, timeframe in pairs:
                # Обрабатываем пару с улучшенной обработкой ошибок
                (
                    success,
                    indicators_count,
                    calculation_time,
                    errors,
                ) = await process_single_pair(session, symbol, timeframe)

                if success:
                    total_processed += 1
                    total_indicators += indicators_count
                    log_indicator_calculation(
                        symbol, timeframe, indicators_count, calculation_time, errors
                    )
                else:
                    total_errors += 1
                    indicators_logger.error(
                        f"❌ Ошибка при обработке {symbol} {timeframe}: {errors}"
                    )

                pbar.update(1)
                pbar.set_postfix(
                    {
                        "Обработано": f"{total_processed}/{len(pairs)}",
                        "Индикаторов": total_indicators,
                        "Ошибок": total_errors,
                        "Текущий": f"{symbol} {timeframe}",
                    }
                )

                # Логируем прогресс
                log_batch_progress(total_processed, len(pairs), symbol, timeframe)

        # Вывести SELECT COUNT(*) FROM indicators
        count_q = select(func.count()).select_from(Indicator)
        result = await session.execute(count_q)
        count = result.scalar()

        # Логируем сводку сессии
        log_session_summary()

        # Финальная статистика
        indicators_logger.info("🎉 Расчёт индикаторов завершён успешно!")
        indicators_logger.info(f"📊 Обработано пар symbol-timeframe: {total_processed}")
        indicators_logger.info(f"📊 Всего индикаторов рассчитано: {total_indicators}")
        indicators_logger.info(f"📊 Ошибок: {total_errors}")
        indicators_logger.info(f"📊 Всего записей в таблице indicators: {count}")

        # Выводим только итоговую статистику в терминал
        print(f"✅ Обработано пар: {total_processed}")
        print(f"📊 Всего индикаторов: {total_indicators}")
        print(f"❌ Ошибок: {total_errors}")
        print(f"📈 Всего записей в таблице: {count}")


async def cleanup_old_indicators(hours_old=24):
    """
    Очистка старых данных из таблицы indicators

    Args:
        hours_old: Удалять данные старше указанного количества часов (по умолчанию 24)
    """
    indicators_logger = logging.getLogger("indicators")
    indicators_logger.info(f"🧹 Очистка данных indicators старше {hours_old} часов...")

    async for session in get_async_session():
        try:
            # Получаем количество записей до очистки
            result = await session.execute(select(func.count()).select_from(Indicator))
            count_before = result.scalar()

            # Вычисляем временную границу
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)

            # Удаляем старые записи
            delete_query = text(
                """
                DELETE FROM indicators
                WHERE calculated_at < :cutoff_time
            """
            )

            result = await session.execute(delete_query, {"cutoff_time": cutoff_time})
            deleted_count = result.rowcount

            await session.commit()

            # Получаем количество записей после очистки
            result = await session.execute(select(func.count()).select_from(Indicator))
            count_after = result.scalar()

            indicators_logger.info("✅ Очистка завершена!")
            indicators_logger.info(f"📊 Удалено записей: {deleted_count:,}")
            indicators_logger.info(f"📊 Было записей: {count_before:,}")
            indicators_logger.info(f"📊 Осталось записей: {count_after:,}")

            return deleted_count

        except Exception as e:
            indicators_logger.error(f"❌ Ошибка при очистке старых данных: {e}")
            await session.rollback()
            raise
    return None


async def main_parallel(symbol=None, cleanup_old=True, cleanup_hours=24):
    """
    Основная функция с параллельной обработкой.

    Args:
        symbol: Конкретный символ (если None, обрабатываются все)
        cleanup_old: Очищать ли старые данные перед расчетом (по умолчанию True)
        cleanup_hours: Удалять данные старше указанного количества часов (по умолчанию 24)
    """
    # Сбрасываем статистику сессии
    reset_session_stats()

    # Используем только новый логгер indicators
    indicators_logger = logging.getLogger("indicators")
    indicators_logger.info("🚀 Запуск параллельного расчёта технических индикаторов...")
    indicators_logger.info(f"⚡ Используем {MAX_WORKERS} параллельных потоков")

    # Очистка старых данных перед расчетом
    if cleanup_old:
        await cleanup_old_indicators(cleanup_hours)

    async for session in get_async_session():
        if symbol:
            # Если указан конкретный символ, получаем только его таймфреймы
            pairs = await get_symbol_timeframes_to_update(session)
            pairs = [(s, tf) for s, tf in pairs if s == symbol]
            indicators_logger.info(
                f"📊 Найдено {len(pairs)} пар (symbol, timeframe) для обновления индикаторов символа {symbol}."
            )
        else:
            pairs = await get_symbol_timeframes_to_update(session)
            indicators_logger.info(
                f"📊 Найдено {len(pairs)} пар (symbol, timeframe) для обновления индикаторов."
            )

        if not pairs:
            indicators_logger.info("✅ Нет данных для обновления индикаторов.")
            return

        # Сортируем по алфавиту (symbol, timeframe)
        pairs = sorted(pairs, key=lambda x: (x[0], x[1]))

        # Логируем начало пакетной обработки
        symbols = list({p[0] for p in pairs})
        log_batch_start(len(pairs), symbols)

        # Разбиваем на пакеты для параллельной обработки
        chunks = [pairs[i : i + CHUNK_SIZE] for i in range(0, len(pairs), CHUNK_SIZE)]

        total_processed = 0
        total_indicators = 0
        total_errors = 0

        with tqdm(
            total=len(pairs), desc="📈 Параллельная обработка", ncols=100
        ) as pbar:
            for chunk_idx, chunk in enumerate(chunks):
                # Обрабатываем пакет параллельно
                chunk_results = await process_chunk_parallel(chunk)

                # Обрабатываем результаты пакета
                for i, (
                    success,
                    indicators_count,
                    calculation_time,
                    errors,
                ) in enumerate(chunk_results):
                    symbol, timeframe = chunk[i]

                    if success:
                        total_processed += 1
                        total_indicators += indicators_count
                        log_indicator_calculation(
                            symbol,
                            timeframe,
                            indicators_count,
                            calculation_time,
                            errors,
                        )
                    else:
                        total_errors += 1
                        indicators_logger.error(
                            f"❌ Ошибка при обработке {symbol} {timeframe}: {errors}"
                        )

                    pbar.update(1)
                    pbar.set_postfix(
                        {
                            "Обработано": f"{total_processed}/{len(pairs)}",
                            "Индикаторов": total_indicators,
                            "Ошибок": total_errors,
                            "Пакет": f"{chunk_idx + 1}/{len(chunks)}",
                        }
                    )

                # Логируем прогресс пакета
                log_batch_progress(
                    total_processed,
                    len(pairs),
                    f"Пакет {chunk_idx + 1}",
                    f"из {len(chunks)}",
                )

        # Вывести статистику
        count_q = select(func.count()).select_from(Indicator)
        result = await session.execute(count_q)
        count = result.scalar()

        log_session_summary()

        indicators_logger.info("🎉 Параллельный расчёт индикаторов завершён успешно!")
        indicators_logger.info(f"📊 Обработано пар symbol-timeframe: {total_processed}")
        indicators_logger.info(f"📊 Всего индикаторов рассчитано: {total_indicators}")
        indicators_logger.info(f"📊 Ошибок: {total_errors}")
        indicators_logger.info(f"📊 Всего записей в таблице indicators: {count}")

        print(f"✅ Обработано пар: {total_processed}")
        print(f"📊 Всего индикаторов: {total_indicators}")
        print(f"❌ Ошибок: {total_errors}")
        print(f"📈 Всего записей в таблице: {count}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Расчёт технических индикаторов")
    parser.add_argument("--symbol", help="Конкретный символ для обработки")
    parser.add_argument(
        "--parallel", action="store_true", help="Использовать параллельную обработку"
    )
    parser.add_argument(
        "--no-cleanup", action="store_true", help="Не очищать старые данные"
    )
    parser.add_argument(
        "--cleanup-hours",
        type=int,
        default=24,
        help="Удалять данные старше N часов (по умолчанию 24)",
    )

    args = parser.parse_args()

    if args.parallel:
        asyncio.run(
            main_parallel(
                args.symbol,
                cleanup_old=not args.no_cleanup,
                cleanup_hours=args.cleanup_hours,
            )
        )
    else:
        asyncio.run(
            main(
                args.symbol,
                cleanup_old=not args.no_cleanup,
                cleanup_hours=args.cleanup_hours,
            )
        )
