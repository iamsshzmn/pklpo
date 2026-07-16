from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any

import pytest

from src.candles.application.sync.dto import ExecutionMode, SyncJobResult
from src.candles.interfaces import swap_sync as swap_sync_module


@dataclass
class DummyMarketAdapter:
    entered: bool = False

    async def __aenter__(self) -> DummyMarketAdapter:
        self.entered = True
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None


@pytest.mark.asyncio
async def test_sync_swap_candles_builds_expected_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_run_candle_sync(request: Any, **kwargs: Any) -> SyncJobResult:
        captured["request"] = request
        captured["kwargs"] = kwargs
        return SyncJobResult(
            mode=request.mode.value,
            timeframes=request.timeframes,
            total_symbols=1,
            symbols_count=1,
            total_symbols_processed=1,
            rows_upserted_total=3,
            errors_count=0,
            duration_sec=1.0,
            candles_per_second=3.0,
            symbols_per_second=1.0,
            results_by_symbol={"BTC-USDT-SWAP": {"1m": 3}},
            endpoint_stats={},
            today_fill={},
            db_write={},
        )

    monkeypatch.setattr(
        swap_sync_module,
        "build_market_data_adapter",
        lambda config: DummyMarketAdapter(),
    )
    monkeypatch.setattr(swap_sync_module, "run_candle_sync", fake_run_candle_sync)
    monkeypatch.setattr(
        swap_sync_module, "trace_sync_run", lambda **kwargs: nullcontext("cid")
    )

    stats = await swap_sync_module.sync_swap_candles(
        symbols=["BTC-USDT-SWAP"],
        timeframes=["1m"],
        config={"mode": "fast", "batch_size": 123, "max_concurrent_symbols": 2},
    )

    request = captured["request"]
    assert request.mode is ExecutionMode.FAST
    assert request.symbols == ("BTC-USDT-SWAP",)
    assert request.timeframes == ("1m",)
    assert request.batch_size == 123
    assert request.max_concurrent_symbols == 2
    assert stats["total_symbols"] == 1
    assert stats["total_candles_synced"] == 3
