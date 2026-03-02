"""Репозиторий для работы с combination_features."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy import MetaData, Table, text

from ..domain.models import CombinationRow
from ..logging_config import get_combinations_logger
from .upsert_helper import build_and_execute_upsert

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_combinations_logger("repository")


class CombinationRepository(Protocol):
    """Протокол репозитория для комбинаций фичей."""

    async def upsert_batch(self, rows: Iterable[CombinationRow]) -> int:
        """Сохранить или обновить батч строк."""
        ...

    async def load_for_range(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | None,
        end: datetime | None,
    ) -> list[CombinationRow]:
        """Загрузить строки за период."""
        ...

    async def load_latest(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[CombinationRow]:
        """Загрузить последние N строк."""
        ...


class PostgresCombinationRepository:
    """PostgreSQL реализация репозитория."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._table: Table | None = None

    async def _get_table(self) -> Table:
        """Получить отражённую таблицу."""
        if self._table is None:
            metadata = MetaData()

            # Используем run_sync для reflection в async контексте
            def _reflect_table(sync_conn):
                """Выполняет reflection синхронно."""
                from sqlalchemy import BigInteger, Column, Text
                from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMPTZ

                # Создаём таблицу с явными колонками (проще чем reflection)
                return Table(
                    "combination_features",
                    metadata,
                    Column("symbol", Text, primary_key=True),
                    Column("timeframe", Text, primary_key=True),
                    Column("timestamp", BigInteger, primary_key=True),
                    Column("combination_id", Text, primary_key=True),
                    Column("features", JSONB, nullable=False),
                    Column("meta", JSONB, nullable=True),
                    Column("created_at", TIMESTAMPTZ),
                    Column("updated_at", TIMESTAMPTZ),
                    schema="public",
                )

            self._table = await self.session.run_sync(_reflect_table)

        # После создания _table гарантированно не None
        assert self._table is not None
        return self._table

    def _row_to_dict(self, row: CombinationRow) -> dict[str, Any]:
        """Преобразовать CombinationRow в dict для БД."""
        # Преобразуем timestamp в int (epoch_ms)
        if isinstance(row.timestamp, datetime):
            timestamp_ms = int(row.timestamp.timestamp() * 1000)
        else:
            timestamp_ms = int(row.timestamp)

        return {
            "symbol": row.symbol,
            "timeframe": row.timeframe,
            "timestamp": timestamp_ms,
            "combination_id": row.combination_id,
            "features": json.dumps(row.features),
            "meta": json.dumps(row.meta) if row.meta else None,
            "updated_at": datetime.utcnow(),
        }

    def _dict_to_row(self, d: dict[str, Any]) -> CombinationRow:
        """Преобразовать dict из БД в CombinationRow."""
        # Преобразуем timestamp обратно
        ts = d["timestamp"]
        timestamp = datetime.fromtimestamp(ts / 1000.0) if isinstance(ts, int) else ts

        # Парсим JSONB поля
        features = d["features"]
        if isinstance(features, str):
            features = json.loads(features)
        elif isinstance(features, dict):
            pass  # уже dict
        else:
            features = {}

        meta = d.get("meta")
        if isinstance(meta, str):
            meta = json.loads(meta)
        elif meta is None:
            meta = None

        return CombinationRow(
            symbol=d["symbol"],
            timeframe=d["timeframe"],
            timestamp=timestamp,
            combination_id=d["combination_id"],
            features=features,
            meta=meta,
        )

    async def upsert_batch(self, rows: Iterable[CombinationRow]) -> int:
        """Сохранить или обновить батч строк."""
        rows_list = list(rows)
        if not rows_list:
            logger.info("No rows to upsert")
            return 0

        table = await self._get_table()
        records = [self._row_to_dict(row) for row in rows_list]

        # Получаем колонки БД
        db_cols_query = text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'combination_features'
            AND table_schema = 'public'
        """
        )
        result = await self.session.execute(db_cols_query)
        db_cols = {row[0] for row in result.all()}

        saved = await build_and_execute_upsert(
            session=self.session,
            model_class=table,
            records=records,
            db_cols=db_cols,
            pk=("symbol", "timeframe", "timestamp", "combination_id"),
            required_fields={"symbol", "timeframe", "timestamp", "combination_id"},
        )

        logger.info(f"Upserted {saved} combination rows")
        return saved

    async def load_for_range(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | None,
        end: datetime | None,
    ) -> list[CombinationRow]:
        """Загрузить строки за период."""
        query = text(
            """
            SELECT symbol, timeframe, timestamp, combination_id, features, meta
            FROM combination_features
            WHERE symbol = :symbol AND timeframe = :timeframe
            AND (:start IS NULL OR timestamp >= :start_ts)
            AND (:end IS NULL OR timestamp <= :end_ts)
            ORDER BY timestamp ASC
        """
        )

        start_ts = int(start.timestamp() * 1000) if start else None
        end_ts = int(end.timestamp() * 1000) if end else None

        result = await self.session.execute(
            query,
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "start": start,
                "end": end,
                "start_ts": start_ts,
                "end_ts": end_ts,
            },
        )

        rows = []
        for row in result.all():
            d = {
                "symbol": row[0],
                "timeframe": row[1],
                "timestamp": row[2],
                "combination_id": row[3],
                "features": row[4],
                "meta": row[5],
            }
            rows.append(self._dict_to_row(d))

        logger.info(f"Loaded {len(rows)} combination rows for {symbol}/{timeframe}")
        return rows

    async def load_latest(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[CombinationRow]:
        """Загрузить последние N строк."""
        query = text(
            """
            SELECT symbol, timeframe, timestamp, combination_id, features, meta
            FROM combination_features
            WHERE symbol = :symbol AND timeframe = :timeframe
            ORDER BY timestamp DESC
            LIMIT :limit
        """
        )

        result = await self.session.execute(
            query,
            {"symbol": symbol, "timeframe": timeframe, "limit": limit},
        )

        rows = []
        for row in result.all():
            d = {
                "symbol": row[0],
                "timeframe": row[1],
                "timestamp": row[2],
                "combination_id": row[3],
                "features": row[4],
                "meta": row[5],
            }
            rows.append(self._dict_to_row(d))

        logger.info(
            f"Loaded {len(rows)} latest combination rows for {symbol}/{timeframe}"
        )
        return rows
