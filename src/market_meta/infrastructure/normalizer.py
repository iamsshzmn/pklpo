"""
Нормализация расширенных рыночных данных к границам баров OHLCV.

v1: нормализация к 1m барам с синхронизацией через OHLCVAligner.
v2: поддержка чтения из raw.market_data_ext_raw.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from .logging_config import get_logger
from .ohlcv_aligner import OHLCVAligner

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = get_logger("market_data_normalizer")

# Версия алгоритма нормализации
ALGO_VERSION = "v2.0.0"


class MarketDataNormalizer:
    """
    Нормализация расширенных данных к границам баров OHLCV.

    v1: нормализация к 1m барам с синхронизацией через OHLCVAligner.
    """

    def __init__(self, ohlcv_aligner: OHLCVAligner):
        """
        Инициализация normalizer.

        Args:
            ohlcv_aligner: OHLCVAligner для синхронизации с фактическими барами
        """
        self.aligner = ohlcv_aligner

    def normalize_to_1m_bars(
        self,
        records: list[dict[str, Any]],
        symbol: str,
        bar_timestamps: list[datetime] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Нормализует данные к 1m барам с синхронизацией по фактическим барам OHLCV.

        Правила:
        - OI, L2: последнее значение в баре (привязка к реальному bar_timestamp из OHLCV)
        - Funding: привязка к ближайшему бару (nearest strategy)

        Args:
            records: Сырые данные из API
            symbol: Символ для загрузки баров
            bar_timestamps: Опционально предзагруженные timestamps баров

        Returns:
            Список нормализованных записей с bar_timestamp
        """
        if not records:
            return []

        # Загружаем фактические бары если не переданы
        if bar_timestamps is None:
            # Определяем диапазон из records
            timestamps = []
            for r in records:
                ts = r.get("timestamp") or r.get("ts")
                if isinstance(ts, datetime):
                    timestamps.append(ts)
                elif isinstance(ts, (int, float)):
                    # Конвертируем из миллисекунд или секунд
                    if ts > 1e10:  # миллисекунды
                        timestamps.append(datetime.fromtimestamp(ts / 1000))
                    else:  # секунды
                        timestamps.append(datetime.fromtimestamp(ts))

            if timestamps:
                # Округляем timestamp'ы до начала минуты перед загрузкой баров
                # чтобы избежать проблем с точными timestamp'ами из API
                start_time = self.aligner.floor_to_minute(min(timestamps))
                end_time = self.aligner.floor_to_minute(max(timestamps))
                # Расширяем диапазон на 1 минуту в каждую сторону для безопасности
                start_time = start_time - timedelta(minutes=1)
                end_time = end_time + timedelta(minutes=1)
                bar_timestamps = self.aligner.load_bar_timestamps(
                    symbol=symbol,
                    timeframe="1m",
                    start_time=start_time,
                    end_time=end_time,
                )
            else:
                logger.warning(
                    f"Не удалось определить timestamps из records для {symbol}"
                )
                return []

        if not bar_timestamps:
            logger.warning(f"Нет баров OHLCV для {symbol} 1m")
            return []

        # Определяем тип данных по полям записи
        first_record = records[0]
        data_type = self._detect_data_type(first_record)

        if data_type == "funding":
            return self._normalize_funding(records, symbol, bar_timestamps)
        elif data_type == "oi":
            return self._normalize_oi(records, symbol, bar_timestamps)
        elif data_type == "l2":
            return self._normalize_l2(records, symbol, bar_timestamps)
        else:
            logger.warning(f"Неизвестный тип данных: {data_type}")
            return []

    def _detect_data_type(self, record: dict[str, Any]) -> str:
        """Определяет тип данных по полям записи"""
        if "funding_rate" in record or "fundingRate" in record:
            return "funding"
        elif "open_interest" in record or "oi" in record:
            return "oi"
        elif "bid_imbalance" in record or "bids" in record:
            return "l2"
        return "unknown"

    def _normalize_funding(
        self,
        records: list[dict[str, Any]],
        symbol: str,
        bar_timestamps: list[datetime],
    ) -> list[dict[str, Any]]:
        """
        Нормализует funding rates к ближайшим барам (nearest strategy).
        """
        normalized = []
        for record in records:
            ts = self._extract_timestamp(record)
            if not ts:
                continue

            # Привязываем к ближайшему бару
            bar_ts = self.aligner.align_to_bar(ts, bar_timestamps, strategy="nearest")
            if bar_ts:
                normalized_record = record.copy()
                normalized_record["bar_timestamp"] = bar_ts
                normalized_record["timeframe"] = "1m"
                normalized.append(normalized_record)

        return normalized

    def _normalize_oi(
        self,
        records: list[dict[str, Any]],
        symbol: str,
        bar_timestamps: list[datetime],
    ) -> list[dict[str, Any]]:
        """
        Нормализует Open Interest: последнее значение в каждом баре.
        """
        # Группируем записи по bar_timestamp один раз (O(n))
        from collections import defaultdict

        bar_groups: dict[datetime, list[tuple[datetime, dict[str, Any]]]] = defaultdict(
            list
        )

        for record in records:
            ts = self._extract_timestamp(record)
            if not ts:
                continue
            bar_ts = self.aligner.align_to_bar(ts, bar_timestamps, strategy="floor")
            if bar_ts:
                bar_groups[bar_ts].append((ts, record))

        # Для каждого бара берём последнюю запись
        bar_data: dict[datetime, dict[str, Any]] = {}
        for bar_ts, group in bar_groups.items():
            # Сортируем по ts, берём последний
            group.sort(key=lambda x: x[0])
            ts, record = group[-1]
            oi_value = record.get("open_interest") or record.get("oi")
            if oi_value is not None:
                bar_data[bar_ts] = {
                    "symbol": symbol,
                    "timestamp": ts,
                    "bar_timestamp": bar_ts,
                    "timeframe": "1m",
                    "open_interest": float(oi_value),
                    "source": record.get("source", "okx"),
                }

        last_oi_value: float | None = None

        # Forward fill для пропущенных баров
        normalized = []
        for bar_ts in sorted(bar_timestamps):
            if bar_ts in bar_data:
                normalized.append(bar_data[bar_ts])
                last_oi_value = bar_data[bar_ts].get("open_interest")
            elif last_oi_value is not None:
                # Forward fill от предыдущего бара
                normalized.append(
                    {
                        "symbol": symbol,
                        "timestamp": bar_ts,  # Используем bar_timestamp как timestamp
                        "bar_timestamp": bar_ts,
                        "timeframe": "1m",
                        "open_interest": last_oi_value,
                        "source": "okx",
                    }
                )

        return normalized

    def _normalize_l2(
        self,
        records: list[dict[str, Any]],
        symbol: str,
        bar_timestamps: list[datetime],
    ) -> list[dict[str, Any]]:
        """
        Нормализует L2 данные: последний snapshot в каждом баре.
        """
        # Группируем записи по bar_timestamp один раз (O(n))
        from collections import defaultdict

        bar_groups: dict[datetime, list[tuple[datetime, dict[str, Any]]]] = defaultdict(
            list
        )

        for record in records:
            ts = self._extract_timestamp(record)
            if not ts:
                continue
            bar_ts = self.aligner.align_to_bar(ts, bar_timestamps, strategy="floor")
            if bar_ts:
                bar_groups[bar_ts].append((ts, record))

        # Для каждого бара берём последний snapshot
        bar_data: dict[datetime, dict[str, Any]] = {}
        for bar_ts, group in bar_groups.items():
            group.sort(key=lambda x: x[0])
            ts, record = group[-1]
            bar_data[bar_ts] = {
                "symbol": symbol,
                "timestamp": ts,
                "bar_timestamp": bar_ts,
                "timeframe": "1m",
                "bid_imbalance": record.get("bid_imbalance"),
                "ask_imbalance": record.get("ask_imbalance"),
                "spread_bps": record.get("spread_bps"),
                "source": record.get("source", "okx"),
            }

        return list(bar_data.values())

    def _extract_timestamp(self, record: dict[str, Any]) -> datetime | None:
        """Извлекает timestamp из записи"""
        ts = record.get("timestamp") or record.get("ts")
        if isinstance(ts, datetime):
            return ts
        elif isinstance(ts, (int, float)):
            # Конвертируем из миллисекунд или секунд
            if ts > 1e10:  # миллисекунды
                return datetime.fromtimestamp(ts / 1000)
            else:  # секунды
                return datetime.fromtimestamp(ts)
        return None

    # =========================================================================
    # v2: Нормализация из raw.market_data_ext_raw
    # =========================================================================

    def normalize_from_raw(
        self,
        engine: Engine,
        symbol: str,
        data_type: Literal["funding", "oi", "l2"],
        start_ts: datetime,
        end_ts: datetime,
        run_id: str,
    ) -> list[dict[str, Any]]:
        """Нормализует данные из raw.market_data_ext_raw.

        Args:
            engine: SQLAlchemy engine.
            symbol: Символ инструмента.
            data_type: Тип данных.
            start_ts: Начало периода.
            end_ts: Конец периода.
            run_id: ID запуска для трассировки.

        Returns:
            Список нормализованных записей с bar_timestamp, algo_version, params_hash.
        """
        from sqlalchemy import text

        # Загружаем сырые данные из raw
        sql = text(
            """
            SELECT symbol, ts, payload
            FROM raw.market_data_ext_raw
            WHERE data_type = :data_type
              AND symbol = :symbol
              AND ts >= :start_ts
              AND ts < :end_ts
            ORDER BY ts
        """
        )

        with engine.connect() as conn:
            result = conn.execute(
                sql,
                {
                    "data_type": data_type,
                    "symbol": symbol,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                },
            )
            raw_records = [
                {"symbol": row.symbol, "ts": row.ts, "payload": row.payload}
                for row in result
            ]

        if not raw_records:
            logger.info(
                f"Нет raw данных для {symbol}/{data_type} за {start_ts}-{end_ts}"
            )
            return []

        # Преобразуем payload в плоские записи
        records = []
        for raw in raw_records:
            payload = raw["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            record = {**payload, "ts": raw["ts"], "symbol": raw["symbol"]}
            records.append(record)

        # Нормализуем к барам
        normalized = self.normalize_to_1m_bars(records, symbol)

        # Добавляем версионирование
        params_hash = self._compute_params_hash(data_type)
        for rec in normalized:
            rec["algo_version"] = ALGO_VERSION
            rec["run_id"] = run_id
            rec["params_hash"] = params_hash

        return normalized

    def _compute_params_hash(self, data_type: str) -> str:
        """
        Вычисляет хеш параметров нормализации из контракта.

        Args:
            data_type: Тип данных (funding, oi, l2) — для совместимости,
                но хеш теперь единый из контракта.

        Returns:
            Hex-строка хеша (16 символов).
        """
        from ..domain.contract import get_params_hash

        return get_params_hash()
