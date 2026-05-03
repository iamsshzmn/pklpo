from __future__ import annotations

from src.candles.infrastructure.adapters import resolve_adapter_name


def test_adapter_selected_from_env(monkeypatch) -> None:
    monkeypatch.setenv("CANDLES_ADAPTER", "ccxt")
    assert resolve_adapter_name({}) == "ccxt"


def test_config_adapter_overrides_env(monkeypatch) -> None:
    monkeypatch.setenv("CANDLES_ADAPTER", "unsupported")
    assert resolve_adapter_name({"adapter": "ccxt"}) == "ccxt"
