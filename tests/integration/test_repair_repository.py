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

_STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000  # 24 hours


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
async def test_repair_repository_upsert_and_query_roundtrip() -> None:
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

    symbol = f"TEST-REPAIR-{uuid.uuid4().hex[:12]}"
    timeframe = "1m"
    base_ts_ms = int(time.time() // 60 * 60 * 1000)
    fetched_at = datetime(2026, 4, 11, 12, 0, tzinfo=UTC)

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

        inserted = await repository.selective_upsert_candles(
            symbol=symbol,
            timeframe=timeframe,
            candles=[
                {
                    "timestamp": base_ts_ms,
                    "open": 100,
                    "high": 110,
                    "low": 95,
                    "close": 105,
                    "volume": 1000,
                    "vol_ccy": 2000,
                    "vol_usd": 3000,
                    "fetched_at": fetched_at,
                },
                {
                    "timestamp": base_ts_ms + 60_000,
                    "open": 105,
                    "high": 111,
                    "low": 101,
                    "close": 108,
                    "volume": 1200,
                    "vol_ccy": 2200,
                    "vol_usd": 3200,
                    "fetched_at": fetched_at,
                },
            ],
        )

        assert inserted == 2
        assert await repository.list_timestamps(
            symbol=symbol,
            timeframe=timeframe,
            start_ts_ms=base_ts_ms,
            end_ts_ms=base_ts_ms + 180_000,
        ) == [base_ts_ms, base_ts_ms + 60_000]
        assert (
            await repository.count_candles(
                symbol=symbol,
                timeframe=timeframe,
                start_ts_ms=base_ts_ms,
                end_ts_ms=base_ts_ms + 180_000,
            )
            == 2
        )

        upserted = await repository.selective_upsert_candles(
            symbol=symbol,
            timeframe=timeframe,
            candles=[
                {
                    "timestamp": base_ts_ms,
                    "open": 101,
                    "high": 112,
                    "low": 96,
                    "close": 109,
                    "volume": 1500,
                    "vol_ccy": 2500,
                    "vol_usd": 3500,
                    "fetched_at": fetched_at,
                    "funding_rate": "should-not-be-written",
                    "open_interest": "should-not-be-written",
                },
                {
                    "timestamp": base_ts_ms + 120_000,
                    "open": 109,
                    "high": 115,
                    "low": 107,
                    "close": 114,
                    "volume": 1800,
                    "vol_ccy": 2800,
                    "vol_usd": 3800,
                    "fetched_at": fetched_at,
                },
            ],
        )

        assert upserted == 2
        assert await repository.list_timestamps(
            symbol=symbol,
            timeframe=timeframe,
            start_ts_ms=base_ts_ms,
            end_ts_ms=base_ts_ms + 240_000,
        ) == [base_ts_ms, base_ts_ms + 60_000, base_ts_ms + 120_000]
        assert (
            await repository.count_candles(
                symbol=symbol,
                timeframe=timeframe,
                start_ts_ms=base_ts_ms,
                end_ts_ms=base_ts_ms + 240_000,
            )
            == 3
        )

        async with session_factory() as session:
            updated_row = (
                await session.execute(
                    text(
                        """
                        SELECT open, high, low, close, volume, vol_ccy, vol_usd,
                               funding_rate, open_interest
                        FROM swap_ohlcv_p
                        WHERE symbol = :symbol
                          AND timeframe = :timeframe
                          AND timestamp = :timestamp
                        """
                    ),
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "timestamp": base_ts_ms,
                    },
                )
            ).one()

        assert float(updated_row.open) == 101.0
        assert float(updated_row.high) == 112.0
        assert float(updated_row.low) == 96.0
        assert float(updated_row.close) == 109.0
        assert float(updated_row.volume) == 1500.0
        assert float(updated_row.vol_ccy) == 2500.0
        assert float(updated_row.vol_usd) == 3500.0
        assert updated_row.funding_rate is None
        assert updated_row.open_interest is None
    finally:
        async with session_factory() as session:
            await session.execute(
                text("DELETE FROM swap_ohlcv_p WHERE symbol = :symbol"),
                {"symbol": symbol},
            )
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_listing_anchor_metadata_returns_none_for_missing_instrument() -> (
    None
):
    db_url = _resolve_test_db_url()
    if not db_url:
        pytest.skip("DATABASE_URL or POSTGRES_* configuration is required")

    engine = create_async_engine(db_url, future=True)
    try:
        try:
            async with engine.begin():
                pass
        except (OSError, socket.gaierror, SQLAlchemyError) as exc:
            pytest.skip(f"test database is not reachable: {exc}")

        repo = RepairCandlesRepository()
        nonexistent_symbol = f"NONEXISTENT-{uuid.uuid4().hex[:8]}"
        result = await repo.get_listing_anchor_metadata(symbol=nonexistent_symbol)
        assert result is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_listing_anchor_metadata_detects_stale_metadata() -> None:
    db_url = _resolve_test_db_url()
    if not db_url:
        pytest.skip("DATABASE_URL or POSTGRES_* configuration is required")

    engine = create_async_engine(db_url, future=True)
    session_factory = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    test_symbol = f"TEST-META-{uuid.uuid4().hex[:8]}"
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    stale_refreshed_at_ms = now_ms - 2 * _STALE_THRESHOLD_MS
    listing_ts_ms = now_ms - 86_400_000 * 365

    try:
        try:
            async with engine.begin():
                pass
        except (OSError, socket.gaierror, SQLAlchemyError) as exc:
            pytest.skip(f"test database is not reachable: {exc}")

        async with session_factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO instruments (
                        symbol,
                        inst_id,
                        list_time,
                        metadata_refreshed_at_ms
                    )
                    VALUES (:symbol, :inst_id, :list_time, :refreshed_at)
                    ON CONFLICT (symbol) DO UPDATE SET
                        inst_id = EXCLUDED.inst_id,
                        list_time = EXCLUDED.list_time,
                        metadata_refreshed_at_ms = EXCLUDED.metadata_refreshed_at_ms
                    """
                ),
                {
                    "symbol": test_symbol,
                    "inst_id": test_symbol,
                    "list_time": listing_ts_ms,
                    "refreshed_at": stale_refreshed_at_ms,
                },
            )
            await session.commit()

        repo = RepairCandlesRepository()
        metadata = await repo.get_listing_anchor_metadata(symbol=test_symbol)

        assert metadata is not None
        assert metadata.list_time_ts_ms == listing_ts_ms
        assert metadata.metadata_refreshed_at_ms == stale_refreshed_at_ms
        age_ms = now_ms - (metadata.metadata_refreshed_at_ms or 0)
        assert (
            age_ms > _STALE_THRESHOLD_MS
        ), "stale metadata should be detectable via age check"
    finally:
        async with session_factory() as session:
            await session.execute(
                text("DELETE FROM instruments WHERE symbol = :symbol"),
                {"symbol": test_symbol},
            )
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_existing_valid_timestamps_excludes_missing_and_corrupted_rows() -> (
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

    symbol = f"TEST-VALID-{uuid.uuid4().hex[:12]}"
    timeframe = "1m"
    base_ts_ms = int(time.time() // 60 * 60 * 1000)
    fetched_at = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)

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
                    "timestamp": base_ts_ms,
                    "open": 100,
                    "high": 110,
                    "low": 95,
                    "close": 105,
                    "volume": 1000,
                    "vol_ccy": 2000,
                    "vol_usd": 3000,
                    "fetched_at": fetched_at,
                },
                {
                    "timestamp": base_ts_ms + 120_000,
                    "open": 100,
                    "high": 90,
                    "low": 95,
                    "close": 105,
                    "volume": 1000,
                    "vol_ccy": 2000,
                    "vol_usd": 3000,
                    "fetched_at": fetched_at,
                },
                {
                    "timestamp": base_ts_ms + 180_000,
                    "open": 106,
                    "high": 112,
                    "low": 104,
                    "close": 109,
                    "volume": 1100,
                    "vol_ccy": 2100,
                    "vol_usd": 3100,
                    "fetched_at": fetched_at,
                },
            ],
        )

        assert await repository.list_existing_valid_timestamps(
            symbol=symbol,
            timeframe=timeframe,
            start_ts_ms=base_ts_ms,
            end_ts_ms=base_ts_ms + 240_000,
        ) == [base_ts_ms, base_ts_ms + 180_000]
    finally:
        async with session_factory() as session:
            await session.execute(
                text("DELETE FROM swap_ohlcv_p WHERE symbol = :symbol"),
                {"symbol": symbol},
            )
            await session.commit()
        await engine.dispose()
