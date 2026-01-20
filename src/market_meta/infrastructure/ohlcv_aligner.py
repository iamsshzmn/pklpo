"""
OHLCV Alignment Service.

Синхронизация нормализации с фактическими барами OHLCV.
Критично для корректной привязки ext-данных к барам.
"""

import bisect
from datetime import datetime
from typing import Any

from sqlalchemy import text

from .logging_config import get_logger

logger = get_logger("ohlcv_aligner")


class OHLCVAligner:
    """
    Синхронизация нормализации с фактическими барами OHLCV.

    Критично для корректной привязки ext-данных к барам.
    Решает проблему нормализации "в слепую" (floor timestamp),
    которая не синхронизируется с фактическими барами OHLCV.
    """

    def __init__(self, engine):
        """
        Инициализация aligner.

        Args:
            engine: SQLAlchemy engine для подключения к БД
        """
        self.engine = engine
        self._bar_cache: dict[str, list[datetime]] = (
            {}
        )  # (symbol, timeframe) -> [timestamps]

    def load_bar_timestamps(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[datetime]:
        """
        Загружает фактические timestamps баров из таблицы swap_ohlcv_p.

        Args:
            symbol: Символ инструмента
            timeframe: Таймфрейм (1m, 5m, 15m, 1H)
            start_time: Начало периода
            end_time: Конец периода

        Returns:
            Список timestamps баров (отсортированный, datetime объекты)
        """
        cache_key = f"{symbol}:{timeframe}"

        # Проверяем кэш (если запрос без фильтров по времени)
        if start_time is None and end_time is None and cache_key in self._bar_cache:
            logger.debug(f"Используем кэш для {cache_key}")
            return self._bar_cache[cache_key]

        # Загружаем из БД
        # Таблица swap_ohlcv_p использует timestamp в миллисекундах (BIGINT)
        params: dict[str, Any] = {"symbol": symbol, "timeframe": timeframe}

        query_str = """
            SELECT DISTINCT timestamp
            FROM swap_ohlcv_p
            WHERE symbol = :symbol AND timeframe = :timeframe
        """

        if start_time:
            # Конвертируем datetime в миллисекунды для сравнения
            start_ms = int(start_time.timestamp() * 1000)
            query_str += " AND timestamp >= :start_ms"
            params["start_ms"] = start_ms

        if end_time:
            end_ms = int(end_time.timestamp() * 1000)
            query_str += " AND timestamp <= :end_ms"
            params["end_ms"] = end_ms

        query_str += " ORDER BY timestamp"
        query = text(query_str)

        with self.engine.connect() as conn:
            result = conn.execute(query, params)
            # Конвертируем миллисекунды в datetime
            timestamps = [
                datetime.fromtimestamp(row[0] / 1000) for row in result if row[0]
            ]

        if not timestamps:
            logger.warning(
                f"Нет баров OHLCV для {symbol} {timeframe}"
                f"{f' в диапазоне {start_time} - {end_time}' if start_time or end_time else ''}"
            )
        else:
            logger.debug(f"Загружено {len(timestamps)} баров для {symbol} {timeframe}")

        # Кэшируем если запрос без фильтров
        if start_time is None and end_time is None:
            self._bar_cache[cache_key] = timestamps
            if timestamps:
                logger.debug(f"Кэшировано {len(timestamps)} баров для {cache_key}")

        return timestamps

    @staticmethod
    def floor_to_minute(timestamp: datetime) -> datetime:
        """
        Округляет timestamp до начала минуты (floor).

        Args:
            timestamp: Время события (может иметь секунды/микросекунды)

        Returns:
            Timestamp округлённый до начала минуты
        """
        return timestamp.replace(second=0, microsecond=0)

    def align_to_bar(
        self,
        timestamp: datetime,
        bar_timestamps: list[datetime],
        strategy: str = "nearest",
    ) -> datetime | None:
        """
        Привязывает timestamp к ближайшему бару.

        Перед поиском округляет timestamp до начала минуты для 1m таймфрейма,
        чтобы избежать проблем с точными timestamp'ами из API.

        Args:
            timestamp: Время события (из OKX API)
            bar_timestamps: Список timestamps баров (отсортированный)
            strategy: "nearest" (ближайший), "floor" (предыдущий), "ceil" (следующий)

        Returns:
            bar_timestamp или None если нет подходящего бара
        """
        if not bar_timestamps:
            return None

        # Округляем timestamp до начала минуты для корректного поиска
        # Бары OHLCV хранятся как начало минуты (16:33:00), а API может вернуть 16:33:07.360
        aligned_ts = self.floor_to_minute(timestamp)

        # Бинарный поиск ближайшего бара
        idx = bisect.bisect_left(bar_timestamps, aligned_ts)

        if strategy == "nearest":
            if idx == 0:
                return bar_timestamps[0]
            elif idx == len(bar_timestamps):
                return bar_timestamps[-1]
            else:
                # Выбираем ближайший
                before = bar_timestamps[idx - 1]
                after = bar_timestamps[idx]
                if (timestamp - before) < (after - timestamp):
                    return before
                return after
        elif strategy == "floor":
            if idx == 0:
                return bar_timestamps[0] if timestamp >= bar_timestamps[0] else None
            return bar_timestamps[idx - 1]
        elif strategy == "ceil":
            if idx >= len(bar_timestamps):
                return None
            return bar_timestamps[idx]

        return None

    def load_bar_timestamps_batch(
        self,
        symbols: list[str],
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, list[datetime]]:
        """
        Загружает timestamps баров для нескольких символов одним запросом.

        Args:
            symbols: Список символов.
            timeframe: Таймфрейм.
            start_time: Начало периода.
            end_time: Конец периода.

        Returns:
            dict[symbol] -> list[datetime] отсортированных timestamps.
        """
        from collections import defaultdict

        if not symbols:
            return {}

        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)

        query = text(
            """
            SELECT symbol, timestamp
            FROM swap_ohlcv_p
            WHERE symbol = ANY(:symbols)
              AND timeframe = :timeframe
              AND timestamp >= :start_ms
              AND timestamp <= :end_ms
            ORDER BY symbol, timestamp
        """
        )

        result_map: dict[str, list[datetime]] = defaultdict(list)

        with self.engine.connect() as conn:
            result = conn.execute(
                query,
                {
                    "symbols": symbols,
                    "timeframe": timeframe,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                },
            )
            for row in result:
                sym = row[0]
                ts_ms = row[1]
                if ts_ms:
                    result_map[sym].append(datetime.fromtimestamp(ts_ms / 1000))

        # Кэшируем результаты
        for sym, timestamps in result_map.items():
            cache_key = f"{sym}:{timeframe}"
            self._bar_cache[cache_key] = timestamps

        logger.debug(
            f"Batch загружено баров для {len(result_map)} символов, tf={timeframe}"
        )
        return dict(result_map)

    def clear_cache(self, symbol: str | None = None, timeframe: str | None = None):
        """
        Очищает кэш баров.

        Args:
            symbol: Если указан, очищает только для этого символа
            timeframe: Если указан, очищает только для этого таймфрейма
        """
        if symbol and timeframe:
            cache_key = f"{symbol}:{timeframe}"
            self._bar_cache.pop(cache_key, None)
        else:
            self._bar_cache.clear()
        logger.debug("Кэш баров очищен")
