from __future__ import annotations

import pytest

from src.candles.infrastructure import adapters as mod


class _StubAdapter:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None


def test_build_legacy_adapter_from_config_factory() -> None:
    adapter = mod.build_market_data_adapter(
        {
            "adapter": "legacy",
            "legacy_adapter_factory": lambda: _StubAdapter(),
        }
    )
    assert isinstance(adapter, _StubAdapter)


def test_build_legacy_adapter_requires_registration(monkeypatch) -> None:
    monkeypatch.delenv("CANDLES_LEGACY_ADAPTER_FACTORY", raising=False)
    with pytest.raises(RuntimeError, match="Legacy adapter is not registered"):
        mod.build_market_data_adapter({"adapter": "legacy"})
