from __future__ import annotations

import asyncio
import os
import time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.market_selection.infrastructure.persistence import MarketSelectionPersistence


def _resolve_test_db_url() -> str | None:
    db_url = os.getenv("MARKET_SELECTION_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
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
async def test_fallback_copy_parallel_same_ts_version_is_serialized() -> None:
    db_url = _resolve_test_db_url()
    if not db_url:
        pytest.skip("MARKET_SELECTION_TEST_DATABASE_URL or DATABASE_URL is required")

    engine = create_async_engine(db_url, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    source_ts_version = int(time.time() * 1000)
    new_ts_version = source_ts_version + 1
    symbols = ["RACE-BTC-USDT", "RACE-ETH-USDT", "RACE-SOL-USDT"]

    try:
        async with session_factory() as session:
            await session.execute(
                text(
                    """
                    DELETE FROM market_universe
                    WHERE ts_version IN (:source_ts_version, :new_ts_version)
                    """
                ),
                {
                    "source_ts_version": source_ts_version,
                    "new_ts_version": new_ts_version,
                },
            )
            for idx, symbol in enumerate(symbols, start=1):
                await session.execute(
                    text(
                        """
                        INSERT INTO market_universe (
                            ts_version, symbol, final_score, rank, config_hash
                        ) VALUES (
                            :ts_version, :symbol, :final_score, :rank, :config_hash
                        )
                        """
                    ),
                    {
                        "ts_version": source_ts_version,
                        "symbol": symbol,
                        "final_score": 1.0 - (idx * 0.1),
                        "rank": idx,
                        "config_hash": "race_test_cfg",
                    },
                )
            await session.commit()

        async def _worker(hold_lock: bool) -> tuple[dict[str, int], float]:
            started = time.monotonic()
            async with session_factory() as worker_session:
                persistence = MarketSelectionPersistence(worker_session)
                async with worker_session.begin():
                    await persistence.acquire_write_lock_for_ts_version(
                        ts_version=new_ts_version,
                        lock_timeout_ms=15_000,
                    )
                    metrics = await persistence.copy_previous_universe_with_metrics(
                        new_ts_version=new_ts_version,
                        source_ts_version=source_ts_version,
                        config_hash="race_test_cfg",
                    )
                    if hold_lock:
                        await asyncio.sleep(1.0)
            return metrics, time.monotonic() - started

        first_task = asyncio.create_task(_worker(hold_lock=True))
        await asyncio.sleep(0.1)
        second_task = asyncio.create_task(_worker(hold_lock=False))
        (first_metrics, first_duration), (second_metrics, second_duration) = await asyncio.gather(
            first_task, second_task
        )

        inserted_counts = sorted(
            [first_metrics["inserted_count"], second_metrics["inserted_count"]]
        )
        assert inserted_counts == [0, len(symbols)]
        assert second_duration > 0.8

        async with session_factory() as verify_session:
            result = await verify_session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM market_universe
                    WHERE ts_version = :ts_version
                    """
                ),
                {"ts_version": new_ts_version},
            )
            assert int(result.scalar_one()) == len(symbols)
    finally:
        async with session_factory() as session:
            await session.execute(
                text(
                    """
                    DELETE FROM market_universe
                    WHERE ts_version IN (:source_ts_version, :new_ts_version)
                    """
                ),
                {
                    "source_ts_version": source_ts_version,
                    "new_ts_version": new_ts_version,
                },
            )
            await session.commit()
        await engine.dispose()
