#!/usr/bin/env python3
"""
Модуль для синхронизации swap OHLCV данных с биржи OKX.
Обеспечивает загрузку исторических и текущих данных по всем swap инструментам
с дополнительными данными: funding rate, open interest, long/short ratios.
"""

import asyncio
import datetime
import json
import logging
import os
import random
from pathlib import Path
from typing import Any

from aiolimiter import AsyncLimiter
from sqlalchemy import select, text
from tqdm import tqdm

from src.market_meta.infrastructure.market import OKXMarket
from src.models import Instrument
from src.utils.session_utils import get_db_session

# Конфигурация
logger = logging.getLogger(__name__)

# Поддерживаемые таймфреймы для swap
SWAP_BARS = ["1m", "5m", "15m", "30m", "1H", "4H", "12H", "1D", "1W", "1M"]

# Конфигурация по умолчанию
DEFAULT_CONFIG = {
    "max_requests_per_second": 80,  # Увеличиваем до 80 req/s (безопасно для публичных данных по IP)
    "batch_size": 300,  # Количество свечей за запрос
    "max_retries": 3,
    "retry_delay": 1.0,
    "max_concurrent_symbols": 3,  # Параллельная обработка символов для ускорения
    "extra_data": False,  # По умолчанию не тянем дополнительные метрики (во избежание 429)
}


class SwapCandlesSync:
    """
    Класс для синхронизации swap свечей с OKX.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Инициализация синхронизатора.

        Args:
            config: Конфигурация синхронизации
        """
        self.config = {**DEFAULT_CONFIG, **(config or {})}

        # Инициализируем клиенты
        self.okx_client = OKXMarket()  # Use OKXMarket instead of OKXClient
        # Список инструментов берём из БД/файла, поэтому metadata_loader не нужен

        # Rate limiting
        self.request_limiter = AsyncLimiter(
            max_rate=self.config["max_requests_per_second"], time_period=1.0
        )
        # Дополнительные локальные лимитеры по эндпоинтам (консервативные значения)
        # Эти лимитеры дополняют клиентские, чтобы сгладить пики.
        self._candles_limiter = AsyncLimiter(16, 1.0)
        self._history_candles_limiter = AsyncLimiter(9, 1.0)
        self._funding_limiter = AsyncLimiter(3, 1.0)
        # Per-instrument лимитер для funding-rate (IP+Instrument ID правило)
        self._funding_per_instrument: dict[str, AsyncLimiter] = {}

        # Кэши допданных в рамках одного запуска
        self._funding_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._oi_cache: dict[tuple[str, str], dict[str, Any]] = {}

        # Метрики по эндпоинтам
        self.endpoint_stats: dict[str, dict[str, float]] = {
            "candles": {"ok": 0, "retries": 0, "rate_limit": 0},
            "history_candles": {"ok": 0, "retries": 0, "rate_limit": 0},
            "funding": {"ok": 0, "retries": 0, "rate_limit": 0, "errors": 0},
            "open_interest": {"ok": 0, "retries": 0, "rate_limit": 0, "errors": 0},
        }

        # Счетчики для метрик
        self.total_candles_synced = 0
        self.total_symbols_processed = 0
        self.errors_count = 0

        logger.info(f"SwapCandlesSync инициализирован с конфигурацией: {self.config}")
        logger.debug(f"Rate limiter: {self.config['max_requests_per_second']} req/s")
        logger.debug(f"Batch size: {self.config['batch_size']} candles")
        logger.debug(f"Max concurrent symbols: {self.config['max_concurrent_symbols']}")

    async def resolve_symbols(self, symbols: list[str] | None) -> list[str]:
        """
        Определяет список символов для синхронизации с автообновлением:
        1) Если symbols переданы — используем их напрямую
        2) Иначе — обновляем список из БД и загружаем из файла
        """
        if symbols:
            logger.info(f"Используем переданные символы: {len(symbols)} шт")
            return symbols

        # Автоматически обновляем список инструментов
        logger.info("🔄 Автообновление списка инструментов...")
        await self._update_instruments_list()

        # Загружаем обновленный список
        instruments_file = self._get_instruments_file()
        if instruments_file.exists():
            try:
                with open(instruments_file, encoding="utf-8") as f:
                    file_symbols: list[str] = json.load(f)
                logger.info(
                    f"Загружено {len(file_symbols)} символов из обновленного файла {instruments_file}"
                )
                return file_symbols
            except Exception as e:
                logger.warning(
                    f"Не удалось загрузить список символов из файла: {e}. Переходим к БД по умолчанию."
                )

        # Fallback — все SWAP USDT из БД
        logger.info("Загружаем символы из базы данных...")
        async with get_db_session() as session:
            result = await session.execute(
                select(Instrument).where(
                    Instrument.settle_ccy == "USDT",
                    Instrument.inst_type == "SWAP",
                )
            )
            db_instruments = result.scalars().all()
            symbols_list = sorted(
                (inst.symbol for inst in db_instruments), key=lambda s: s
            )
            logger.info(f"Загружено {len(symbols_list)} символов из БД")
            return symbols_list

    async def _update_instruments_list(self) -> None:
        """
        Внутренний метод для обновления списка инструментов.
        Сохраняет BTC и ETH в начале, остальные добавляет по алфавиту.
        """
        instruments_file = self._get_instruments_file()

        # Загружаем текущий список
        current_symbols: list[str] = []
        if instruments_file.exists():
            try:
                with open(instruments_file, encoding="utf-8") as f:
                    current_symbols = json.load(f)
                logger.debug(
                    f"📋 Загружен текущий список: {len(current_symbols)} символов"
                )
            except Exception as e:
                logger.warning(f"⚠️ Ошибка загрузки текущего списка: {e}")

        # Получаем все SWAP USDT символы из БД
        logger.info("🔄 Загружаем символы из базы данных...")
        async with get_db_session() as session:
            # Сначала проверим что есть в БД
            all_instruments = await session.execute(select(Instrument))
            all_count = len(all_instruments.fetchall())
            logger.info(f"📊 Всего инструментов в БД: {all_count}")

            # Проверим SWAP инструменты
            swap_instruments = await session.execute(
                select(Instrument).where(Instrument.inst_type == "SWAP")
            )
            swap_count = len(swap_instruments.fetchall())
            logger.info(f"📊 SWAP инструментов в БД: {swap_count}")

            # Проверим USDT инструменты
            usdt_instruments = await session.execute(
                select(Instrument).where(Instrument.settle_ccy == "USDT")
            )
            usdt_count = len(usdt_instruments.fetchall())
            logger.info(f"📊 USDT инструментов в БД: {usdt_count}")

            # Теперь основной запрос
            result = await session.execute(
                select(Instrument.symbol).where(
                    Instrument.settle_ccy == "USDT",
                    Instrument.inst_type == "SWAP",
                )
            )
            db_symbols = [row[0] for row in result.fetchall()]

        logger.info(f"📊 Найдено {len(db_symbols)} SWAP USDT символов в БД")
        if db_symbols:
            logger.info(f"📋 Первые 5 символов: {db_symbols[:5]}")
        else:
            logger.warning("⚠️ Не найдено SWAP USDT символов в БД!")

        # Определяем приоритетные символы (всегда в начале)
        priority_symbols = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]

        # Создаем новый список
        new_symbols = []

        # 1. Добавляем приоритетные символы (если есть в БД)
        for priority in priority_symbols:
            if priority in db_symbols:
                new_symbols.append(priority)
                logger.debug(f"➕ Добавлен приоритетный символ: {priority}")

        # 2. Добавляем остальные символы по алфавиту
        remaining_symbols = sorted([s for s in db_symbols if s not in priority_symbols])
        new_symbols.extend(remaining_symbols)

        logger.debug(f"📝 Новый список содержит {len(new_symbols)} символов")

        # Проверяем изменения
        current_set = set(current_symbols)
        new_set = set(new_symbols)

        added = new_set - current_set
        removed = current_set - new_set

        if added:
            logger.info(f"➕ Добавлены новые символы: {sorted(added)}")
        if removed:
            logger.info(f"➖ Удалены символы: {sorted(removed)}")

        if not added and not removed:
            logger.debug("✅ Список актуален, изменений не требуется")
            return

        # Сохраняем новый список
        try:
            with open(instruments_file, "w", encoding="utf-8") as f:
                json.dump(new_symbols, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Список обновлен и сохранен в {instruments_file}")

            # Показываем статистику
            logger.info("📊 СТАТИСТИКА ОБНОВЛЕНИЯ:")
            logger.info(f"   • Всего символов: {len(new_symbols)}")
            logger.info(
                f"   • Приоритетных: {len([s for s in new_symbols if s in priority_symbols])}"
            )
            logger.info(
                f"   • Обычных: {len([s for s in new_symbols if s not in priority_symbols])}"
            )
            if added:
                logger.info(f"   • Добавлено: {len(added)}")
            if removed:
                logger.info(f"   • Удалено: {len(removed)}")

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения списка: {e}")
            raise

    def _get_instruments_file(self) -> Path:
        """Возвращает путь к файлу кэша инструментов в доступной для записи директории.
        По умолчанию используем `/opt/airflow/project/logs` внутри контейнера Airflow.
        Путь можно переопределить через переменную окружения `INSTRUMENTS_CACHE_DIR`.
        """
        cache_dir = Path(
            os.getenv("INSTRUMENTS_CACHE_DIR", "/opt/airflow/project/logs")
        )
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Если не удалось создать, откатываемся в /tmp
            cache_dir = Path("/tmp")
            cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / "instruments_list.json"

    async def sync_swap_bar(
        self, symbol: str, timeframe: str, before: str | None = None
    ) -> tuple[int, str | None]:
        """
        Синхронизация одного таймфрейма для одного swap инструмента.

        Args:
            symbol: Символ инструмента
            timeframe: Таймфрейм
            before: Timestamp для пагинации

        Returns:
            Кортеж: (количество синхронизированных свечей, ts последней свечи)
        """
        try:
            logger.debug(f"Запрашиваем свечи {symbol} {timeframe} (before: {before})")
            # Экспоненциальный backoff с джиттером при 429/5xx
            attempts = 0
            delay = max(self.config.get("retry_delay", 1.0), 0.5)
            while True:
                try:
                    async with self._candles_limiter:
                        async with self.okx_client._public_limiter:
                            async with self.okx_client.get_instrument_limiter(symbol):
                                candles = await self.okx_client.get_candles(
                                    inst_id=symbol,
                                    bar=timeframe,
                                    limit=self.config["batch_size"],
                                    before=before,
                                )
                    self.endpoint_stats["candles"]["ok"] += 1
                    break
                except Exception as fetch_err:
                    msg = str(fetch_err)
                    retriable = any(
                        x in msg
                        for x in [
                            "429",
                            "Too Many Requests",
                            "50011",
                            "5xx",
                            "temporarily",
                        ]
                    )
                    if not retriable or attempts >= self.config.get("max_retries", 3):
                        raise
                    attempts += 1
                    if any(x in msg for x in ["429", "Too Many Requests", "50011"]):
                        self.endpoint_stats["candles"]["rate_limit"] += 1
                    self.endpoint_stats["candles"]["retries"] += 1
                    jitter = random.uniform(0.2, 0.5)
                    sleep_for = min(60.0, delay) + jitter
                    logger.warning(
                        f"{symbol} {timeframe}: ограничение/сбой запроса, повтор через {sleep_for:.2f}s (попытка {attempts})"
                    )
                    await asyncio.sleep(sleep_for)
                    delay *= 1.5

            if not candles:
                logger.debug(f"Нет свечей для {symbol} {timeframe}")
                return 0, None

            logger.debug(f"Получено {len(candles)} свечей для {symbol} {timeframe}")
            # Доп. данные для swap
            additional_data = await self._get_swap_additional_data(symbol, candles)

            # Сохраняем в БД
            saved_count = await self._save_swap_candles(
                symbol, timeframe, candles, additional_data
            )
            last_ts: str | None = str(candles[-1]["ts"]) if candles else None
            logger.debug(f"Сохранено {saved_count} свечей для {symbol} {timeframe}")
            return saved_count, last_ts

        except Exception as e:
            if "51000" in str(e) and "Parameter bar error" in str(e):
                logger.warning(f"{symbol}: Таймфрейм {timeframe} не поддерживается")
                return 0, None
            logger.error(f"Ошибка при синхронизации {symbol} {timeframe}: {e}")
            self.errors_count += 1
            raise

    async def _get_swap_additional_data(
        self, symbol: str, candles: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Получает дополнительные данные для swap инструментов.

        Args:
            symbol: Символ инструмента
            candles: Список свечей

        Returns:
            Дополнительные данные
        """
        # По умолчанию дополнительные данные отключены для снижения 429
        if not self.config.get("extra_data", False):
            logger.debug(f"Дополнительные данные отключены для {symbol}")
            return {}

        logger.debug(f"Запрашиваем дополнительные данные для {symbol}")
        additional_data: dict[str, Any] = {}

        # Ключи кэша будут построены после получения данных (symbol, fundingTime/ts)

        # Funding rate (ограниченный эндпоинт: IP+Instrument)
        try:
            async with self._funding_limiter:
                limiter = self._funding_per_instrument.setdefault(
                    symbol, AsyncLimiter(2, 1.0)
                )
                async with limiter, self.okx_client._public_limiter:
                    async with self.okx_client.get_instrument_limiter(symbol):
                        fr_map = await self.okx_client.get_funding_rates([symbol])
            fr = fr_map.get(symbol)
            if fr:
                # ожидаем поля fundingTime/ts в ответе
                f_time = str(fr.get("fundingTime") or fr.get("ts") or "")
                cache_key = (symbol, f_time)
                if cache_key not in self._funding_cache:
                    self._funding_cache[cache_key] = fr
                additional_data["funding_rate"] = self._funding_cache[cache_key]
                logger.debug(
                    f"Получен funding rate для {symbol} (cache_key={cache_key})"
                )
                self.endpoint_stats["funding"]["ok"] += 1
        except Exception as e:
            logger.warning(f"Не удалось получить funding rate для {symbol}: {e}")
            msg = str(e)
            if any(x in msg for x in ["429", "Too Many Requests", "50011"]):
                self.endpoint_stats["funding"]["rate_limit"] += 1
                self.endpoint_stats["funding"]["retries"] += 1
            else:
                self.endpoint_stats["funding"]["errors"] += 1

        # Open interest (публичный, но тоже сдерживаем)
        try:
            async with self._funding_limiter:
                async with self.okx_client._public_limiter:
                    async with self.okx_client.get_instrument_limiter(symbol):
                        oi_map = await self.okx_client.get_open_interest([symbol])
            oi = oi_map.get(symbol)
            if oi:
                o_time = str(oi.get("ts") or oi.get("time") or "")
                cache_key = (symbol, o_time)
                if cache_key not in self._oi_cache:
                    self._oi_cache[cache_key] = oi
                additional_data["open_interest"] = self._oi_cache[cache_key]
                logger.debug(
                    f"Получен open interest для {symbol} (cache_key={cache_key})"
                )
                self.endpoint_stats["open_interest"]["ok"] += 1
        except Exception as e:
            logger.warning(f"Не удалось получить open interest для {symbol}: {e}")
            msg = str(e)
            if any(x in msg for x in ["429", "Too Many Requests", "50011"]):
                self.endpoint_stats["open_interest"]["rate_limit"] += 1
                self.endpoint_stats["open_interest"]["retries"] += 1
            else:
                self.endpoint_stats["open_interest"]["errors"] += 1

        return additional_data

    async def _save_swap_candles(
        self,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
        additional_data: dict[str, Any],
    ) -> int:
        """
        Сохраняет swap свечи в базу данных.

        Args:
            symbol: Символ инструмента
            timeframe: Таймфрейм
            candles: Список свечей
            additional_data: Дополнительные данные

        Returns:
            Количество сохраненных свечей
        """
        async with get_db_session() as session:
            try:
                saved_count = 0
                logger.debug(
                    f"Начинаем сохранение {len(candles)} свечей для {symbol} {timeframe}"
                )

                for candle in candles:
                    # Базовые данные свечи
                    candle_data = {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "timestamp": candle["ts"],
                        "open": candle["open"],
                        "high": candle["high"],
                        "low": candle["low"],
                        "close": candle["close"],
                        "volume": candle["volume"],
                        "vol_ccy": candle.get("volCcy"),
                        "vol_usd": candle.get("volUsd"),
                        "fetched_at": datetime.datetime.utcnow(),
                    }

                    # Добавляем дополнительные данные если доступны
                    if additional_data.get("funding_rate"):
                        candle_data["funding_rate"] = additional_data[
                            "funding_rate"
                        ].get("fundingRate")

                    if additional_data.get("open_interest"):
                        candle_data["open_interest"] = additional_data[
                            "open_interest"
                        ].get("oi")

                    # Вставляем или обновляем данные используя raw SQL
                    columns = list(candle_data.keys())
                    list(candle_data.values())
                    placeholders = [f":{col}" for col in columns]

                    sql = f"""
                    INSERT INTO swap_ohlcv_p ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                    ON CONFLICT (symbol, timeframe, timestamp)
                    DO UPDATE SET
                    """
                    update_parts = [
                        f"{col} = EXCLUDED.{col}"
                        for col in columns
                        if col not in ["symbol", "timeframe", "timestamp"]
                    ]
                    sql += ", ".join(update_parts)

                    stmt = text(sql)

                    await session.execute(stmt, candle_data)
                    saved_count += 1

                await session.commit()
                logger.debug(
                    f"Успешно сохранено {saved_count} свечей в БД для {symbol} {timeframe}"
                )
                return saved_count

            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка при сохранении свечей {symbol} {timeframe}: {e}")
                raise

    async def sync_swap_symbol(
        self, symbol: str, timeframes: list[str] | None = None
    ) -> dict[str, int]:
        """
        Синхронизация всех таймфреймов для одного swap инструмента.

        Args:
            symbol: Символ инструмента
            timeframes: Список таймфреймов для синхронизации

        Returns:
            Статистика синхронизации по таймфреймам
        """
        if timeframes is None:
            timeframes = SWAP_BARS

        stats: dict[str, int] = {}

        async def sync_one_tf(tf: str) -> tuple[str, int]:
            total = 0
            before_local: str | None = None
            logger.debug(f"Начинаем синхронизацию {symbol} {tf}")
            while True:
                count, last_ts = await self.sync_swap_bar(symbol, tf, before_local)
                total += count
                if count < self.config["batch_size"] or not last_ts:
                    break
                before_local = last_ts
                logger.debug(f"{symbol} {tf}: загружено {count} свечей, всего {total}")
            logger.info(f"{symbol} {tf}: синхронизировано {total} свечей")
            return tf, total

        # Последовательно по таймфреймам, чтобы сгладить нагрузку
        logger.debug(
            f"Запускаем последовательную синхронизацию {len(timeframes)} таймфреймов для {symbol}"
        )
        for tf in timeframes:
            tf_name, total = await sync_one_tf(tf)
            stats[tf_name] = total
            # Небольшой джиттер между барами
            await asyncio.sleep(random.uniform(0.2, 0.5))

        return stats

    async def sync_all_swap_candles(
        self, symbols: list[str] | None = None, timeframes: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Синхронизация всех swap свечей.

        Args:
            symbols: Список символов для синхронизации (если None - все)
            timeframes: Список таймфреймов для синхронизации

        Returns:
            Общая статистика синхронизации
        """
        logger.info("🚀 Начинаем синхронизацию swap свечей...")

        start_time = datetime.datetime.now()

        try:
            # Гарантируем корректную инициализацию/закрытие HTTP-сессии клиента OKX
            async with self.okx_client:
                # Получаем список символов из БД/файла (как в sync_candles.py)
                symbols = await self.resolve_symbols(symbols)

                logger.info(f"📊 Синхронизируем {len(symbols)} swap инструментов")
                logger.info(f"⏰ Таймфреймы: {timeframes or SWAP_BARS}")
                logger.info(f"⚙️ Конфигурация: {self.config}")

                # Параллельная обработка символов с ограничением через Semaphore
                max_concurrent = self.config.get("max_concurrent_symbols", 1)
                semaphore = asyncio.Semaphore(max_concurrent)
                results = {}

                logger.info(
                    f"🔄 Запускаем параллельную синхронизацию {len(symbols)} символов "
                    f"(max_concurrent={max_concurrent})"
                )

                async def sync_symbol_with_semaphore(
                    symbol: str,
                ) -> tuple[str, dict[str, int] | Exception]:
                    """Обрабатывает один символ с ограничением параллелизма."""
                    async with semaphore:
                        try:
                            logger.info(f"🔄 Обрабатываем символ: {symbol}")
                            result = await self.sync_swap_symbol(symbol, timeframes)

                            # Обновляем общую статистику (thread-safe через asyncio)
                            for _timeframe, count in result.items():
                                self.total_candles_synced += count
                            self.total_symbols_processed += 1

                            total_candles = sum(result.values())
                            logger.info(
                                f"✅ Символ {symbol} завершен: {total_candles} свечей"
                            )
                            return symbol, result
                        except Exception as e:
                            logger.error(
                                f"❌ Ошибка при синхронизации символа {symbol}: {e}"
                            )
                            self.errors_count += 1
                            return symbol, e

                # Запускаем все задачи параллельно
                tasks = [
                    asyncio.create_task(sync_symbol_with_semaphore(symbol))
                    for symbol in symbols
                ]

                # Собираем результаты с обработкой исключений
                with tqdm(total=len(symbols), desc="Синхронизация swap") as pbar:
                    for coro in asyncio.as_completed(tasks):
                        symbol, result = await coro
                        if isinstance(result, Exception):
                            results[symbol] = {}
                        else:
                            results[symbol] = result
                        pbar.update(1)

            end_time = datetime.datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Подсчёт свежести за сегодня
            today_stats = {
                "rows_today": 0,
                "funding_rate_non_null": 0,
                "open_interest_non_null": 0,
                "funding_rate_fill_pct": 0.0,
                "open_interest_fill_pct": 0.0,
            }

            try:
                start_of_day_ms = int(
                    datetime.datetime.utcnow()
                    .replace(hour=0, minute=0, second=0, microsecond=0)
                    .timestamp()
                    * 1000
                )
                async with get_db_session() as session:
                    q_total = await session.execute(
                        text(
                            """
                        SELECT COUNT(*) FROM swap_ohlcv_p WHERE timestamp >= :t
                    """
                        ),
                        {"t": start_of_day_ms},
                    )
                    today_stats["rows_today"] = int(q_total.scalar() or 0)

                    q_fill = await session.execute(
                        text(
                            """
                        SELECT
                          COUNT(*) FILTER (WHERE funding_rate IS NOT NULL) AS fr,
                          COUNT(*) FILTER (WHERE open_interest IS NOT NULL) AS oi
                        FROM swap_ohlcv_p
                        WHERE timestamp >= :t
                    """
                        ),
                        {"t": start_of_day_ms},
                    )
                    fr, oi = q_fill.fetchone()
                    today_stats["funding_rate_non_null"] = int(fr or 0)
                    today_stats["open_interest_non_null"] = int(oi or 0)
                    if today_stats["rows_today"] > 0:
                        today_stats["funding_rate_fill_pct"] = round(
                            100.0
                            * today_stats["funding_rate_non_null"]
                            / today_stats["rows_today"],
                            2,
                        )
                        today_stats["open_interest_fill_pct"] = round(
                            100.0
                            * today_stats["open_interest_non_null"]
                            / today_stats["rows_today"],
                            2,
                        )
            except Exception as e:
                logger.warning(f"Не удалось вычислить свежесть за сегодня: {e}")

            # Формируем итоговую статистику
            total_stats = {
                "total_symbols": len(symbols),
                "total_candles_synced": self.total_candles_synced,
                "total_symbols_processed": self.total_symbols_processed,
                "errors_count": self.errors_count,
                "duration_seconds": duration,
                "symbols_per_second": len(symbols) / duration if duration > 0 else 0,
                "candles_per_second": (
                    self.total_candles_synced / duration if duration > 0 else 0
                ),
                "results_by_symbol": results,
                "endpoint_stats": self.endpoint_stats,
                "today_fill": today_stats,
            }

            logger.info("✅ Синхронизация swap свечей завершена!")
            logger.info("📊 Итоговая статистика:")
            logger.info(f"   • Символов обработано: {total_stats['total_symbols']}")
            logger.info(
                f"   • Свечей синхронизировано: {total_stats['total_candles_synced']:,}"
            )
            logger.info(f"   • Ошибок: {total_stats['errors_count']}")
            logger.info(
                f"   • Время выполнения: {total_stats['duration_seconds']:.2f} сек"
            )
            logger.info(
                f"   • Скорость: {total_stats['candles_per_second']:.2f} свечей/сек"
            )
            logger.debug(f"📋 Детальная статистика: {total_stats}")

            return total_stats

        except Exception as e:
            logger.error(f"❌ Критическая ошибка при синхронизации swap свечей: {e}")
            raise


async def sync_swap_candles(
    symbols: list[str] | None = None,
    timeframes: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Основная функция для синхронизации swap свечей.

    Args:
        symbols: Список символов для синхронизации
        timeframes: Список таймфреймов для синхронизации
        config: Конфигурация синхронизации

    Returns:
        Статистика синхронизации
    """
    sync = SwapCandlesSync(config)
    return await sync.sync_all_swap_candles(symbols, timeframes)


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("🚀 Запуск модуля синхронизации swap свечей")

    # Запуск синхронизации
    asyncio.run(sync_swap_candles())
