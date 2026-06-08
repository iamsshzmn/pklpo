from __future__ import annotations

import pytest

from src.candles.infrastructure.extra_data import ExtraDataFetcher


class _AdapterStub:
    def __init__(self) -> None:
        self.funding_calls = 0
        self.oi_calls = 0
        self._funding = {
            "instId": "BTC-USDT-SWAP",
            "fundingTime": "1",
            "fundingRate": 0.01,
        }
        self._oi = {"instId": "BTC-USDT-SWAP", "ts": "2", "oi": 100}

    async def fetch_funding_rates(self, symbols):
        self.funding_calls += 1
        return {symbols[0]: dict(self._funding)}

    async def fetch_open_interest(self, symbols):
        self.oi_calls += 1
        return {symbols[0]: dict(self._oi)}


class _FailingAdapter:
    async def fetch_funding_rates(self, symbols):
        raise RuntimeError("429 Too Many Requests")

    async def fetch_open_interest(self, symbols):
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
