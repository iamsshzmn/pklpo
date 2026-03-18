from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MetadataRefreshRequest:
    force: bool = False
    extended: bool = False
    provider_id: str = "default"
    provider_options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MetadataRefreshResult:
    refreshed: bool
    instruments_count: int = 0
    provider_id: str = "default"
    reason: str | None = None


@dataclass(frozen=True)
class OrderValidationRequest:
    symbol: str
    price: float
    qty: float
    order_type: str = "limit"
    side: str = "buy"
    account_balance: float | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderValidationResult:
    is_valid: bool
    violations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

