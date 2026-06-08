from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.features.application.freshness_gate import (
    FreshnessGateConfig,
    check_has_work_to_do,
)


def _result(value):
    result = MagicMock()
    result.scalar.return_value = value
    return result


@pytest.mark.asyncio
async def test_manual_run_bypasses_checks() -> None:
    session = AsyncMock()
    has_work = await check_has_work_to_do(
        session,
        ["1m", "5m"],
        is_manual_run=True,
    )
    assert has_work is True
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_missing_ohlcv_requires_work() -> None:
    session = AsyncMock()
    session.execute.return_value = _result(None)

    has_work = await check_has_work_to_do(session, ["1m"])

    assert has_work is True
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_all_fresh_and_synced_skips_work() -> None:
    now = datetime.now(UTC)
    expected_closed = int(((int(now.timestamp()) // 60) * 60 - 60) * 1000)
    ohlcv_recent = expected_closed
    indicators_recent = ohlcv_recent - 60_000

    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(ohlcv_recent),
            _result(indicators_recent),
        ]
    )

    has_work = await check_has_work_to_do(
        session,
        ["1m"],
        config=FreshnessGateConfig(max_lag_fast=240, max_lag_slow=1200),
    )

    assert has_work is False


@pytest.mark.asyncio
async def test_feature_lag_requires_work() -> None:
    now = datetime.now(UTC)
    expected_closed = int(((int(now.timestamp()) // 60) * 60 - 60) * 1000)
    ohlcv_recent = expected_closed
    indicators_stale = ohlcv_recent - int(timedelta(minutes=10).total_seconds() * 1000)

    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(ohlcv_recent),
            _result(indicators_stale),
        ]
    )

    has_work = await check_has_work_to_do(session, ["1m"])

    assert has_work is True
