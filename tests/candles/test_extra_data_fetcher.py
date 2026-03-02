from __future__ import annotations

import sys
import types

import pytest

from src.candles.infrastructure.extra_data import ExtraDataFetcher


class _AdapterStub:
    def __init__(self) -> None:
        self.funding_calls = 0
        self.oi_calls = 0
        self._funding = {"instId": "BTC-USDT-SWAP", "fundingTime": "1", "fundingRate": 0.01}
        self._oi = {"instId": "BTC-USDT-SWAP", "ts": "2", "oi": 100}

    async def get_funding_rates(self, symbols):
        self.funding_calls += 1
        return {symbols[0]: dict(self._funding)}

    async def get_open_interest(self, symbols):
        self.oi_calls += 1
        return {symbols[0]: dict(self._oi)}


class _FailingAdapter:
    async def get_funding_rates(self, symbols):
        raise RuntimeError("429 Too Many Requests")

    async def get_open_interest(self, symbols):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_extra_data_fetcher_cache_returns_stable_payload() -> None:
    adapter = _AdapterStub()
    fetcher = ExtraDataFetcher(adapter)  # type: ignore[arg-type]

    first = await fetcher.fetch_for_symbol("BTC-USDT-SWAP")
    adapter._funding["fundingRate"] = 0.99
    adapter._oi["oi"] = 999
    second = await fetcher.fetch_for_symbol("BTC-USDT-SWAP")

    assert first["funding_rate"]["fundingRate"] == 0.01
    assert second["funding_rate"]["fundingRate"] == 0.01
    assert first["open_interest"]["oi"] == 100
    assert second["open_interest"]["oi"] == 100


@pytest.mark.asyncio
async def test_extra_data_fetcher_stats_record_rate_limit_and_errors() -> None:
    fetcher = ExtraDataFetcher(_FailingAdapter())  # type: ignore[arg-type]

    data = await fetcher.fetch_for_symbol("BTC-USDT-SWAP")
    stats = fetcher.snapshot_stats()

    assert data == {}
    assert stats["funding"]["rate_limit"] == 1
    assert stats["funding"]["retries"] == 1
    assert stats["open_interest"]["errors"] == 1


class _RepoStub:
    async def upsert_swap_candles(self, **kwargs):
        return 1

    async def fetch_swap_usdt_symbols(self):
        return ["BTC-USDT-SWAP"]

    async def fetch_instrument_counts(self):
        return {"all": 1, "swap": 1, "usdt": 1}

    async def fetch_today_fill_stats(self, start_timestamp_ms: int):
        return {}


class _MarketAdapterStub:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def get_candles(self, **kwargs):
        return [{"ts": 1, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]

    async def get_funding_rates(self, symbols):
        return {s: {} for s in symbols}

    async def get_open_interest(self, symbols):
        return {s: {} for s in symbols}


@pytest.mark.asyncio
async def test_sync_does_not_create_or_use_extra_fetcher_when_disabled() -> None:
    fake_tqdm = types.ModuleType("tqdm")
    fake_tqdm.tqdm = object()
    sys.modules.setdefault("tqdm", fake_tqdm)

    from src.candles.sync_swap_candles import SwapCandlesSync

    sync = SwapCandlesSync(
        config={"extra_data": False, "batch_size": 10},
        repository=_RepoStub(),  # type: ignore[arg-type]
        market_adapter=_MarketAdapterStub(),  # type: ignore[arg-type]
    )
    assert sync.extra_data_fetcher is None

    saved, _last_ts = await sync.sync_swap_bar("BTC-USDT-SWAP", "1m")
    assert saved == 1
