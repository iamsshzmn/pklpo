from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.candles.domain.repair import RepairOutcome

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.candles.domain.repair import (
        RepairExecutionMode,
        RepairGuardrails,
        RepairPlan,
        RepairStrategy,
        RepairVerificationMethod,
        RepairWindow,
    )

    from .summary import RepairSummary


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
    remaining_gap_tasks: int = 0
    remaining_requested_bars: int = 0
    verification_method: RepairVerificationMethod | None = None
    watermark_updated: bool = False
    received_bars: int = 0
    remaining_missing_before: int = 0
    remaining_missing_after: int = 0
    progress: int = 0
    api_fill_ratio: float = 0.0
    write_success_ratio: float = 0.0
    outcome: RepairOutcome = RepairOutcome.SUCCESS

    def to_summary(
        self,
        *,
        padding_bars: int,
        guardrail_violations: Sequence[str] = (),
    ) -> RepairSummary:
        from .summary import RepairSummary

        return RepairSummary.from_result(
            self,
            padding_bars=padding_bars,
            guardrail_violations=guardrail_violations,
        )


@dataclass(frozen=True)
class RepairPreview:
    requested_mode: RepairExecutionMode
    strategy: RepairStrategy
    symbol: str
    timeframe: str
    window: RepairWindow
    auto_apply_window: bool
    gap_tasks: int
    requested_bars: int
    expected_iteration_count: int
    guardrail_risk: str  # "ok" | "medium" | "high"
    guardrail_violations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_mode": self.requested_mode.value,
            "strategy": self.strategy.value,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "window": {
                "start_ts_ms": self.window.start_ts_ms,
                "end_ts_ms": self.window.end_ts_ms,
            },
            "auto_apply_window": self.auto_apply_window,
            "gap_tasks": self.gap_tasks,
            "requested_bars": self.requested_bars,
            "expected_iteration_count": self.expected_iteration_count,
            "guardrail_risk": self.guardrail_risk,
            "guardrail_violations": list(self.guardrail_violations),
        }
