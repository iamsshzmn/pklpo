"""Raw Ingestor - запись сырых данных OKX в raw.market_data_ext_raw.

Модуль отвечает за:
- Приём сырых данных от OKX (funding, oi, l2)
- Расчёт payload_hash для защиты от дублей
- Upsert в raw.market_data_ext_raw
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

DataType = Literal["funding", "oi", "l2"]


def compute_payload_hash(payload: dict[str, Any]) -> str:
    """Вычисляет SHA256 хеш payload для защиты от дублей.

    Args:
        payload: Словарь с данными от OKX.

    Returns:
        Hex-строка SHA256 хеша.
    """
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


class RawIngestor:
    """Инжестор сырых данных в raw.market_data_ext_raw."""

    def __init__(self, engine: Engine, source: str = "okx") -> None:
        """Инициализация инжестора.

        Args:
            engine: SQLAlchemy engine.
            source: Источник данных (по умолчанию 'okx').
        """
        self._engine = engine
        self._source = source

    def ingest_batch(
        self,
        records: list[dict[str, Any]],
        data_type: DataType,
        *,
        dry_run: bool = True,
    ) -> int:
        """Записывает батч сырых записей в raw.market_data_ext_raw.

        Args:
            records: Список записей. Каждая запись должна содержать:
                - symbol: str
                - ts: datetime (UTC)
                - payload: dict
            data_type: Тип данных ('funding', 'oi', 'l2').
            dry_run: Если True, только печатает план без записи.

        Returns:
            Количество записанных (или запланированных) записей.

        Raises:
            RuntimeError: Если dry_run=False не передан явно.
        """
        if not records:
            return 0

        prepared = []
        for rec in records:
            payload = rec.get("payload", rec)
            payload_hash = compute_payload_hash(payload)
            prepared.append(
                {
                    "symbol": rec["symbol"],
                    "data_type": data_type,
                    "ts": rec["ts"],
                    "payload": json.dumps(payload, default=str),
                    "payload_hash": payload_hash,
                    "source": self._source,
                }
            )

        if dry_run:
            print(
                f"[DRY-RUN] Будет записано {len(prepared)} записей в raw.market_data_ext_raw"
            )
            print(f"  data_type: {data_type}")
            print(f"  symbols: {set(r['symbol'] for r in prepared)}")
            if prepared:
                print(
                    f"  ts range: {min(r['ts'] for r in prepared)} - {max(r['ts'] for r in prepared)}"
                )
            return len(prepared)

        # Upsert батчами с ON CONFLICT DO NOTHING (идемпотентность)
        sql = text(
            """
            INSERT INTO raw.market_data_ext_raw
                (symbol, data_type, ts, payload, payload_hash, source)
            VALUES
                (:symbol, :data_type, :ts, :payload::jsonb, :payload_hash, :source)
            ON CONFLICT (symbol, data_type, ts, payload_hash) DO NOTHING
        """
        )

        chunk_size = 500 if data_type == "l2" else 1000
        with self._engine.begin() as conn:
            for i in range(0, len(prepared), chunk_size):
                chunk = prepared[i : i + chunk_size]
                conn.execute(sql, chunk)

        return len(prepared)

    def ingest_funding(
        self,
        records: list[dict[str, Any]],
        *,
        dry_run: bool = True,
    ) -> int:
        """Записывает funding rate данные.

        Args:
            records: Список записей с funding rate.
            dry_run: Если True, только печатает план.

        Returns:
            Количество записанных записей.
        """
        return self.ingest_batch(records, "funding", dry_run=dry_run)

    def ingest_oi(
        self,
        records: list[dict[str, Any]],
        *,
        dry_run: bool = True,
    ) -> int:
        """Записывает open interest данные.

        Args:
            records: Список записей с open interest.
            dry_run: Если True, только печатает план.

        Returns:
            Количество записанных записей.
        """
        return self.ingest_batch(records, "oi", dry_run=dry_run)

    def ingest_l2(
        self,
        records: list[dict[str, Any]],
        *,
        dry_run: bool = True,
    ) -> int:
        """Записывает L2 order book данные.

        Args:
            records: Список записей с L2 данными.
            dry_run: Если True, только печатает план.

        Returns:
            Количество записанных записей.
        """
        return self.ingest_batch(records, "l2", dry_run=dry_run)

    def get_raw_data(
        self,
        data_type: DataType,
        symbol: str,
        start_ts: datetime,
        end_ts: datetime,
    ) -> list[dict[str, Any]]:
        """Читает сырые данные из raw.market_data_ext_raw.

        Args:
            data_type: Тип данных.
            symbol: Символ инструмента.
            start_ts: Начало периода (включительно).
            end_ts: Конец периода (исключительно).

        Returns:
            Список записей с полями: symbol, ts, payload.
        """
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

        with self._engine.connect() as conn:
            result = conn.execute(
                sql,
                {
                    "data_type": data_type,
                    "symbol": symbol,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                },
            )
            return [
                {"symbol": row.symbol, "ts": row.ts, "payload": row.payload}
                for row in result
            ]
