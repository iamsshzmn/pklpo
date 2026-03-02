from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from src.utils.session_utils import get_db_session


async def fetch_swap_status() -> dict[str, Any] | None:
    async with get_db_session() as session:
        stats_query = text(
            """
            SELECT
                COUNT(DISTINCT symbol) as total_symbols,
                COUNT(DISTINCT timeframe) as total_timeframes,
                COUNT(*) as total_records,
                MIN(timestamp) as earliest_timestamp,
                MAX(timestamp) as latest_timestamp,
                MIN(fetched_at) as earliest_fetch,
                MAX(fetched_at) as latest_fetch
            FROM swap_ohlcv_p
            """
        )
        result = await session.execute(stats_query)
        stats = result.fetchone()
        if not stats or stats[0] == 0:
            return None

        symbols_query = text(
            """
            SELECT
                symbol,
                COUNT(*) as records,
                COUNT(DISTINCT timeframe) as timeframes,
                MAX(fetched_at) as last_update
            FROM swap_ohlcv_p
            GROUP BY symbol
            ORDER BY records DESC
            LIMIT 10
            """
        )
        result = await session.execute(symbols_query)
        symbols = result.fetchall()

        timeframes_query = text(
            """
            SELECT
                timeframe,
                COUNT(*) as records,
                COUNT(DISTINCT symbol) as symbols
            FROM swap_ohlcv_p
            GROUP BY timeframe
            ORDER BY records DESC
            """
        )
        result = await session.execute(timeframes_query)
        timeframes = result.fetchall()

    return {
        "stats": stats,
        "symbols": symbols,
        "timeframes": timeframes,
    }


async def fetch_symbol_details(symbol: str) -> dict[str, Any] | None:
    async with get_db_session() as session:
        info_query = text(
            """
            SELECT
                symbol,
                COUNT(DISTINCT timeframe) as timeframes,
                COUNT(*) as total_records,
                MIN(timestamp) as earliest_ts,
                MAX(timestamp) as latest_ts,
                MIN(fetched_at) as earliest_fetch,
                MAX(fetched_at) as latest_fetch,
                AVG(volume) as avg_volume,
                AVG(COALESCE(funding_rate, 0)) as avg_funding_rate,
                COUNT(CASE WHEN funding_rate IS NOT NULL THEN 1 END) as funding_rate_records,
                COUNT(CASE WHEN open_interest IS NOT NULL THEN 1 END) as open_interest_records
            FROM swap_ohlcv_p
            WHERE symbol = :symbol
            GROUP BY symbol
            """
        )
        result = await session.execute(info_query, {"symbol": symbol})
        info = result.fetchone()
        if not info:
            return None

        timeframes_query = text(
            """
            SELECT
                timeframe,
                COUNT(*) as records,
                MIN(timestamp) as earliest_ts,
                MAX(timestamp) as latest_ts,
                MAX(fetched_at) as last_update
            FROM swap_ohlcv_p
            WHERE symbol = :symbol
            GROUP BY timeframe
            ORDER BY timeframe
            """
        )
        result = await session.execute(timeframes_query, {"symbol": symbol})
        timeframes = result.fetchall()

    return {
        "info": info,
        "timeframes": timeframes,
    }


async def cleanup_swap_data(days: int) -> tuple[int, int]:
    cutoff_timestamp = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    async with get_db_session() as session:
        count_query = text(
            """
            SELECT COUNT(*) FROM swap_ohlcv_p
            WHERE timestamp < :cutoff_timestamp
            """
        )
        result = await session.execute(count_query, {"cutoff_timestamp": cutoff_timestamp})
        count = int(result.scalar() or 0)
        if count == 0:
            return 0, 0

        delete_query = text(
            """
            DELETE FROM swap_ohlcv_p
            WHERE timestamp < :cutoff_timestamp
            """
        )
        result = await session.execute(delete_query, {"cutoff_timestamp": cutoff_timestamp})
        await session.commit()
        return count, int(result.rowcount or 0)


async def export_swap_symbol_data(
    symbol: str, timeframes: list[str] | None = None
) -> list[dict[str, Any]]:
    base_query = """
        SELECT
            symbol, timeframe, timestamp, open, high, low, close, volume,
            vol_ccy, vol_usd, funding_rate, open_interest,
            long_short_ratio, long_account_ratio, short_account_ratio,
            top_long_short_ratio, top_long_account_ratio, top_short_account_ratio,
            fetched_at
        FROM swap_ohlcv_p
        WHERE symbol = :symbol
    """
    params: dict[str, Any] = {"symbol": symbol}
    if timeframes:
        placeholders = []
        for i, tf in enumerate(timeframes):
            key = f"tf_{i}"
            placeholders.append(f":{key}")
            params[key] = tf
        base_query += f" AND timeframe IN ({', '.join(placeholders)})"
    base_query += " ORDER BY timeframe, timestamp"

    async with get_db_session() as session:
        result = await session.execute(text(base_query), params)
        rows = result.fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "symbol": row[0],
                "timeframe": row[1],
                "timestamp": row[2],
                "open": float(row[3]),
                "high": float(row[4]),
                "low": float(row[5]),
                "close": float(row[6]),
                "volume": float(row[7]),
                "vol_ccy": float(row[8]) if row[8] is not None else None,
                "vol_usd": float(row[9]) if row[9] is not None else None,
                "funding_rate": float(row[10]) if row[10] is not None else None,
                "open_interest": float(row[11]) if row[11] is not None else None,
                "long_short_ratio": float(row[12]) if row[12] is not None else None,
                "long_account_ratio": float(row[13]) if row[13] is not None else None,
                "short_account_ratio": float(row[14]) if row[14] is not None else None,
                "top_long_short_ratio": float(row[15]) if row[15] is not None else None,
                "top_long_account_ratio": float(row[16]) if row[16] is not None else None,
                "top_short_account_ratio": float(row[17]) if row[17] is not None else None,
                "fetched_at": row[18].isoformat() if row[18] else None,
            }
        )
    return out
