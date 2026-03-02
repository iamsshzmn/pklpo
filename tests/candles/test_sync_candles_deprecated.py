from __future__ import annotations

import warnings

import pytest


@pytest.mark.asyncio
async def test_fetch_and_sync_candles_delegates_and_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    fake_tqdm = types.ModuleType("tqdm")
    fake_tqdm.tqdm = object()
    sys.modules.setdefault("tqdm", fake_tqdm)

    from src.candles import sync_candles

    captured: dict[str, object] = {}

    async def _fake_sync_swap_candles(*, symbols, timeframes, config):
        captured["symbols"] = symbols
        captured["timeframes"] = timeframes
        captured["config"] = config
        return {"ok": True}

    monkeypatch.setattr(sync_candles, "sync_swap_candles", _fake_sync_swap_candles)

    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always", DeprecationWarning)
        result = await sync_candles.fetch_and_sync_candles(
            symbol="btc-usdt",
            timeframes=["1m", "5m"],
            config={"batch_size": 100},
        )
    assert any(w.category is DeprecationWarning for w in emitted)

    assert result == {"ok": True}
    assert captured["symbols"] == ["BTC-USDT-SWAP"]
    assert captured["timeframes"] == ["1m", "5m"]
    assert captured["config"] == {"batch_size": 100}
