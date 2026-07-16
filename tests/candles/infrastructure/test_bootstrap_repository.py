"""Integration tests for BootstrapCandlesRepository.

Requires a live DB. Run with:
    pytest tests/candles/infrastructure/test_bootstrap_repository.py -m integration -v
"""

from __future__ import annotations

import pytest

from src.candles.infrastructure.bootstrap_repository import BootstrapCandlesRepository


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upsert_bootstrap_state_creates_row() -> None:
    repo = BootstrapCandlesRepository()
    symbol, timeframe = "TEST-USDT-SWAP", "1H"
    await repo.upsert_bootstrap_state(
        symbol=symbol,
        timeframe=timeframe,
        lookback_days=7,
        target_start_ts=1_000_000,
        target_end_ts=2_000_000,
        expected_bars=168,
        status="running",
    )
    state = await repo.get_bootstrap_state(symbol=symbol, timeframe=timeframe)
    assert state is not None
    assert state.status == "running"
    assert state.expected_bars == 168
    assert state.checkpoint_ts is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upsert_checkpoint_ts_is_caller_controlled() -> None:
    repo = BootstrapCandlesRepository()
    symbol, timeframe = "TEST-USDT-SWAP", "4H"
    await repo.upsert_bootstrap_state(
        symbol=symbol,
        timeframe=timeframe,
        lookback_days=7,
        target_start_ts=1_000_000,
        target_end_ts=2_000_000,
        expected_bars=42,
        status="running",
        checkpoint_ts=1_500_000,
    )
    await repo.upsert_bootstrap_state(
        symbol=symbol,
        timeframe=timeframe,
        lookback_days=7,
        target_start_ts=1_000_000,
        target_end_ts=2_000_000,
        expected_bars=42,
        status="running",
    )
    state = await repo.get_bootstrap_state(symbol=symbol, timeframe=timeframe)
    assert state is not None
    assert state.checkpoint_ts is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_status_raises() -> None:
    repo = BootstrapCandlesRepository()
    with pytest.raises(Exception):
        await repo.upsert_bootstrap_state(
            symbol="TEST-USDT-SWAP",
            timeframe="1H",
            lookback_days=7,
            target_start_ts=1_000_000,
            target_end_ts=2_000_000,
            expected_bars=42,
            status="INVALID_STATUS",
        )
