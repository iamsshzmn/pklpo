from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
from sqlalchemy import text

from ..domain.timeframe import timeframe_to_seconds as _domain_timeframe_to_seconds

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ..ports import FeatureStorageGateway

_TIMEFRAME_LIMITS = {
    "1m": 15000,
    "5m": 10000,
    "15m": 5000,
    "30m": 4000,
    "1H": 3000,
    "4H": 2000,
    "12H": 1500,
    "1D": 1000,
    "1W": 500,
    "1M": 300,
}

_TIMEFRAME_TIMEOUTS = {
    "1m": 600,
    "5m": 450,
    "15m": 300,
    "30m": 300,
    "1H": 240,
    "4H": 180,
    "12H": 150,
    "1D": 120,
    "1W": 90,
    "1M": 60,
}

OHLCV_TIMESTAMP_COLUMN = "timestamp"


def timeframe_to_seconds(timeframe: str) -> int:
    return _domain_timeframe_to_seconds(timeframe)


def limit_for_timeframe(timeframe: str) -> int:
    return _TIMEFRAME_LIMITS.get(timeframe, 5000)


def timeout_for_timeframe(timeframe: str) -> int:
    return _TIMEFRAME_TIMEOUTS.get(timeframe, 300)


async def get_last_calculated_ts(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
    storage_gateway: FeatureStorageGateway,
) -> int | None:
    return await storage_gateway.fetch_latest_ts(session, symbol, timeframe)


async def check_has_new_ohlcv(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
    last_feature_ts: int | None,
    *,
    ohlcv_timestamp_column: str = OHLCV_TIMESTAMP_COLUMN,
) -> tuple[bool, int | None]:
    latest_ohlcv_ts_ms = (
        await session.execute(
            text(
                f"""
                SELECT {ohlcv_timestamp_column}
                FROM swap_ohlcv_p
                WHERE symbol = :symbol AND timeframe = :tf
                ORDER BY {ohlcv_timestamp_column} DESC
                LIMIT 1
                """
            ),
            {"symbol": symbol, "tf": timeframe},
        )
    ).scalar()

    if not latest_ohlcv_ts_ms:
        return (False, None)

    latest_ohlcv_ts_seconds = latest_ohlcv_ts_ms // 1000
    if last_feature_ts is None:
        return (True, latest_ohlcv_ts_seconds)
    return (latest_ohlcv_ts_seconds > last_feature_ts, latest_ohlcv_ts_seconds)


async def get_ohlcv_window(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
    from_ts: int | None,
    storage_gateway: FeatureStorageGateway,
    *,
    warmup_bars: int = 500,
    timeframe_limits: dict[str, int] | None = None,
) -> pd.DataFrame:
    limits = timeframe_limits or _TIMEFRAME_LIMITS
    warmup_ts = None
    if from_ts:
        warmup_ts = from_ts - (warmup_bars * timeframe_to_seconds(timeframe))

    df = await storage_gateway.fetch_ohlcv_df(
        session,
        symbol=symbol,
        timeframe=timeframe,
        since_ts=warmup_ts,
        limit=limits.get(timeframe, 5000),
    )

    if df is None or len(df) == 0:
        return pd.DataFrame()

    normalized = df.copy()
    normalized["timestamp"] = normalized["ts"] * 1000
    return normalized[["timestamp", "open", "high", "low", "close", "volume"]]
