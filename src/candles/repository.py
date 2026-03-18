from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import select, text

from src.models import Instrument
from src.utils.session_utils import get_db_session


class SwapCandlesRepository:
    async def upsert_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
        additional_data: dict[str, Any],
    ) -> int:
        if not candles:
            return 0

        funding_rate = None
        if additional_data.get("funding_rate"):
            funding_rate = additional_data["funding_rate"].get("fundingRate")

        open_interest = None
        if additional_data.get("open_interest"):
            open_interest = additional_data["open_interest"].get("oi")

        rows: list[dict[str, Any]] = []
        now = datetime.datetime.utcnow()
        for candle in candles:
            rows.append(
                {
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
                    "fetched_at": now,
                    "funding_rate": funding_rate,
                    "open_interest": open_interest,
                }
            )

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
                fetched_at,
                funding_rate,
                open_interest
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
                :fetched_at,
                :funding_rate,
                :open_interest
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
                fetched_at = EXCLUDED.fetched_at,
                funding_rate = EXCLUDED.funding_rate,
                open_interest = EXCLUDED.open_interest
            """
        )

        async with get_db_session() as session:
            try:
                await session.execute(stmt, rows)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        return len(rows)

    async def list_swap_symbols(self) -> list[str]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Instrument.symbol).where(
                    Instrument.settle_ccy == "USDT",
                    Instrument.inst_type == "SWAP",
                )
            )
            symbols = [row[0] for row in result.fetchall()]
        return sorted(symbols)

    async def get_latest_timestamp(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> int | None:
        async with get_db_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT MAX(timestamp)
                    FROM swap_ohlcv_p
                    WHERE symbol = :symbol AND timeframe = :timeframe
                    """
                ),
                {"symbol": symbol, "timeframe": timeframe},
            )
            latest_ts = result.scalar()
        return int(latest_ts) if latest_ts is not None else None

    async def get_instrument_counts(self) -> dict[str, int]:
        async with get_db_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        COUNT(*) AS all_count,
                        COUNT(*) FILTER (WHERE inst_type = 'SWAP') AS swap_count,
                        COUNT(*) FILTER (WHERE settle_ccy = 'USDT') AS usdt_count
                    FROM instruments
                    """
                )
            )
            row = result.fetchone()

        return {
            "all": int((row[0] if row else 0) or 0),
            "swap": int((row[1] if row else 0) or 0),
            "usdt": int((row[2] if row else 0) or 0),
        }

    async def get_fill_stats(
        self,
        start_timestamp_ms: int,
    ) -> dict[str, int | float]:
        async with get_db_session() as session:
            q_total = await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM swap_ohlcv_p WHERE timestamp >= :t
                    """
                ),
                {"t": start_timestamp_ms},
            )
            rows_today = int(q_total.scalar() or 0)

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
                {"t": start_timestamp_ms},
            )
            fr, oi = q_fill.fetchone()

        funding_rate_non_null = int(fr or 0)
        open_interest_non_null = int(oi or 0)
        funding_rate_fill_pct = (
            round(100.0 * funding_rate_non_null / rows_today, 2) if rows_today else 0.0
        )
        open_interest_fill_pct = (
            round(100.0 * open_interest_non_null / rows_today, 2) if rows_today else 0.0
        )

        return {
            "rows_today": rows_today,
            "funding_rate_non_null": funding_rate_non_null,
            "open_interest_non_null": open_interest_non_null,
            "funding_rate_fill_pct": funding_rate_fill_pct,
            "open_interest_fill_pct": open_interest_fill_pct,
        }

    async def upsert_swap_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
        additional_data: dict[str, Any],
    ) -> int:
        return await self.upsert_candles(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            additional_data=additional_data,
        )

    async def fetch_swap_usdt_symbols(self) -> list[str]:
        return await self.list_swap_symbols()

    async def fetch_latest_timestamp_ms(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> int | None:
        return await self.get_latest_timestamp(symbol=symbol, timeframe=timeframe)

    async def fetch_instrument_counts(self) -> dict[str, int]:
        return await self.get_instrument_counts()

    async def fetch_today_fill_stats(
        self,
        start_timestamp_ms: int,
    ) -> dict[str, int | float]:
        return await self.get_fill_stats(start_timestamp_ms)
