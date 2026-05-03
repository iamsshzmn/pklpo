from __future__ import annotations

import pytest

from src.candles.interfaces import swap_sync


class _RepositoryStub:
    async def list_swap_symbols(self) -> list[str]:
        return ["BTC-USDT-SWAP"]

    async def get_instrument_counts(self) -> dict[str, int]:
        return {"all": 1, "swap": 1, "usdt": 1}


@pytest.mark.asyncio
async def test_instrument_catalog_port_loads_curated_symbols_from_repo_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def _load_symbols_from_file(path, *, logger=None) -> list[str]:
        calls.append(str(path))
        if path == swap_sync.resolve_repo_instruments_file():
            return ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
        return []

    monkeypatch.setattr(
        "src.candles.interfaces.swap_sync.load_symbols_from_file",
        _load_symbols_from_file,
    )

    catalog = swap_sync._InstrumentCatalogPort(_RepositoryStub())  # type: ignore[arg-type]

    result = await catalog.load_curated_symbols()

    assert result == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    assert calls == [str(swap_sync.resolve_repo_instruments_file())]


@pytest.mark.asyncio
async def test_instrument_catalog_port_loads_runtime_cache_symbols_only_from_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def _load_symbols_from_file(path, *, logger=None) -> list[str]:
        calls.append(str(path))
        if path == swap_sync.resolve_instruments_cache_file():
            return ["SOL-USDT-SWAP", "DOGE-USDT-SWAP"]
        return []

    monkeypatch.setattr(
        "src.candles.interfaces.swap_sync.load_symbols_from_file",
        _load_symbols_from_file,
    )

    catalog = swap_sync._InstrumentCatalogPort(_RepositoryStub())  # type: ignore[arg-type]

    result = await catalog.load_cached_symbols()

    assert result == ["SOL-USDT-SWAP", "DOGE-USDT-SWAP"]
    assert calls == [str(swap_sync.resolve_instruments_cache_file())]
