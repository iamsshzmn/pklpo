"""A4 (Roadmap Phase A): double-run idempotency tests for the shared OHLCV write path.

`SwapCandlesRepository.upsert_candles` is the single write path used by both the
ingest DAG (`okx_swap_ohlcv_sync_v2`) and the backfill DAG
(`okx_swap_ohlcv_bootstrap_v1`) to persist rows into `swap_ohlcv_p`.
`RepairCandlesRepository.selective_upsert_candles` (repair DAG,
`okx_swap_repair_v1`) extends the same base class and writes to the same table
with its own ON CONFLICT clause. Running either path twice with identical input
must not create duplicate rows or change the stored values on the second run.

The `signals` DAG has no double-run test here: per `docs/MENTAL_MODEL.md`, the
`signals` bounded context is not wired into the production Airflow loop (code
exists, but nothing schedules it), so there is no deployed DAG to exercise.
"""

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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from src.candles import repository as swap_repository_module
from src.candles.infrastructure import repair_repository as repair_repository_module
from src.candles.infrastructure.repair_repository import RepairCandlesRepository
from src.candles.repository import SwapCandlesRepository

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
                    f"Postgres is unavailable for double-run idempotency tests: {exc}"
                )

            if result.scalar() is None:
                pytest.skip(
                    "swap_ohlcv_p table is unavailable for double-run idempotency tests"
                )

        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
def patch_swap_repository_session(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker,
) -> None:
    @asynccontextmanager
    async def _get_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    # upsert_candles is defined on SwapCandlesRepository, resolved against
    # src.candles.repository's own module globals even when called via the
    # RepairCandlesRepository subclass - patch the base module.
    monkeypatch.setattr(swap_repository_module, "get_db_session", _get_db_session)


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


@pytest.mark.usefixtures("patch_swap_repository_session")
async def test_upsert_candles_double_run_is_idempotent(
    session_factory: async_sessionmaker,
) -> None:
    """Covers the ingest (sync) and backfill (bootstrap) DAG write path."""
    repository = SwapCandlesRepository()
    symbol = f"TEST-DOUBLE-RUN-{uuid4().hex[:8]}"
    timeframe = "1m"
    base_ts = 1_775_001_600_000  # known-aligned 1m boundary, see test_repair_repository_integration.py

    candles = [
        {
            "ts": base_ts,
            "open": 10,
            "high": 11,
            "low": 9,
            "close": 10.5,
            "volume": 100,
            "volCcy": 101,
            "volUsd": 102,
        },
        {
            "ts": base_ts + 60_000,
            "open": 11,
            "high": 12,
            "low": 10,
            "close": 11.5,
            "volume": 200,
            "volCcy": 201,
            "volUsd": 202,
        },
        {
            "ts": base_ts + 120_000,
            "open": 12,
            "high": 13,
            "low": 11,
            "close": 12.5,
            "volume": 300,
            "volCcy": 301,
            "volUsd": 302,
        },
    ]

    try:
        written_first_run = await repository.upsert_candles(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            additional_data={},
        )
        written_second_run = await repository.upsert_candles(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            additional_data={},
        )

        assert written_first_run == 3
        assert written_second_run == 3

        async with session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT timestamp, open, high, low, close, volume
                    FROM swap_ohlcv_p
                    WHERE symbol = :symbol AND timeframe = :timeframe
                    ORDER BY timestamp
                    """
                ),
                {"symbol": symbol, "timeframe": timeframe},
            )
            rows = result.fetchall()

        # No duplicate rows created by the second, identical run.
        assert len(rows) == 3
        assert [int(r.timestamp) for r in rows] == [
            base_ts,
            base_ts + 60_000,
            base_ts + 120_000,
        ]
        assert float(rows[0].open) == 10.0
        assert float(rows[0].high) == 11.0
        assert float(rows[0].close) == 10.5
    finally:
        await _delete_test_rows(session_factory, symbol=symbol, timeframe=timeframe)


@pytest.mark.usefixtures("patch_repair_repository_session")
async def test_selective_upsert_candles_double_run_is_idempotent(
    session_factory: async_sessionmaker,
) -> None:
    """Covers the repair DAG write path (RepairCandlesRepository)."""
    repository = RepairCandlesRepository()
    symbol = f"TEST-DOUBLE-RUN-REPAIR-{uuid4().hex[:8]}"
    timeframe = "1m"
    base_ts = 1_775_001_600_000

    candles = [
        {
            "timestamp": base_ts,
            "open": 20,
            "high": 21,
            "low": 19,
            "close": 20.5,
            "volume": 100,
            "vol_ccy": 101,
            "vol_usd": 102,
            "fetched_at": datetime(2026, 4, 11, tzinfo=UTC),
        },
        {
            "timestamp": base_ts + 60_000,
            "open": 21,
            "high": 22,
            "low": 20,
            "close": 21.5,
            "volume": 200,
            "vol_ccy": 201,
            "vol_usd": 202,
            "fetched_at": datetime(2026, 4, 11, 0, 1, tzinfo=UTC),
        },
    ]

    try:
        written_first_run = await repository.selective_upsert_candles(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
        )
        written_second_run = await repository.selective_upsert_candles(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
        )

        assert written_first_run == 2
        assert written_second_run == 2

        async with session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT timestamp, open, high, low, close, volume
                    FROM swap_ohlcv_p
                    WHERE symbol = :symbol AND timeframe = :timeframe
                    ORDER BY timestamp
                    """
                ),
                {"symbol": symbol, "timeframe": timeframe},
            )
            rows = result.fetchall()

        assert len(rows) == 2
        assert float(rows[0].open) == 20.0
        assert float(rows[1].open) == 21.0
    finally:
        await _delete_test_rows(session_factory, symbol=symbol, timeframe=timeframe)
