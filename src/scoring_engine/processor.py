#!/usr/bin/env python3
"""
Автоматический процессор для Scoring Engine
Обрабатывает все доступные данные индикаторов и комбинаций
"""

import asyncio
import logging
import multiprocessing
import time
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from tqdm import tqdm

from src.database import get_async_session
from src.models import INDICATORS_TABLE_NAME

from .compute import ScoringEngine

logger = logging.getLogger(__name__)
# Настраиваем логгер для записи только в файл, а не в консоль
logger.setLevel(logging.DEBUG)
# Удаляем все существующие обработчики
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
# Добавляем только файловый обработчик
file_handler = logging.FileHandler("scoring_engine.log", encoding="utf-8")
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


# Константы для параллельной обработки
MAX_WORKERS = min(multiprocessing.cpu_count(), 8)  # количество параллельных потоков
CHUNK_SIZE = 10  # размер пакета для параллельной обработки


class ScoringProcessor:
    """Автоматический процессор для вычисления score"""

    def __init__(self, batch_size: int = 100, max_workers: int = 4):
        """
        Инициализация процессора

        Args:
            batch_size: Размер пакета для обработки
            max_workers: Максимальное количество параллельных задач
        """
        self.engine = ScoringEngine()
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.processed_count = 0
        self.error_count = 0

    async def get_pending_records(
        self, session: AsyncSession, limit: int | None = None
    ) -> list[tuple[str, str, int]]:
        """
        Получает записи, которые нужно обработать

        Returns:
            Список кортежей (symbol, timeframe, ts)
        """
        try:
            # Ищем записи с данными индикаторов и комбинаций, но без score
            query = text(
                f"""
                SELECT DISTINCT i.symbol, i.timeframe, i.timestamp
                FROM {INDICATORS_TABLE_NAME} i
                INNER JOIN combination_results c ON
                    i.symbol = c.symbol AND
                    i.timeframe = c.timeframe AND
                    i.timestamp = c.ts
                LEFT JOIN score_results s ON
                    i.symbol = s.symbol AND
                    i.timeframe = s.timeframe AND
                    i.timestamp = s.ts
                WHERE s.id IS NULL
                ORDER BY i.timestamp DESC
            """
            )

            if limit:
                query = text(str(query) + f" LIMIT {limit}")

            result = await session.execute(query)
            records = result.fetchall()

            logger.debug(f"📊 Найдено {len(records)} записей для обработки")
            return [(row[0], row[1], row[2]) for row in records]

        except Exception as e:
            logger.error(f"Ошибка при получении записей для обработки: {e}")
            return []

    async def process_single_score(
        self, record: tuple[str, str, int]
    ) -> tuple[bool, float]:
        """
        Обрабатывает одну запись score

        Args:
            record: Кортеж (symbol, timeframe, ts)

        Returns:
            Кортеж (успех, время обработки)
        """
        start_time = time.time()
        symbol, timeframe, ts = record

        # Отключаем подробное логирование для консоли во время расчетов
        disable_verbose_logging()

        try:
            result = await self.engine.compute_score(symbol, timeframe, ts)
            calculation_time = time.time() - start_time

            if result:
                logger.debug(
                    f"✅ {symbol} {timeframe}: Score рассчитан за {calculation_time:.2f}с"
                )
                return True, calculation_time
            logger.debug(f"⚠️ {symbol} {timeframe}: Нет данных для расчета score")
            return False, calculation_time

        except Exception as e:
            calculation_time = time.time() - start_time
            logger.error(f"❌ {symbol} {timeframe}: Ошибка расчета score: {e}")
            return False, calculation_time

    async def process_chunk_parallel(
        self, chunk: list[tuple[str, str, int]]
    ) -> list[tuple[bool, float]]:
        """
        Обрабатывает чанк записей параллельно

        Args:
            chunk: Список записей для обработки

        Returns:
            List[Tuple[bool, float]]: Результаты обработки
        """
        # Создаём задачи для параллельной обработки
        tasks = []
        for record in chunk:
            task = asyncio.create_task(self.process_single_score(record))
            tasks.append(task)

        # Выполняем все задачи параллельно
        chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Обрабатываем результаты
        processed_results = []
        for _i, result in enumerate(chunk_results):
            if isinstance(result, Exception):
                processed_results.append((False, 0.0))
            else:
                processed_results.append(result)

        return processed_results

    async def process_batch(
        self, records: list[tuple[str, str, int]]
    ) -> tuple[int, int]:
        """
        Обрабатывает пакет записей (последовательно)

        Args:
            records: Список записей для обработки

        Returns:
            Кортеж (обработано, ошибок)
        """
        processed = 0
        errors = 0

        for symbol, timeframe, ts in records:
            try:
                result = await self.engine.compute_score(symbol, timeframe, ts)
                if result:
                    processed += 1
                    if processed % 10 == 0:
                        logger.debug(
                            f"Обработано {processed} записей из {len(records)} "
                            f"(последняя: {symbol} {timeframe} {ts})"
                        )
                else:
                    errors += 1

            except Exception as e:
                errors += 1
                logger.error(f"Ошибка при обработке {symbol} {timeframe} {ts}: {e}")

        return processed, errors

    async def process_all_parallel(self, limit: int | None = None) -> dict:
        """
        Обрабатывает все доступные записи с параллельной обработкой

        Args:
            limit: Ограничение количества записей для обработки

        Returns:
            Статистика обработки
        """
        start_time = datetime.now()
        logger.info(f"🚀 Запуск параллельной обработки score (лимит: {limit})")
        logger.info(f"⚡ Используем {MAX_WORKERS} параллельных потоков")
        # Включаем подробное логирование для основных сообщений
        enable_verbose_logging()

        async for session in get_async_session():
            try:
                # Получаем записи для обработки
                records = await self.get_pending_records(session, limit)

                if not records:
                    logger.info("✅ Нет записей для обработки")
                    return {
                        "processed": 0,
                        "errors": 0,
                        "duration": 0,
                        "status": "no_data",
                    }

                logger.info(f"📊 Найдено {len(records)} записей для обработки")

                # Разбиваем на чанки для параллельной обработки
                chunks = [
                    records[i : i + CHUNK_SIZE]
                    for i in range(0, len(records), CHUNK_SIZE)
                ]
                logger.debug(
                    f"📦 Разбито на {len(chunks)} чанков по {CHUNK_SIZE} записей"
                )

                total_processed = 0
                total_errors = 0
                total_calculation_time = 0.0

                # Параллельная обработка с прогресс баром
                with tqdm(
                    total=len(chunks),
                    desc="🎯 Параллельная обработка scores",
                    unit="чанк",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
                    position=0,
                    leave=True,
                    dynamic_ncols=True,
                ) as pbar:
                    for chunk in chunks:
                        try:
                            # Обрабатываем чанк параллельно
                            chunk_results = await self.process_chunk_parallel(chunk)

                            # Подсчитываем результаты
                            for success, calc_time in chunk_results:
                                if success:
                                    total_processed += 1
                                else:
                                    total_errors += 1
                                total_calculation_time += calc_time

                            pbar.update(1)
                            pbar.set_postfix(
                                {
                                    "Обработано": f"{total_processed}",
                                    "Ошибок": f"{total_errors}",
                                }
                            )

                        except Exception as e:
                            logger.error(f"❌ Ошибка при обработке чанка: {e}")
                            total_errors += len(chunk)
                            pbar.update(1)

                duration = (datetime.now() - start_time).total_seconds()

                # Итоговая статистика
                logger.info("=" * 60)
                logger.info("📊 ИТОГОВАЯ СТАТИСТИКА ОБРАБОТКИ SCORES:")
                logger.info(f"📋 Всего записей: {len(records)}")
                logger.info(f"✅ Успешно обработано: {total_processed}")
                logger.info(f"❌ Ошибок: {total_errors}")
                logger.info(f"⏱️ Общее время расчётов: {total_calculation_time:.2f}с")
                logger.info(f"⏱️ Общее время выполнения: {duration:.2f}с")

                if total_processed > 0:
                    success_rate = total_processed / len(records) * 100
                    avg_time = total_calculation_time / total_processed
                    logger.info(f"📈 Успешность: {success_rate:.1f}%")
                    logger.info(f"⏱️ Среднее время на score: {avg_time:.2f}с")

                logger.info("🎉 Расчёт scores завершён успешно!")

                return {
                    "processed": total_processed,
                    "errors": total_errors,
                    "duration": duration,
                    "status": "completed",
                }

            except Exception as e:
                logger.error(f"❌ Критическая ошибка при обработке: {e}")
                return {
                    "processed": 0,
                    "errors": 1,
                    "duration": (datetime.now() - start_time).total_seconds(),
                    "status": "error",
                }
            finally:
                await session.close()
        return None

    async def process_all(self, limit: int | None = None) -> dict:
        """
        Обрабатывает все доступные записи (последовательно)

        Args:
            limit: Ограничение количества записей для обработки

        Returns:
            Статистика обработки
        """
        start_time = datetime.now()
        logger.info(f"🚀 Запуск автоматической обработки score (лимит: {limit})")

        async for session in get_async_session():
            try:
                # Получаем записи для обработки
                records = await self.get_pending_records(session, limit)

                if not records:
                    logger.info("✅ Нет записей для обработки")
                    return {
                        "processed": 0,
                        "errors": 0,
                        "duration": 0,
                        "status": "no_data",
                    }

                logger.info(f"📊 Найдено {len(records)} записей для обработки")

                # Обрабатываем пакетами
                total_processed = 0
                total_errors = 0

                for i in range(0, len(records), self.batch_size):
                    batch = records[i : i + self.batch_size]
                    logger.info(
                        f"📦 Обрабатываем пакет {i//self.batch_size + 1}/{(len(records)-1)//self.batch_size + 1} "
                        f"({len(batch)} записей)"
                    )

                    processed, errors = await self.process_batch(batch)
                    total_processed += processed
                    total_errors += errors

                    # Небольшая пауза между пакетами
                    await asyncio.sleep(0.1)

                duration = (datetime.now() - start_time).total_seconds()

                logger.info(
                    f"✅ Обработка завершена за {duration:.1f}с: "
                    f"{total_processed} обработано, {total_errors} ошибок"
                )

                return {
                    "processed": total_processed,
                    "errors": total_errors,
                    "duration": duration,
                    "status": "completed",
                }

            except Exception as e:
                logger.error(f"❌ Критическая ошибка при обработке: {e}")
                return {
                    "processed": 0,
                    "errors": 1,
                    "duration": (datetime.now() - start_time).total_seconds(),
                    "status": "error",
                }
            finally:
                await session.close()
        return None

    async def process_symbol(self, symbol: str, timeframe: str | None = None) -> dict:
        """
        Обрабатывает конкретный символ

        Args:
            symbol: Символ для обработки
            timeframe: Таймфрейм (если None, то все)

        Returns:
            Статистика обработки
        """
        start_time = datetime.now()
        logger.info(f"🎯 Обработка символа {symbol} (timeframe: {timeframe})")

        async for session in get_async_session():
            try:
                # Формируем запрос для конкретного символа
                base_query = f"""
                    SELECT DISTINCT i.symbol, i.timeframe, i.timestamp
                    FROM {INDICATORS_TABLE_NAME} i
                    INNER JOIN combination_results c ON
                        i.symbol = c.symbol AND
                        i.timeframe = c.timeframe AND
                        i.timestamp = c.ts
                    LEFT JOIN score_results s ON
                        i.symbol = s.symbol AND
                        i.timeframe = s.timeframe AND
                        i.timestamp = s.ts
                    WHERE i.symbol = '{symbol}' AND s.id IS NULL
                """

                if timeframe:
                    base_query += f" AND i.timeframe = '{timeframe}'"

                base_query += " ORDER BY i.timestamp DESC"

                result = await session.execute(text(base_query))
                records = result.fetchall()

                if not records:
                    logger.info(f"✅ Нет записей для обработки символа {symbol}")
                    return {
                        "processed": 0,
                        "errors": 0,
                        "duration": 0,
                        "status": "no_data",
                    }

                logger.info(f"📊 Найдено {len(records)} записей для {symbol}")

                # Обрабатываем записи
                processed, errors = await self.process_batch(records)
                duration = (datetime.now() - start_time).total_seconds()

                logger.info(
                    f"✅ Обработка {symbol} завершена за {duration:.1f}с: "
                    f"{processed} обработано, {errors} ошибок"
                )

                return {
                    "processed": processed,
                    "errors": errors,
                    "duration": duration,
                    "status": "completed",
                }

            except Exception as e:
                logger.error(f"❌ Ошибка при обработке символа {symbol}: {e}")
                return {
                    "processed": 0,
                    "errors": 1,
                    "duration": (datetime.now() - start_time).total_seconds(),
                    "status": "error",
                }
            finally:
                await session.close()
        return None

    async def get_statistics(self) -> dict:
        """Получает статистику по обработанным данным"""
        async for session in get_async_session():
            try:
                # Общая статистика
                total_indicators = await session.execute(
                    text(f"SELECT COUNT(*) FROM {INDICATORS_TABLE_NAME}")
                )
                total_combinations = await session.execute(
                    text("SELECT COUNT(*) FROM combination_results")
                )
                total_scores = await session.execute(
                    text("SELECT COUNT(*) FROM score_results")
                )

                # Статистика по символам
                symbols_stats = await session.execute(
                    text(
                        """
                    SELECT symbol, COUNT(*) as count
                    FROM score_results
                    GROUP BY symbol
                    ORDER BY count DESC
                    LIMIT 10
                """
                    )
                )

                # Статистика по времени
                recent_scores = await session.execute(
                    text(
                        """
                    SELECT COUNT(*)
                    FROM score_results
                    WHERE created_at > NOW() - INTERVAL '1 hour'
                """
                    )
                )

                return {
                    "total_indicators": total_indicators.scalar(),
                    "total_combinations": total_combinations.scalar(),
                    "total_scores": total_scores.scalar(),
                    "recent_scores_1h": recent_scores.scalar(),
                    "top_symbols": [
                        {"symbol": row[0], "count": row[1]}
                        for row in symbols_stats.fetchall()
                    ],
                }

            except Exception as e:
                logger.error(f"Ошибка при получении статистики: {e}")
                return {}
            finally:
                await session.close()
        return None


# Глобальный экземпляр процессора
_processor = None


def get_scoring_processor() -> ScoringProcessor:
    """Возвращает глобальный экземпляр процессора"""
    global _processor
    if _processor is None:
        _processor = ScoringProcessor()
    return _processor


async def process_all_scores(limit: int | None = None) -> dict:
    """Удобная функция для обработки всех score (параллельная версия)"""
    processor = get_scoring_processor()
    return await processor.process_all_parallel(limit)


async def process_symbol_scores(symbol: str, timeframe: str | None = None) -> dict:
    """Удобная функция для обработки score конкретного символа"""
    processor = get_scoring_processor()
    return await processor.process_symbol(symbol, timeframe)


async def get_score_statistics() -> dict:
    """Удобная функция для получения статистики"""
    processor = get_scoring_processor()
    return await processor.get_statistics()
