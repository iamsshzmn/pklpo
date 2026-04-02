"""Functions for feature-related database access."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import text

from src.features.storage_contract import IndicatorStorageContract

_TIMEFRAME_TO_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1H": 3600,
    "4H": 14400,
    "12H": 43200,
    "1D": 86400,
    "1W": 604800,
    "1M": 2592000,
}


def _month_start(dt: datetime) -> datetime:
    normalized = dt.astimezone(UTC)
    return datetime(normalized.year, normalized.month, 1, tzinfo=UTC)


def _add_month(dt: datetime, months: int) -> datetime:
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    return datetime(year, month, 1, tzinfo=UTC)


def _timeframe_to_seconds(timeframe: str) -> int:
    return _TIMEFRAME_TO_SECONDS.get(timeframe, 60)


def build_ohlcv_partition_pruning_window_ms(
    *,
    timeframe: str,
    since_ts: int | None,
    limit: int,
    now_utc: datetime | None = None,
) -> tuple[int, int]:
    """Return an inclusive/exclusive timestamp window for monthly partition pruning."""
    now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    horizon_seconds = max(limit, 1) * _timeframe_to_seconds(timeframe)
    lower_anchor = (
        datetime.fromtimestamp(since_ts, tz=UTC)
        if since_ts is not None
        else datetime.fromtimestamp(max(0, int(now.timestamp()) - horizon_seconds), tz=UTC)
    )
    lower_bound = _month_start(lower_anchor)
    upper_bound = _add_month(_month_start(now), 1)
    return int(lower_bound.timestamp() * 1000), int(upper_bound.timestamp() * 1000)


async def fetch_latest_ts(session, symbol: str, timeframe: str) -> int | None:
    """Return the latest indicator timestamp in seconds for a symbol/timeframe."""
    res = await session.execute(
        text(
            f"""
            SELECT timestamp
            FROM {IndicatorStorageContract.table_name}
            WHERE symbol = :symbol
              AND timeframe = :timeframe
            ORDER BY timestamp DESC
            LIMIT 1
            """
        ),
        {"symbol": symbol, "timeframe": timeframe},
    )
    latest_ms = res.scalar_one_or_none()
    return (latest_ms // 1000) if latest_ms else None


async def ensure_columns_exist(session, table: str, columns: list[str]) -> None:
    from src.db.db_schema_utils import ensure_columns

    await ensure_columns(session, table, columns)


async def get_symbol_timeframes_to_update(session):
    """Return (symbol, timeframe) pairs with new OHLCV rows to process."""
    result = await session.execute(
        text(
            f"""
            WITH latest_indicators AS (
                SELECT symbol, timeframe, MAX(timestamp) AS max_ts_ms
                FROM {IndicatorStorageContract.table_name}
                GROUP BY symbol, timeframe
            )
            SELECT o.symbol, o.timeframe
            FROM swap_ohlcv_p o
            LEFT JOIN latest_indicators i
              ON i.symbol = o.symbol
             AND i.timeframe = o.timeframe
            WHERE o.timestamp > COALESCE(i.max_ts_ms, 0)
            GROUP BY o.symbol, o.timeframe
            """
        )
    )
    return result.all()


async def fetch_ohlcv_df(
    session, symbol: str, timeframe: str, since_ts: int | None = None, limit: int = 200
) -> pd.DataFrame | None:
    """Load OHLCV data from swap_ohlcv_p using timestamp bounds for partition pruning."""
    from_ts_ms, to_ts_ms = build_ohlcv_partition_pruning_window_ms(
        timeframe=timeframe,
        since_ts=since_ts,
        limit=limit,
    )

    params = {
        "symbol": symbol,
        "timeframe": timeframe,
        "from_ts_ms": from_ts_ms,
        "to_ts_ms": to_ts_ms,
        "limit": int(limit),
    }
    query = """
        SELECT timestamp, open, high, low, close, volume
        FROM swap_ohlcv_p
        WHERE symbol = :symbol
          AND timeframe = :timeframe
          AND timestamp >= :from_ts_ms
          AND timestamp < :to_ts_ms
    """
    if since_ts is not None:
        query += " AND timestamp > :since_ts_ms"
        params["since_ts_ms"] = since_ts * 1000

    query += """
        ORDER BY timestamp DESC
        LIMIT :limit
    """

    res = await session.execute(text(query), params)
    rows = res.fetchall()
    if not rows:
        return None

    df = pd.DataFrame(
        [
            {
                "ts": int(row[0]) // 1000,
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]) if row[5] is not None else 0.0,
            }
            for row in reversed(rows)
        ]
    )
    df.name = symbol
    df.timeframe = timeframe
    return df
