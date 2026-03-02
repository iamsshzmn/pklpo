from __future__ import annotations

import sys
import types


class _LegacyAdapterStub:
    pass


def _ensure_tqdm_stub() -> None:
    fake_tqdm = types.ModuleType("tqdm")
    fake_tqdm.tqdm = object()
    sys.modules.setdefault("tqdm", fake_tqdm)


def test_use_legacy_adapter_when_ccxt_disabled(monkeypatch) -> None:
    _ensure_tqdm_stub()
    from src.candles import sync_swap_candles as mod

    monkeypatch.setattr(
        mod,
        "build_market_data_adapter",
        lambda config=None: _LegacyAdapterStub(),
    )
    sync = mod.SwapCandlesSync(config={"use_ccxt": False, "batch_size": 10})
    assert isinstance(sync.okx_client, _LegacyAdapterStub)


def test_fallback_to_legacy_when_ccxt_init_fails(monkeypatch) -> None:
    _ensure_tqdm_stub()
    from src.candles import sync_swap_candles as mod

    calls = {"count": 0}

    def _factory(config=None):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("ccxt init failure")
        return _LegacyAdapterStub()

    monkeypatch.setattr(mod, "build_market_data_adapter", _factory)

    sync = mod.SwapCandlesSync(config={"use_ccxt": True, "batch_size": 10})
    assert isinstance(sync.okx_client, _LegacyAdapterStub)


def test_adapter_selected_from_env(monkeypatch) -> None:
    _ensure_tqdm_stub()
    from src.candles import sync_swap_candles as mod

    monkeypatch.setenv("CANDLES_ADAPTER", "legacy")
    monkeypatch.setattr(
        mod,
        "build_market_data_adapter",
        lambda config=None: _LegacyAdapterStub(),
    )

    sync = mod.SwapCandlesSync(config={"batch_size": 10})
    assert isinstance(sync.okx_client, _LegacyAdapterStub)
