from __future__ import annotations

import os
from typing import Any

from src.candles.ccxt_okx_adapter import CcxtOKXAdapter


def resolve_adapter_name(config: dict[str, Any] | None = None) -> str:
    cfg = config or {}
    explicit = cfg.get("adapter")
    if isinstance(explicit, str) and explicit:
        return explicit.lower()

    env_value = os.getenv("CANDLES_ADAPTER")
    if env_value:
        return env_value.lower()

    return "ccxt"


def build_market_data_adapter(
    config: dict[str, Any] | None = None,
) -> CcxtOKXAdapter:
    cfg = config or {}
    adapter_name = resolve_adapter_name(cfg)
    if adapter_name != "ccxt":
        raise RuntimeError(
            f"Unsupported candles adapter '{adapter_name}'. The only supported "
            "runtime adapter is 'ccxt'."
        )
    return CcxtOKXAdapter(
        max_requests_per_second=int(cfg.get("max_requests_per_second", 80))
    )
