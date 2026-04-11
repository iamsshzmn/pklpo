from __future__ import annotations

from typing import Any

from sqlalchemy import text

from src.candles.repository import SwapCandlesRepository
from src.utils.session_utils import get_db_session


class RepairCandlesRepository(SwapCandlesRepository):
    async def list_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[int]:
        async def _operation() -> list[int]:
            async with get_db_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT timestamp
                        FROM swap_ohlcv_p
                        WHERE symbol = :symbol
                          AND timeframe = :timeframe
                          AND timestamp >= :start_ts_ms
                          AND timestamp < :end_ts_ms
                        ORDER BY timestamp
                        """
                    ),
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "start_ts_ms": start_ts_ms,
                        "end_ts_ms": end_ts_ms,
                    },
                )
                rows = result.fetchall()
            return [int(row[0]) for row in rows]

        return await self._run_with_db_retry(_operation)

    async def count_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> int:
        async def _operation() -> int:
            async with get_db_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM swap_ohlcv_p
                        WHERE symbol = :symbol
                          AND timeframe = :timeframe
                          AND timestamp >= :start_ts_ms
                          AND timestamp < :end_ts_ms
                        """
                    ),
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "start_ts_ms": start_ts_ms,
                        "end_ts_ms": end_ts_ms,
                    },
                )
                return int(result.scalar() or 0)

        return await self._run_with_db_retry(_operation)

    async def selective_upsert_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
    ) -> int:
        if not candles:
            return 0

        rows = [
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": candle["timestamp"],
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "volume": candle["volume"],
                "vol_ccy": candle.get("vol_ccy"),
                "vol_usd": candle.get("vol_usd"),
                "fetched_at": candle["fetched_at"],
            }
            for candle in candles
        ]

        stmt = text(
            """
            INSERT INTO swap_ohlcv_p (
                symbol,
                timeframe,
                timestamp,
                open,
                high,
                low,
                close,
                volume,
                vol_ccy,
                vol_usd,
                fetched_at
            )
            VALUES (
                :symbol,
                :timeframe,
                :timestamp,
                :open,
                :high,
                :low,
                :close,
                :volume,
                :vol_ccy,
                :vol_usd,
                :fetched_at
            )
            ON CONFLICT (symbol, timeframe, timestamp)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                vol_ccy = EXCLUDED.vol_ccy,
                vol_usd = EXCLUDED.vol_usd,
                fetched_at = EXCLUDED.fetched_at
            """
        )

        async def _operation() -> int:
            async with get_db_session() as session:
                try:
                    result = await session.execute(stmt, rows)
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
            return result.rowcount if result.rowcount >= 0 else len(rows)

        return int(await self._run_with_db_retry(_operation))
