from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.features.infrastructure import db_operations


def _result_with_rows(rows):
    result = MagicMock()
    result.fetchall.return_value = rows
    return result


def test_build_ohlcv_partition_pruning_window_uses_month_floor() -> None:
    from_ts_ms, to_ts_ms = db_operations.build_ohlcv_partition_pruning_window_ms(
        timeframe="1m",
        since_ts=1_706_797_230,
        limit=15_000,
        now_utc=datetime(2026, 3, 18, tzinfo=UTC),
    )

    assert from_ts_ms == int(datetime(2024, 2, 1, tzinfo=UTC).timestamp() * 1000)
    assert to_ts_ms == int(datetime(2026, 4, 1, tzinfo=UTC).timestamp() * 1000)


@pytest.mark.asyncio
async def test_fetch_ohlcv_df_queries_swap_partitions_with_timestamp_bounds() -> None:
    session = AsyncMock()
    session.execute.return_value = _result_with_rows(
        [
            (1_710_000_060_000, 11, 12, 10, 11.5, 101),
            (1_710_000_120_000, 12, 13, 11, 12.5, 102),
        ]
    )

    df = await db_operations.fetch_ohlcv_df(
        session,
        "BTC-USDT-SWAP",
        "1m",
        since_ts=1_709_999_000,
        limit=200,
    )

    assert df is not None
    assert list(df["ts"]) == [1_710_000_120, 1_710_000_060]
    query_text = str(session.execute.await_args.args[0])
    params = session.execute.await_args.args[1]
    assert "FROM swap_ohlcv_p" in query_text
    assert "timestamp > :since_ts_ms" in query_text
    assert "timestamp >= :from_ts_ms" in query_text
    assert params["since_ts_ms"] == 1_709_999_000_000


@pytest.mark.asyncio
async def test_ensure_columns_exist_delegates_to_schema_ddl_port() -> None:
    session = AsyncMock()
    port = AsyncMock()

    await db_operations.ensure_columns_exist(
        session,
        "indicators",
        ["ema_8", "ema_21"],
        schema_ddl_port=port,
    )

    port.ensure_columns.assert_awaited_once_with(
        session,
        "indicators",
        ["ema_8", "ema_21"],
    )


@pytest.mark.asyncio
async def test_ensure_columns_exist_uses_default_schema_ddl_port(monkeypatch) -> None:
    session = AsyncMock()
    port = AsyncMock()
    monkeypatch.setattr(db_operations, "_DEFAULT_SCHEMA_DDL_PORT", port)

    await db_operations.ensure_columns_exist(
        session,
        "indicators",
        ["ema_8"],
    )

    port.ensure_columns.assert_awaited_once_with(session, "indicators", ["ema_8"])
