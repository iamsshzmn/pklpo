from __future__ import annotations

import sys
import types

import pytest


class _RepoSpy:
    def __init__(self) -> None:
        self.called = False
        self.payload = None

    async def upsert_swap_candles(self, **kwargs):
        self.called = True
        self.payload = kwargs
        return 7

    async def fetch_swap_usdt_symbols(self) -> list[str]:
        return ["BTC-USDT-SWAP"]

    async def fetch_instrument_counts(self) -> dict[str, int]:
        return {"all": 1, "swap": 1, "usdt": 1}

    async def fetch_today_fill_stats(self, start_timestamp_ms: int) -> dict[str, int | float]:
        return {
            "rows_today": 1,
            "funding_rate_non_null": 1,
            "open_interest_non_null": 1,
            "funding_rate_fill_pct": 100.0,
            "open_interest_fill_pct": 100.0,
        }


class _AdapterNoLimiterStub:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def get_candles(self, **kwargs):
        return [
            {"ts": 123, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10},
        ]

    async def get_funding_rates(self, symbols):
        return {s: {} for s in symbols}

    async def get_open_interest(self, symbols):
        return {s: {} for s in symbols}


@pytest.mark.asyncio
async def test_sync_save_uses_repository_abstraction() -> None:
    fake_tqdm = types.ModuleType("tqdm")
    fake_tqdm.tqdm = object()
    sys.modules.setdefault("tqdm", fake_tqdm)
    from src.candles.sync_swap_candles import SwapCandlesSync

    repo = _RepoSpy()
    sync = SwapCandlesSync(config={"batch_size": 10}, repository=repo)  # type: ignore[arg-type]

    candles = [
        {"ts": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10},
    ]
    additional = {"funding_rate": {"fundingRate": 0.001}, "open_interest": {"oi": 123}}

    saved = await sync._save_swap_candles("BTC-USDT-SWAP", "1m", candles, additional)

    assert saved == 7
    assert repo.called is True
    assert repo.payload is not None
    assert repo.payload["symbol"] == "BTC-USDT-SWAP"
    assert repo.payload["timeframe"] == "1m"
    assert len(sync._db_write_latencies_sec) == 1
    assert sync._db_write_batch_sizes == [1]


@pytest.mark.asyncio
async def test_sync_orchestrator_works_with_adapter_stub_without_limiters() -> None:
    fake_tqdm = types.ModuleType("tqdm")
    fake_tqdm.tqdm = object()
    sys.modules.setdefault("tqdm", fake_tqdm)
    from src.candles.sync_swap_candles import SwapCandlesSync

    repo = _RepoSpy()
    sync = SwapCandlesSync(
        config={"batch_size": 10},
        repository=repo,  # type: ignore[arg-type]
        market_adapter=_AdapterNoLimiterStub(),  # type: ignore[arg-type]
    )

    saved, last_ts = await sync.sync_swap_bar("BTC-USDT-SWAP", "1m")

    assert saved == 7
    assert last_ts == "123"
