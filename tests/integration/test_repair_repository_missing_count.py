from __future__ import annotations

import socket
import time
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.candles.infrastructure.repair_repository import RepairCandlesRepository
from src.config.env_validator import get_database_url


def _resolve_test_db_url() -> str | None:
    try:
        db_url = get_database_url()
    except Exception:
        return None
    if not db_url:
        return None
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if db_url.startswith("postgres://"):
        return db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return db_url


@pytest.mark.asyncio
@pytest.mark.integration
async def test_count_missing_timestamps_returns_nine_with_one_bar_in_ten_slots() -> (
    None
):
    db_url = _resolve_test_db_url()
    if not db_url:
        pytest.skip("DATABASE_URL or POSTGRES_* configuration is required")

    engine = create_async_engine(db_url, future=True)
    session_factory = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    repository = RepairCandlesRepository()

    symbol = f"TEST-MISSCNT-{uuid.uuid4().hex[:12]}"
    timeframe = "1m"
    interval_ms = 60_000
    base_ts_ms = int(time.time() // 60 * 60 * 1000)
    window_start = base_ts_ms
    window_end = base_ts_ms + 10 * interval_ms
    fetched_at = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)

    try:
        try:
            async with engine.begin():
                pass
        except (OSError, socket.gaierror, SQLAlchemyError) as exc:
            pytest.skip(f"test database is not reachable: {exc}")

        async with session_factory() as session:
            await session.execute(
                text("DELETE FROM swap_ohlcv_p WHERE symbol = :symbol"),
                {"symbol": symbol},
            )
            await session.commit()

        await repository.selective_upsert_candles(
            symbol=symbol,
            timeframe=timeframe,
            candles=[
                {
                    "timestamp": base_ts_ms + 3 * interval_ms,
                    "open": 100,
                    "high": 110,
                    "low": 95,
                    "close": 105,
                    "volume": 1000,
                    "vol_ccy": 2000,
                    "vol_usd": 3000,
                    "fetched_at": fetched_at,
                },
            ],
        )

        missing_count = await repository.count_missing_timestamps(
            symbol=symbol,
            timeframe=timeframe,
            start_ts_ms=window_start,
            end_ts_ms=window_end,
        )
        assert missing_count == 9

        empty_count = await repository.count_missing_timestamps(
            symbol=symbol,
            timeframe=timeframe,
            start_ts_ms=window_start,
            end_ts_ms=window_start,
        )
        assert empty_count == 0
    finally:
        async with session_factory() as session:
            await session.execute(
                text("DELETE FROM swap_ohlcv_p WHERE symbol = :symbol"),
                {"symbol": symbol},
            )
            await session.commit()
        await engine.dispose()
