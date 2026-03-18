from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ExecutionMode(StrEnum):
    FAST = "fast"
    SLOW = "slow"
    EXTENDED = "ext"
    BOOTSTRAP = "bootstrap"


@dataclass(frozen=True)
class SyncJobRequest:
    mode: ExecutionMode = ExecutionMode.FAST
    symbols: tuple[str, ...] = ()
    timeframes: tuple[str, ...] = ()
    extra_data: bool = False
    batch_size: int = 300
    max_retries: int = 5
    retry_delay: float = 1.5
    max_concurrent_symbols: int = 1
    provider_id: str = "default"
    provider_options: dict[str, Any] = field(default_factory=dict)
    triggered_at: datetime | None = None


@dataclass(frozen=True)
class SyncJobResult:
    mode: str
    timeframes: tuple[str, ...]
    total_symbols: int
    symbols_count: int
    total_symbols_processed: int
    rows_upserted_total: int
    errors_count: int
    duration_sec: float
    candles_per_second: float
    symbols_per_second: float
    results_by_symbol: dict[str, dict[str, int]] = field(default_factory=dict)
    endpoint_stats: dict[str, Any] = field(default_factory=dict)
    today_fill: dict[str, Any] = field(default_factory=dict)
    db_write: dict[str, Any] = field(default_factory=dict)
    skipped: bool = False
    skip_reason: str | None = None
