from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.candles.ccxt_okx_adapter import CcxtOKXAdapter
from src.candles.infrastructure import adapters as mod


def test_resolve_adapter_name_defaults_to_ccxt() -> None:
    assert mod.resolve_adapter_name({}) == "ccxt"
    assert mod.resolve_adapter_name({"use_ccxt": False}) == "ccxt"


def test_resolve_adapter_name_prefers_explicit_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CANDLES_ADAPTER", "unsupported")
    assert mod.resolve_adapter_name({"adapter": "ccxt"}) == "ccxt"


def test_build_market_data_adapter_rejects_unsupported_adapter() -> None:
    with pytest.raises(RuntimeError, match="Unsupported candles adapter"):
        mod.build_market_data_adapter({"adapter": "legacy"})


def test_build_market_data_adapter_passes_timeout_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, float | int] = {}

    class _AdapterStub:
        def __init__(
            self, *, max_requests_per_second: int, timeout_seconds: float
        ) -> None:
            captured["max_requests_per_second"] = max_requests_per_second
            captured["timeout_seconds"] = timeout_seconds

    monkeypatch.setattr(mod, "CcxtOKXAdapter", _AdapterStub)

    adapter = mod.build_market_data_adapter(
        {"max_requests_per_second": 17, "timeout_seconds": 45}
    )

    assert isinstance(adapter, _AdapterStub)
    assert captured == {"max_requests_per_second": 17, "timeout_seconds": 45}


def test_ccxt_okx_adapter_applies_timeout_seconds_to_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, dict[str, object]] = {}

    class _ExchangeStub:
        def __init__(self) -> None:
            self.markets: dict[str, dict[str, object]] = {}

        async def load_markets(self) -> None:
            return None

        async def close(self) -> None:
            return None

    def _okx(options: dict[str, object]) -> _ExchangeStub:
        captured["options"] = options
        return _ExchangeStub()

    monkeypatch.setattr(
        "src.candles.ccxt_okx_adapter.ccxt",
        SimpleNamespace(okx=_okx),
    )

    adapter = CcxtOKXAdapter(max_requests_per_second=12, timeout_seconds=7.5)

    assert isinstance(adapter, CcxtOKXAdapter)
    assert captured["options"] == {
        "enableRateLimit": True,
        "timeout": 7500,
    }
