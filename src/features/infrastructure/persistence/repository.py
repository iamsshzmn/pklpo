"""
Repository adapters for indicator persistence.

This module binds the domain-level IndicatorRepository protocol to the current
SQLAlchemy-based persistence implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
from sqlalchemy import text

from src.models import INDICATORS_TABLE_NAME

from .inserter import insert_indicators

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ...domain.protocols import IndicatorRepository


class SqlAlchemyIndicatorRepository:
    """IndicatorRepository adapter backed by AsyncSession + insert_indicators()."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_batch(
        self,
        records: list[dict],
        symbol: str,
        timeframe: str,
    ) -> int:
        if not records:
            return 0

        df = pd.DataFrame.from_records(records)
        return await self.save_batch_from_df(df, symbol, timeframe)

    async def save_batch_from_df(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
    ) -> int:
        return await insert_indicators(
            session=self._session,
            ind_df=df,
            symbol=symbol,
            timeframe=timeframe,
        )

    async def validate_connection(self) -> dict[str, object]:
        """Validate DB connectivity and target indicators table structure."""
        try:
            result = await self._session.execute(text("SELECT 1"))
            connection_ok = result.scalar() == 1

            table_check = await self._session.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT FROM information_schema.tables "
                    "WHERE table_name = :table_name"
                    ")"
                ),
                {"table_name": INDICATORS_TABLE_NAME},
            )
            table_exists = table_check.scalar()

            columns: list[dict[str, str]] = []
            if table_exists:
                columns_result = await self._session.execute(
                    text(
                        "SELECT column_name, data_type "
                        "FROM information_schema.columns "
                        "WHERE table_name = :table_name "
                        "ORDER BY ordinal_position"
                    ),
                    {"table_name": INDICATORS_TABLE_NAME},
                )
                columns = [
                    {"name": row[0], "type": row[1]}
                    for row in columns_result.fetchall()
                ]

            return {
                "connection_ok": connection_ok,
                "table_exists": table_exists,
                "columns": columns,
                "valid": connection_ok and table_exists,
            }
        except Exception as exc:
            return {
                "connection_ok": False,
                "table_exists": False,
                "error": str(exc),
                "valid": False,
            }

    async def verify_integrity(
        self,
        symbol: str,
        timeframe: str,
    ) -> dict[str, object]:
        """Verify stored rows consistency for a symbol/timeframe slice."""
        try:
            await self._session.execute(text("SET statement_timeout = '60s'"))

            count_result = await self._session.execute(
                text(
                    f"SELECT COUNT(*) FROM {INDICATORS_TABLE_NAME} "
                    "WHERE symbol = :symbol AND timeframe = :timeframe"
                ),
                {"symbol": symbol, "timeframe": timeframe},
            )
            total_count = count_result.scalar()

            ts_result = await self._session.execute(
                text(
                    "SELECT MIN(timestamp), MAX(timestamp), COUNT(DISTINCT timestamp) "
                    f"FROM {INDICATORS_TABLE_NAME} "
                    "WHERE symbol = :symbol AND timeframe = :timeframe"
                ),
                {"symbol": symbol, "timeframe": timeframe},
            )
            ts_data = ts_result.fetchone()

            duplicate_result = await self._session.execute(
                text(
                    "SELECT COUNT(*) FROM ("
                    "  SELECT symbol, timeframe, timestamp, COUNT(*) "
                    f"  FROM {INDICATORS_TABLE_NAME} "
                    "  WHERE symbol = :symbol AND timeframe = :timeframe "
                    "  GROUP BY symbol, timeframe, timestamp "
                    "  HAVING COUNT(*) > 1"
                    ") duplicates"
                ),
                {"symbol": symbol, "timeframe": timeframe},
            )
            duplicate_count = duplicate_result.scalar()

            return {
                "total_count": total_count,
                "min_timestamp": ts_data[0] if ts_data else None,
                "max_timestamp": ts_data[1] if ts_data else None,
                "unique_timestamps": ts_data[2] if ts_data else 0,
                "duplicate_count": duplicate_count,
                "integrity_ok": duplicate_count == 0,
                "timestamp_range_ok": bool(ts_data and ts_data[0] is not None),
            }
        except Exception as exc:
            return {"error": str(exc), "integrity_ok": False}


def create_indicator_repository(session: AsyncSession) -> IndicatorRepository:
    """Create the default persistence adapter for features save use cases."""

    return SqlAlchemyIndicatorRepository(session)
