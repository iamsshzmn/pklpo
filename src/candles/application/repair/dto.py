from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.candles.domain.repair import (
        RepairExecutionMode,
        RepairGuardrails,
        RepairPlan,
        RepairStrategy,
    )


@dataclass(frozen=True)
class RepairCommand:
    symbol: str
    timeframe: str
    start_ts_ms: int
    end_ts_ms: int
    mode: RepairExecutionMode
    strategy: RepairStrategy
    guardrails: RepairGuardrails
    now_ts_ms: int
    padding_bars: int = 0


@dataclass(frozen=True)
class RepairResult:
    mode: RepairExecutionMode
    strategy: RepairStrategy
    plan: RepairPlan
    fetch_calls: int
    rows_written: int
    verified: bool
    watermark_updated: bool = False
