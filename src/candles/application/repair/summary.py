from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.candles.domain.repair import (
    RepairExecutionMode,
    RepairOutcome,
    RepairStrategy,
    RepairVerificationMethod,
    RepairWindow,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .dto import RepairResult


def _coerce_int(value: Any, *, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"repair summary field {field_name!r} must be an integer, got {value!r}"
        ) from exc


def _coerce_float(value: Any, *, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"repair summary field {field_name!r} must be a float, got {value!r}"
        ) from exc


def _coerce_outcome(value: Any) -> RepairOutcome:
    if isinstance(value, RepairOutcome):
        return value
    if value is None:
        return RepairOutcome.SUCCESS
    return RepairOutcome(str(value))


def _coerce_bool(value: Any) -> bool:
    return bool(value)


def _coerce_unique_strs(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _coerce_mode(value: Any) -> RepairExecutionMode:
    if isinstance(value, RepairExecutionMode):
        return value
    return RepairExecutionMode(str(value))


def _coerce_strategy(value: Any) -> RepairStrategy:
    if isinstance(value, RepairStrategy):
        return value
    return RepairStrategy(str(value))


def _coerce_verification_method(
    value: Any,
) -> RepairVerificationMethod | None:
    if value is None:
        return None
    if isinstance(value, RepairVerificationMethod):
        return value
    return RepairVerificationMethod(str(value))


def _assert_same(
    summaries: Sequence[RepairSummary],
    *,
    field_name: str,
) -> None:
    values = {getattr(summary, field_name) for summary in summaries}
    if len(values) <= 1:
        return
    raise ValueError(
        f"repair summary merge requires identical {field_name}, got {sorted(str(value) for value in values)}"
    )


@dataclass(frozen=True)
class RepairSummary:
    """Typed repair run contract used for XCom, CLI and aggregation."""

    mode: RepairExecutionMode
    strategy: RepairStrategy
    symbol: str
    timeframe: str
    window: RepairWindow
    gap_tasks: int
    requested_bars: int
    remaining_gap_tasks: int
    remaining_requested_bars: int
    verification_method: RepairVerificationMethod | None
    rows_written: int
    fetch_calls: int
    verified: bool
    padding_bars: int
    guardrail_violations: tuple[str, ...] = ()
    watermark_updated: bool = False
    auto_apply_incomplete: bool = False
    received_bars: int = 0
    remaining_missing_before: int = 0
    remaining_missing_after: int = 0
    progress: int = 0
    api_fill_ratio: float = 0.0
    write_success_ratio: float = 0.0
    outcome: RepairOutcome = RepairOutcome.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "mode": self.mode.value,
            "strategy": self.strategy.value,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "window": {
                "start_ts_ms": self.window.start_ts_ms,
                "end_ts_ms": self.window.end_ts_ms,
            },
            "gap_tasks": self.gap_tasks,
            "requested_bars": self.requested_bars,
            "remaining_gap_tasks": self.remaining_gap_tasks,
            "remaining_requested_bars": self.remaining_requested_bars,
            "verification_method": (
                self.verification_method.value
                if self.verification_method is not None
                else None
            ),
            "rows_written": self.rows_written,
            "fetch_calls": self.fetch_calls,
            "verified": self.verified,
            "padding_bars": self.padding_bars,
            "guardrail_violations": list(self.guardrail_violations),
            "watermark_updated": self.watermark_updated,
            "received_bars": self.received_bars,
            "remaining_missing_before": self.remaining_missing_before,
            "remaining_missing_after": self.remaining_missing_after,
            "progress": self.progress,
            "api_fill_ratio": self.api_fill_ratio,
            "write_success_ratio": self.write_success_ratio,
            "outcome": self.outcome.value,
        }
        if self.auto_apply_incomplete:
            payload["auto_apply_incomplete"] = True
        return payload

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> RepairSummary:
        window = payload.get("window") or {}
        if not isinstance(window, Mapping):
            raise ValueError("repair summary window must be a mapping")
        remaining_gap_tasks = _coerce_int(
            payload.get("remaining_gap_tasks", 0),
            field_name="remaining_gap_tasks",
        )
        remaining_requested_bars = _coerce_int(
            payload.get("remaining_requested_bars", 0),
            field_name="remaining_requested_bars",
        )
        return cls(
            mode=_coerce_mode(payload.get("mode")),
            strategy=_coerce_strategy(payload.get("strategy")),
            symbol=str(payload.get("symbol", "")),
            timeframe=str(payload.get("timeframe", "")),
            window=RepairWindow(
                start_ts_ms=_coerce_int(
                    window.get("start_ts_ms", 0),
                    field_name="window.start_ts_ms",
                ),
                end_ts_ms=_coerce_int(
                    window.get("end_ts_ms", 0),
                    field_name="window.end_ts_ms",
                ),
            ),
            gap_tasks=_coerce_int(payload.get("gap_tasks", 0), field_name="gap_tasks"),
            requested_bars=_coerce_int(
                payload.get("requested_bars", 0),
                field_name="requested_bars",
            ),
            remaining_gap_tasks=remaining_gap_tasks,
            remaining_requested_bars=remaining_requested_bars,
            verification_method=_coerce_verification_method(
                payload.get("verification_method")
            ),
            rows_written=_coerce_int(payload.get("rows_written", 0), field_name="rows_written"),
            fetch_calls=_coerce_int(payload.get("fetch_calls", 0), field_name="fetch_calls"),
            verified=_coerce_bool(payload.get("verified", False)),
            padding_bars=_coerce_int(
                payload.get("padding_bars", 0),
                field_name="padding_bars",
            ),
            guardrail_violations=_coerce_unique_strs(
                tuple(str(value) for value in (payload.get("guardrail_violations") or []))
            ),
            watermark_updated=_coerce_bool(payload.get("watermark_updated", False)),
            auto_apply_incomplete=(
                _coerce_bool(payload.get("auto_apply_incomplete", False))
                or remaining_gap_tasks > 0
                or remaining_requested_bars > 0
            ),
            received_bars=_coerce_int(
                payload.get("received_bars", 0),
                field_name="received_bars",
            ),
            remaining_missing_before=_coerce_int(
                payload.get("remaining_missing_before", 0),
                field_name="remaining_missing_before",
            ),
            remaining_missing_after=_coerce_int(
                payload.get("remaining_missing_after", 0),
                field_name="remaining_missing_after",
            ),
            progress=_coerce_int(payload.get("progress", 0), field_name="progress"),
            api_fill_ratio=_coerce_float(
                payload.get("api_fill_ratio", 0.0),
                field_name="api_fill_ratio",
            ),
            write_success_ratio=_coerce_float(
                payload.get("write_success_ratio", 0.0),
                field_name="write_success_ratio",
            ),
            outcome=_coerce_outcome(payload.get("outcome")),
        )

    @classmethod
    def from_result(
        cls,
        result: RepairResult,
        *,
        padding_bars: int,
        guardrail_violations: Sequence[str] = (),
    ) -> RepairSummary:
        return cls(
            mode=result.mode,
            strategy=result.strategy,
            symbol=result.plan.symbol,
            timeframe=result.plan.timeframe,
            window=result.plan.window,
            gap_tasks=result.plan.gap_tasks,
            requested_bars=result.plan.requested_bars,
            remaining_gap_tasks=result.remaining_gap_tasks,
            remaining_requested_bars=result.remaining_requested_bars,
            verification_method=result.verification_method,
            rows_written=result.rows_written,
            fetch_calls=result.fetch_calls,
            verified=result.verified,
            padding_bars=padding_bars,
            guardrail_violations=_coerce_unique_strs(tuple(guardrail_violations)),
            watermark_updated=result.watermark_updated,
            auto_apply_incomplete=(
                result.remaining_gap_tasks > 0 or result.remaining_requested_bars > 0
            ),
            received_bars=getattr(result, "received_bars", 0),
            remaining_missing_before=getattr(result, "remaining_missing_before", 0),
            remaining_missing_after=getattr(result, "remaining_missing_after", 0),
            progress=getattr(result, "progress", 0),
            api_fill_ratio=getattr(result, "api_fill_ratio", 0.0),
            write_success_ratio=getattr(result, "write_success_ratio", 0.0),
            outcome=getattr(result, "outcome", RepairOutcome.SUCCESS),
        )


def build_noop_repair_summary(
    *,
    validated: Mapping[str, Any],
    timeframe: str,
    closed_until_ts_ms: int,
) -> RepairSummary:
    return RepairSummary(
        mode=RepairExecutionMode.APPLY,
        strategy=_coerce_strategy(validated.get("repair_strategy")),
        symbol=str(validated.get("symbol", "")),
        timeframe=timeframe,
        window=RepairWindow(
            start_ts_ms=closed_until_ts_ms,
            end_ts_ms=closed_until_ts_ms,
        ),
        gap_tasks=0,
        requested_bars=0,
        remaining_gap_tasks=0,
        remaining_requested_bars=0,
        verification_method=RepairVerificationMethod.GAP_DETECTION,
        rows_written=0,
        fetch_calls=0,
        verified=True,
        padding_bars=_coerce_int(validated.get("padding_bars", 0), field_name="padding_bars"),
        guardrail_violations=(),
        watermark_updated=False,
        auto_apply_incomplete=False,
    )


def merge_repair_summaries(
    *,
    validated: Mapping[str, Any],
    timeframe: str,
    summaries: Sequence[RepairSummary | Mapping[str, Any]],
    closed_until_ts_ms: int,
) -> RepairSummary:
    if not summaries:
        return build_noop_repair_summary(
            validated=validated,
            timeframe=timeframe,
            closed_until_ts_ms=closed_until_ts_ms,
        )

    coerced = [
        summary if isinstance(summary, RepairSummary) else RepairSummary.from_mapping(summary)
        for summary in summaries
    ]
    _assert_same(coerced, field_name="symbol")
    _assert_same(coerced, field_name="mode")
    _assert_same(coerced, field_name="strategy")
    first_summary = coerced[0]
    last_summary = coerced[-1]
    guardrail_violations = _coerce_unique_strs(
        tuple(
            violation
            for summary in coerced
            for violation in summary.guardrail_violations
        )
    )
    total_received = sum(summary.received_bars for summary in coerced)
    total_requested = sum(summary.requested_bars for summary in coerced)
    total_written = sum(summary.rows_written for summary in coerced)
    remaining_missing_before = first_summary.remaining_missing_before
    remaining_missing_after = last_summary.remaining_missing_after
    progress = remaining_missing_before - remaining_missing_after
    return RepairSummary(
        mode=last_summary.mode,
        strategy=last_summary.strategy,
        symbol=last_summary.symbol,
        timeframe=timeframe,
        window=RepairWindow(
            start_ts_ms=_coerce_int(
                first_summary.window.start_ts_ms,
                field_name="summary[0].window.start_ts_ms",
            ),
            end_ts_ms=closed_until_ts_ms,
        ),
        gap_tasks=sum(summary.gap_tasks for summary in coerced),
        requested_bars=total_requested,
        remaining_gap_tasks=last_summary.remaining_gap_tasks,
        remaining_requested_bars=last_summary.remaining_requested_bars,
        verification_method=last_summary.verification_method,
        rows_written=total_written,
        fetch_calls=sum(summary.fetch_calls for summary in coerced),
        verified=last_summary.verified,
        padding_bars=_coerce_int(validated.get("padding_bars", 0), field_name="padding_bars"),
        guardrail_violations=guardrail_violations,
        watermark_updated=any(summary.watermark_updated for summary in coerced),
        auto_apply_incomplete=(
            last_summary.remaining_gap_tasks > 0 or last_summary.remaining_requested_bars > 0
        ),
        received_bars=total_received,
        remaining_missing_before=remaining_missing_before,
        remaining_missing_after=remaining_missing_after,
        progress=progress,
        api_fill_ratio=total_received / max(total_requested, 1),
        write_success_ratio=total_written / max(total_received, 1),
        outcome=last_summary.outcome,
    )
