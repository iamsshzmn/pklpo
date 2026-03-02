from __future__ import annotations

import importlib
import os
from typing import Any, Callable

from src.candles.ccxt_okx_adapter import CcxtOKXAdapter
from src.candles.ports import MarketDataAdapterPort


LegacyAdapterFactory = Callable[[], MarketDataAdapterPort]


def _load_factory_from_path(path: str) -> LegacyAdapterFactory:
    module_path, _, attr = path.partition(":")
    if not module_path or not attr:
        raise RuntimeError(
            "Invalid CANDLES_LEGACY_ADAPTER_FACTORY value. "
            "Expected format: 'module.path:factory_name'."
        )
    module = importlib.import_module(module_path)
    factory = getattr(module, attr, None)
    if not callable(factory):
        raise RuntimeError(
            f"Legacy adapter factory '{path}' is not callable or not found."
        )
    return factory


def resolve_adapter_name(config: dict[str, Any] | None = None) -> str:
    cfg = config or {}
    explicit = cfg.get("adapter")
    if isinstance(explicit, str) and explicit:
        return explicit.lower()

    env_value = os.getenv("CANDLES_ADAPTER")
    if env_value:
        return env_value.lower()

    if cfg.get("use_ccxt", True):
        return "ccxt"
    return "legacy"


def build_market_data_adapter(
    config: dict[str, Any] | None = None,
) -> MarketDataAdapterPort:
    cfg = config or {}
    adapter_name = resolve_adapter_name(cfg)
    if adapter_name == "legacy":
        factory = cfg.get("legacy_adapter_factory")
        if callable(factory):
            return factory()

        factory_path = os.getenv("CANDLES_LEGACY_ADAPTER_FACTORY", "")
        if factory_path:
            loaded_factory = _load_factory_from_path(factory_path)
            return loaded_factory()

        raise RuntimeError(
            "Legacy adapter is not registered. Provide `legacy_adapter_factory` in "
            "config or set CANDLES_LEGACY_ADAPTER_FACTORY='module.path:factory_name'."
        )
    return CcxtOKXAdapter(
        max_requests_per_second=int(cfg.get("max_requests_per_second", 80))
    )
