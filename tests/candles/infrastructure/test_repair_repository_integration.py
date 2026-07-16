from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

try:
    from sqlalchemy.ext.asyncio import async_sessionmaker
except ImportError:  # pragma: no cover
    from typing import Any

    from sqlalchemy.orm import sessionmaker

    class AsyncSessionMaker:
        def __init__(self, bind=None, **kwargs: Any) -> None:
            self._sessionmaker = sessionmaker(bind=bind, class_=AsyncSession, **kwargs)

        def __call__(self, **local_kwargs: Any) -> AsyncSession:
            return self._sessionmaker(**local_kwargs)

    async_sessionmaker = AsyncSessionMaker

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from src.candles.infrastructure import repair_repository as repair_repository_module
from src.candles.infrastructure.repair_repository import RepairCandlesRepository

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


def _build_local_postgres_url() -> str:
    load_dotenv()

    user = os.getenv("POSTGRES_USER", "pklpo_user")
    password = os.getenv("POSTGRES_PASSWORD", "strongpassword")
    database = os.getenv("POSTGRES_DB", "pklpo")
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "5432")

    if host in {"localhost", "pklpo_db"}:
        host = "127.0.0.1"

    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker]:
    engine = create_async_engine(
        _build_local_postgres_url(),
        future=True,
        pool_pre_ping=True,
        connect_args={"ssl": "disable"},
    )
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    try:
        async with factory() as session:
            try:
                result = await session.execute(
                    text("SELECT to_regclass('public.swap_ohlcv_p')")
                )
            except (ConnectionRefusedError, OSError, OperationalError) as exc:
                pytest.skip(
                    f"Postgres is unavailable for repair integration tests: {exc}"
                )

            if result.scalar() is None:
                pytest.skip(
                    "swap_ohlcv_p table is unavailable for repair integration tests"
                )

        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
def patch_repair_repository_session(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker,
) -> None:
    @asynccontextmanager
    async def _get_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    monkeypatch.setattr(repair_repository_module, "get_db_session", _get_db_session)


async def _delete_test_rows(
    session_factory: async_sessionmaker,
    *,
    symbol: str,
    timeframe: str,
) -> None:
    async with session_factory() as session:
        await session.execute(
            text(
                """
                DELETE FROM swap_ohlcv_p
                WHERE symbol = :symbol
                  AND timeframe = :timeframe
                """
            ),
            {"symbol": symbol, "timeframe": timeframe},
        )
        await session.commit()


@pytest.mark.usefixtures("patch_repair_repository_session")
async def test_selective_upsert_preserves_noncanonical_columns_on_conflict(
    session_factory: async_sessionmaker,
) -> None:
    repository = RepairCandlesRepository()
    symbol = f"TEST-REPAIR-{uuid4().hex[:8]}"
    timeframe = "1m"
    timestamp = 1_775_001_600_000

    try:
        async with session_factory() as session:
            await session.execute(
                text(
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
                        funding_rate,
                        open_interest,
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
                        :funding_rate,
                        :open_interest,
                        :fetched_at
                    )
                    """
                ),
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "timestamp": timestamp,
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10.5,
                    "volume": 100,
                    "vol_ccy": 101,
                    "vol_usd": 102,
                    "funding_rate": 0.0125,
                    "open_interest": 456.0,
                    "fetched_at": datetime(2026, 4, 11, tzinfo=UTC),
                },
            )
            await session.commit()

        written = await repository.selective_upsert_candles(
            symbol=symbol,
            timeframe=timeframe,
            candles=[
                {
                    "timestamp": timestamp,
                    "open": 20,
                    "high": 21,
                    "low": 19,
                    "close": 20.5,
                    "volume": 200,
                    "vol_ccy": 201,
                    "vol_usd": 202,
                    "fetched_at": datetime(2026, 4, 11, 0, 1, tzinfo=UTC),
                }
            ],
        )

        assert written == 1

        async with session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        open,
                        high,
                        low,
                        close,
                        volume,
                        vol_ccy,
                        vol_usd,
                        funding_rate,
                        open_interest
                    FROM swap_ohlcv_p
                    WHERE symbol = :symbol
                      AND timeframe = :timeframe
                      AND timestamp = :timestamp
                    """
                ),
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "timestamp": timestamp,
                },
            )
            row = result.one()

        assert float(row.open) == 20.0
        assert float(row.high) == 21.0
        assert float(row.low) == 19.0
        assert float(row.close) == 20.5
        assert float(row.volume) == 200.0
        assert float(row.vol_ccy) == 201.0
        assert float(row.vol_usd) == 202.0
        assert float(row.funding_rate) == 0.0125
        assert float(row.open_interest) == 456.0
    finally:
        await _delete_test_rows(session_factory, symbol=symbol, timeframe=timeframe)


@pytest.mark.usefixtures("patch_repair_repository_session")
async def test_list_timestamps_and_count_candles_use_real_db_window(
    session_factory: async_sessionmaker,
) -> None:
    repository = RepairCandlesRepository()
    symbol = f"TEST-REPAIR-{uuid4().hex[:8]}"
    timeframe = "1m"
    start_ts_ms = 1_775_001_600_000

    try:
        written = await repository.selective_upsert_candles(
            symbol=symbol,
            timeframe=timeframe,
            candles=[
                {
                    "timestamp": start_ts_ms,
                    "open": 1,
                    "high": 2,
                    "low": 0.5,
                    "close": 1.5,
                    "volume": 10,
                    "vol_ccy": 11,
                    "vol_usd": 12,
                    "fetched_at": datetime(2026, 4, 11, tzinfo=UTC),
                },
                {
                    "timestamp": start_ts_ms + 60_000,
                    "open": 2,
                    "high": 3,
                    "low": 1.5,
                    "close": 2.5,
                    "volume": 20,
                    "vol_ccy": 21,
                    "vol_usd": 22,
                    "fetched_at": datetime(2026, 4, 11, 0, 1, tzinfo=UTC),
                },
                {
                    "timestamp": start_ts_ms + 120_000,
                    "open": 3,
                    "high": 4,
                    "low": 2.5,
                    "close": 3.5,
                    "volume": 30,
                    "vol_ccy": 31,
                    "vol_usd": 32,
                    "fetched_at": datetime(2026, 4, 11, 0, 2, tzinfo=UTC),
                },
            ],
        )

        listed = await repository.list_timestamps(
            symbol=symbol,
            timeframe=timeframe,
            start_ts_ms=start_ts_ms,
            end_ts_ms=start_ts_ms + 180_000,
        )
        count = await repository.count_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_ts_ms=start_ts_ms + 60_000,
            end_ts_ms=start_ts_ms + 180_000,
        )

        assert written == 3
        assert listed == [start_ts_ms, start_ts_ms + 60_000, start_ts_ms + 120_000]
        assert count == 2
    finally:
        await _delete_test_rows(session_factory, symbol=symbol, timeframe=timeframe)
