from __future__ import annotations

import sys
import types

import pytest


class _FailingAdapter:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def get_candles(self, **kwargs):
        raise RuntimeError("boom")

    async def get_funding_rates(self, symbols):
        return {s: {} for s in symbols}

    async def get_open_interest(self, symbols):
        return {s: {} for s in symbols}


@pytest.mark.asyncio
async def test_sync_symbol_failure_increments_error_once() -> None:
    fake_tqdm = types.ModuleType("tqdm")
    fake_tqdm.tqdm = object()
    sys.modules.setdefault("tqdm", fake_tqdm)

    from src.candles.sync_swap_candles import SwapCandlesSync

    sync = SwapCandlesSync(
        config={"batch_size": 10, "max_retries": 0},
        market_adapter=_FailingAdapter(),  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="boom"):
        await sync.sync_swap_symbol("BTC-USDT-SWAP", ["1m"])

    assert sync.errors_count == 1
