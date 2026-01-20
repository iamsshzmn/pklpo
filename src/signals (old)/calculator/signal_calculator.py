"""
Основной класс калькулятора сигналов (оптимизированная версия).
"""

import asyncio
import json
import logging
import multiprocessing
import time
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from tqdm import tqdm

from src.database import get_async_session
from src.models import Signal

from ..engine import SignalEngine
from ..logging import disable_verbose_logging, enable_verbose_logging

logger = logging.getLogger(__name__)
# Настраиваем логгер для записи только в файл, а не в консоль
logger.setLevel(logging.DEBUG)
# Удаляем все существующие обработчики
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
# Добавляем только файловый обработчик
file_handler = logging.FileHandler("signal_calculator.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

BATCH_SIZE = 1000  # размер пакета для обработки
MAX_WORKERS = min(multiprocessing.cpu_count(), 12)  # количество параллельных потоков
CHUNK_SIZE = 10  # размер пакета для параллельной обработки


class SignalCalculator:
    """
    Калькулятор для генерации и сохранения торговых сигналов (оптимизированная версия).
    """

    def __init__(self, engine: SignalEngine):
        """
        Инициализация калькулятора.

        Args:
            engine: Движок сигналов
        """
        self.engine = engine
        self.batch_size = BATCH_SIZE

    async def get_symbols_to_process(self, symbol=None) -> list[str]:
        """
        Получить список символов для обработки.

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

                logger.info(f"📊 Найдено {len(symbols)} символов для обработки")
                return symbols

            except Exception as e:
                logger.error(f"❌ Ошибка при получении символов: {e}")
                return []
        return None

    async def get_timeframes_for_symbol(
        self, session: AsyncSession, symbol: str
    ) -> list[str]:
        """
        Получить таймфреймы для символа.

        Args:
            session: Сессия БД
            symbol: Символ

        Returns:
            List[str]: Список таймфреймов
        """
        try:
            query = text(
                "SELECT DISTINCT timeframe FROM indicators WHERE symbol = :symbol"
            )
            result = await session.execute(query, {"symbol": symbol})
            return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.error(f"❌ Ошибка при получении таймфреймов для {symbol}: {e}")
            return []

    async def get_indicators_for_symbol(
        self, session: AsyncSession, symbol: str, timeframe: str
    ) -> list[dict]:
        """
        Получает индикаторы для символа и таймфрейма.

        Args:
            session: Сессия БД
            symbol: Символ
            timeframe: Таймфрейм

        Returns:
            List[dict]: Список данных индикаторов
        """
        # Используем прямой SQL запрос с ограничением
        query = text(
            """
            SELECT * FROM indicators
            WHERE symbol = :symbol AND timeframe = :timeframe
            ORDER BY ts DESC
            LIMIT :limit
        """
        )

        result = await session.execute(
            query, {"symbol": symbol, "timeframe": timeframe, "limit": self.batch_size}
        )
        rows = result.fetchall()

        # Преобразуем в список словарей (в правильном порядке)
        indicators = []
        for row in reversed(rows):  # Разворачиваем для правильного порядка
            indicators.append(dict(row._mapping))

        return indicators

    async def check_existing_signal(
        self, session: AsyncSession, symbol: str, timeframe: str, ts: int
    ) -> bool:
        """
        Проверяет, существует ли уже сигнал для данной свечи.

        Args:
            session: Сессия БД
            symbol: Символ
            timeframe: Таймфрейм
            ts: Timestamp

        Returns:
            bool: True если сигнал уже существует
        """
        query = select(Signal).where(
            Signal.symbol == symbol, Signal.timeframe == timeframe, Signal.ts == ts
        )

        result = await session.execute(query)
        return result.scalar_one_or_none() is not None

    async def process_single_symbol_timeframe(
        self, symbol: str, timeframe: str, recalculate: bool = False
    ) -> tuple[bool, int, float, list[str]]:
        """
        Обработать один символ-таймфрейм с улучшенной обработкой ошибок.

        Args:
            symbol: Символ
            timeframe: Таймфрейм
            recalculate: Пересчитывать ли существующие сигналы

        Returns:
            Tuple[bool, int, float, List[str]]: (успех, количество сигналов, время, ошибки)
        """
        start_time = time.time()
        errors = []

        try:
            async for session in get_async_session():
                try:
                    signals_count = await self.calculate_signals_for_symbol(
                        session, symbol, timeframe, recalculate
                    )
                    calculation_time = time.time() - start_time
                    return True, signals_count, calculation_time, errors

                except Exception as e:
                    errors.append(str(e))
                    calculation_time = time.time() - start_time
                    return False, 0, calculation_time, errors

        except Exception as e:
            errors.append(str(e))
            calculation_time = time.time() - start_time
            return False, 0, calculation_time, errors

    async def calculate_signals_for_symbol(
        self,
        session: AsyncSession,
        symbol: str,
        timeframe: str,
        recalculate: bool = False,
    ) -> int:
        """
        Рассчитывает сигналы для конкретного символа и таймфрейма.

        Args:
            session: Сессия БД
            symbol: Символ
            timeframe: Таймфрейм
            recalculate: Пересчитывать ли существующие сигналы

        Returns:
            int: Количество созданных/обновленных сигналов
        """
        # Отключаем подробное логирование для консоли во время расчетов
        disable_verbose_logging()

        # Логируем только в файл
        logger.debug(f"Рассчитываем сигналы для {symbol} {timeframe}")

        # Если пересчет, сначала удаляем существующие сигналы
        if recalculate:
            delete_query = text(
                "DELETE FROM signals WHERE symbol = :symbol AND timeframe = :timeframe"
            )
            await session.execute(
                delete_query, {"symbol": symbol, "timeframe": timeframe}
            )
            logger.debug(f"Удалены существующие сигналы для {symbol} {timeframe}")

        # Получаем индикаторы
        indicators = await self.get_indicators_for_symbol(session, symbol, timeframe)

        if len(indicators) < 2:
            logger.warning(
                f"Недостаточно данных для {symbol} {timeframe}: {len(indicators)} записей"
            )
            return 0

        signals_created = 0
        batch_signals = []

        # Обрабатываем каждую свечу (начиная со второй, чтобы иметь предыдущую)
        for i in range(1, len(indicators)):
            current = indicators[i]
            previous = indicators[i - 1]

            # Проверяем, существует ли уже сигнал (только если не пересчет)
            if not recalculate and await self.check_existing_signal(
                session, current["symbol"], current["timeframe"], current["ts"]
            ):
                continue

            try:
                # Генерируем сигнал
                signal_data = self.engine.generate_signal(current, previous)

                # Создаем объект сигнала
                signal = Signal(
                    symbol=current["symbol"],
                    timeframe=current["timeframe"],
                    ts=current["ts"],
                    signal=signal_data["signal"],
                    reason=json.dumps(signal_data, ensure_ascii=False, default=str),
                    created_at=datetime.now(),
                )

                # Добавляем в пакет
                batch_signals.append(signal)
                signals_created += 1

                # Логируем сигнал (только для отладки)
                # score = sum(signal_data.get("rule_signals", []))
                # log_signal(
                #     symbol=current["symbol"],
                #     timeframe=current["timeframe"],
                #     signal=signal_data["signal"],
                #     score=score,
                #     reason=signal_data["reason"],
                #     ts=current["ts"],
                # )

                # Коммитим пакет если достигли размера
                if len(batch_signals) >= self.batch_size:
                    session.add_all(batch_signals)
                    await session.commit()
                    batch_signals = []

            except Exception as e:
                logger.error(
                    f"Ошибка при расчете сигнала для {symbol} {timeframe} at {current['ts']}: {e}"
                )
                continue

        # Коммитим оставшиеся сигналы
        if batch_signals:
            try:
                session.add_all(batch_signals)
                await session.commit()
                logger.debug(
                    f"Создано {signals_created} сигналов для {symbol} {timeframe}"
                )
            except Exception as e:
                logger.error(f"Ошибка при коммите для {symbol} {timeframe}: {e}")
                await session.rollback()
                return 0

        return signals_created

    async def process_chunk_parallel(
        self, chunk: list[tuple[str, str]], recalculate: bool = False
    ) -> list[tuple[bool, int, float, list[str]]]:
        """
        Обработать пакет пар параллельно.

        Args:
            chunk: Список пар (symbol, timeframe) для обработки
            recalculate: Пересчитывать ли существующие сигналы

        Returns:
            List[Tuple[bool, int, float, List[str]]]: Результаты обработки
        """

        async def process_with_session(symbol: str, timeframe: str):
            async for _session in get_async_session():
                return await self.process_single_symbol_timeframe(
                    symbol, timeframe, recalculate
                )
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

    async def calculate_signals_for_all(
        self,
        timeframe: str = "all",
        symbol: str | None = None,
        recalculate: bool = False,
    ) -> dict:
        """
        Рассчитывает сигналы для всех символов с улучшенной статистикой.

        Args:
            timeframe: Таймфрейм для обработки
            symbol: Конкретный символ (если None, обрабатываются все)
            recalculate: Пересчитывать ли существующие сигналы

        Returns:
            dict: Статистика обработки
        """
        logger.info("🚀 Запуск расчёта сигналов...")
        # Включаем подробное логирование для основных сообщений
        enable_verbose_logging()

        # Получаем символы для обработки
        symbols = await self.get_symbols_to_process(symbol)
        if not symbols:
            logger.warning("⚠️ Нет символов для обработки")
            return {"status": "no_symbols", "processed": 0, "signals": 0, "errors": 0}

        # Получаем таймфреймы для каждого символа
        symbol_timeframes = []
        async for session in get_async_session():
            try:
                for sym in symbols:
                    timeframes = await self.get_timeframes_for_symbol(session, sym)

                    if timeframe and timeframe != "all":
                        # Если указан конкретный таймфрейм, используем его
                        if timeframe in timeframes:
                            symbol_timeframes.append((sym, timeframe))
                    else:
                        # Используем все доступные таймфреймы
                        for tf in timeframes:
                            symbol_timeframes.append((sym, tf))

                break
            except Exception as e:
                logger.error(f"❌ Ошибка при получении таймфреймов: {e}")
                return {"status": "error", "processed": 0, "signals": 0, "errors": 1}

        if not symbol_timeframes:
            logger.warning("⚠️ Нет пар symbol-timeframe для обработки")
            return {"status": "no_data", "processed": 0, "signals": 0, "errors": 0}

        logger.info(
            f"📊 Найдено {len(symbol_timeframes)} пар symbol-timeframe для обработки"
        )

        total_signals = 0
        total_processed = 0
        total_errors = 0

        with tqdm(
            total=len(symbol_timeframes),
            desc="🎯 Обработка сигналов",
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
                    signals_count,
                    calculation_time,
                    errors,
                ) = await self.process_single_symbol_timeframe(
                    symbol, timeframe, recalculate
                )

                if success:
                    total_processed += 1
                    total_signals += signals_count
                    # Убираем избыточное логирование для ускорения и видимости прогресс бара
                    # if signals_count > 0:  # Логируем только если есть сигналы
                    #     logger.info(f"✅ {symbol} {timeframe}: {signals_count} сигналов за {calculation_time:.2f}с")
                else:
                    total_errors += 1
                    logger.error(
                        f"❌ Ошибка при обработке {symbol} {timeframe}: {errors}"
                    )

                pbar.update(1)
                pbar.set_postfix(
                    {
                        "Обработано": f"{total_processed}/{len(symbol_timeframes)}",
                        "Сигналов": f"{total_signals:,}",
                        "Ошибок": total_errors,
                    }
                )

        # Итоговая статистика
        logger.info("=" * 60)
        logger.info("📊 ИТОГОВАЯ СТАТИСТИКА ОБРАБОТКИ:")
        logger.info(f"📋 Всего пар symbol-timeframe: {len(symbol_timeframes)}")
        logger.info(f"✅ Успешно обработано: {total_processed}")
        logger.info(f"🎯 Всего сигналов создано: {total_signals}")
        logger.info(f"❌ Ошибок: {total_errors}")

        if total_processed > 0:
            success_rate = total_processed / len(symbol_timeframes) * 100
            logger.info(f"📈 Успешность: {success_rate:.1f}%")

        logger.info("🎉 Расчёт сигналов завершён успешно!")

        return {
            "status": "completed",
            "processed": total_processed,
            "signals": total_signals,
            "errors": total_errors,
            "total_pairs": len(symbol_timeframes),
        }

    async def calculate_signals_for_all_parallel(
        self,
        timeframe: str = "all",
        symbol: str | None = None,
        recalculate: bool = False,
    ) -> dict:
        """
        Рассчитывает сигналы для всех символов с параллельной обработкой.

        Args:
            timeframe: Таймфрейм для обработки
            symbol: Конкретный символ (если None, обрабатываются все)
            recalculate: Пересчитывать ли существующие сигналы

        Returns:
            dict: Статистика обработки
        """
        logger.info("🚀 Запуск параллельного расчёта сигналов...")
        logger.info(f"⚡ Используем {MAX_WORKERS} параллельных потоков")
        # Включаем подробное логирование для основных сообщений
        enable_verbose_logging()

        # Получаем символы для обработки
        symbols = await self.get_symbols_to_process(symbol)
        if not symbols:
            logger.warning("⚠️ Нет символов для обработки")
            return {"status": "no_symbols", "processed": 0, "signals": 0, "errors": 0}

        # Получаем таймфреймы для каждого символа
        symbol_timeframes = []
        async for session in get_async_session():
            try:
                for sym in symbols:
                    timeframes = await self.get_timeframes_for_symbol(session, sym)

                    if timeframe and timeframe != "all":
                        # Если указан конкретный таймфрейм, используем его
                        if timeframe in timeframes:
                            symbol_timeframes.append((sym, timeframe))
                    else:
                        # Используем все доступные таймфреймы
                        for tf in timeframes:
                            symbol_timeframes.append((sym, tf))

                break
            except Exception as e:
                logger.error(f"❌ Ошибка при получении таймфреймов: {e}")
                return {"status": "error", "processed": 0, "signals": 0, "errors": 1}

        if not symbol_timeframes:
            logger.warning("⚠️ Нет пар symbol-timeframe для обработки")
            return {"status": "no_data", "processed": 0, "signals": 0, "errors": 0}

        logger.info(
            f"📊 Найдено {len(symbol_timeframes)} пар symbol-timeframe для обработки"
        )

        # Разбиваем на пакеты для параллельной обработки
        chunks = [
            symbol_timeframes[i : i + CHUNK_SIZE]
            for i in range(0, len(symbol_timeframes), CHUNK_SIZE)
        ]

        total_signals = 0
        total_processed = 0
        total_errors = 0

        with tqdm(
            total=len(symbol_timeframes),
            desc="🎯 Параллельная обработка сигналов",
            ncols=120,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
            position=0,
            leave=True,
            dynamic_ncols=True,
        ) as pbar:
            for chunk_idx, chunk in enumerate(chunks):
                # Обрабатываем пакет параллельно
                chunk_results = await self.process_chunk_parallel(chunk, recalculate)

                # Обрабатываем результаты пакета
                for i, (success, signals_count, _calculation_time, errors) in enumerate(
                    chunk_results
                ):
                    symbol, timeframe = chunk[i]

                    if success:
                        total_processed += 1
                        total_signals += signals_count
                        # Убираем избыточное логирование для ускорения и видимости прогресс бара
                        # if signals_count > 0:  # Логируем только если есть сигналы
                        #     logger.info(f"✅ {symbol} {timeframe}: {signals_count} сигналов за {calculation_time:.2f}с")
                    else:
                        total_errors += 1
                        logger.error(
                            f"❌ Ошибка при обработке {symbol} {timeframe}: {errors}"
                        )

                    pbar.update(1)
                    pbar.set_postfix(
                        {
                            "Обработано": f"{total_processed}/{len(symbol_timeframes)}",
                            "Сигналов": f"{total_signals:,}",
                            "Ошибок": total_errors,
                            "Пакет": f"{chunk_idx + 1}/{len(chunks)}",
                        }
                    )

        # Итоговая статистика
        logger.info("=" * 60)
        logger.info("📊 ИТОГОВАЯ СТАТИСТИКА ПАРАЛЛЕЛЬНОЙ ОБРАБОТКИ:")
        logger.info(f"📋 Всего пар symbol-timeframe: {len(symbol_timeframes)}")
        logger.info(f"✅ Успешно обработано: {total_processed}")
        logger.info(f"🎯 Всего сигналов создано: {total_signals}")
        logger.info(f"❌ Ошибок: {total_errors}")

        if total_processed > 0:
            success_rate = total_processed / len(symbol_timeframes) * 100
            logger.info(f"📈 Успешность: {success_rate:.1f}%")

        logger.info("🎉 Параллельный расчёт сигналов завершён успешно!")

        return {
            "status": "completed",
            "processed": total_processed,
            "signals": total_signals,
            "errors": total_errors,
            "total_pairs": len(symbol_timeframes),
        }
