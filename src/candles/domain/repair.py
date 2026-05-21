from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from numbers import Real
from typing import TYPE_CHECKING, Any, Literal

from .repair_timeframes import floor_to_timeframe_business, list_expected_timestamps

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime

    from .okx_calendar import OKXCandleCalendar


class RepairExecutionMode(StrEnum):
    DETECT_ONLY = "detect-only"
    DRY_RUN = "dry-run"
    APPLY = "apply"


class RepairStrategy(StrEnum):
    BACKFILL = "backfill"
    GAP_REPAIR = "gap-repair"


class RepairVerificationMethod(StrEnum):
    NOT_APPLICABLE = "not-applicable"
    PLAN_ONLY = "plan-only"
    GAP_DETECTION = "gap-detection"


class RepairOutcome(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    EMPTY = "empty"
    FAIL = "fail"


def classify_repair_outcome(
    *,
    requested: int,
    received: int,
    exception: bool,
) -> RepairOutcome:
    if exception:
        return RepairOutcome.FAIL
    if requested == 0:
        return RepairOutcome.SUCCESS
    if received == 0:
        return RepairOutcome.EMPTY
    if received < requested:
        return RepairOutcome.PARTIAL
    return RepairOutcome.SUCCESS


def is_blocked_repair_outcome(
    *,
    requested: int,
    received: int,
    exception: bool,
) -> bool:
    return not exception and requested > 0 and received == 0


@dataclass(frozen=True)
class NoProgressPolicy:
    critical_timeframes: frozenset[str] = frozenset({"1H"})
    no_progress_threshold: int = 3

    def is_critical(self, timeframe: str) -> bool:
        return timeframe in self.critical_timeframes


@dataclass(frozen=True)
class RepairWindow:
    start_ts_ms: int
    end_ts_ms: int

    @property
    def is_empty(self) -> bool:
        return self.start_ts_ms >= self.end_ts_ms


@dataclass(frozen=True)
class CoverageReconciliation:
    expected_bars: int
    valid_bars: int
    missing_bars: int
    invalid_extra_rows: int


@dataclass(frozen=True)
class GapTask:
    start_ts_ms: int
    end_ts_ms: int
    missing_bars: int


@dataclass(frozen=True)
class GuardrailViolation:
    code: str
    message: str


@dataclass(frozen=True)
class GapRange:
    start_ts_ms: int
    end_ts_ms: int


@dataclass(frozen=True)
class RepairPlan:
    strategy: RepairStrategy
    symbol: str
    timeframe: str
    window: RepairWindow
    tasks: list[GapTask] = field(default_factory=list)

    @property
    def gap_tasks(self) -> int:
        return len(self.tasks)

    @property
    def requested_bars(self) -> int:
        return sum(task.missing_bars for task in self.tasks)

    @property
    def range_days(self) -> float:
        return (self.window.end_ts_ms - self.window.start_ts_ms) / 86_400_000


@dataclass(frozen=True)
class BackfillPlan(RepairPlan):
    pass


@dataclass(frozen=True)
class LastNClosedBarsPlan:
    symbol: str
    tf: str
    window_start: int
    closed_until: int
    expected_count: int
    missing_ts: list[int]
    corrupted_ts: list[int]
    repair_ranges: list[GapRange]
    status: Literal["ok", "partial", "blocked", "deferred", "not_matured"]


@dataclass(frozen=True)
class RepairVerificationSummary:
    method: RepairVerificationMethod
    remaining_gap_tasks: int
    remaining_requested_bars: int


@dataclass(frozen=True)
class LastNClosedBarsOutcome:
    """Separate from application RepairResult; field overlap is well below 60%."""

    status: Literal["ok", "partial", "blocked", "deferred", "not_matured"]
    unresolved_timestamps: list[int]
    affected_recalc_range: tuple[int, int] | None
    corrupted_count: int
    repaired_count: int
    run_id: str
    algo_version: str
    params_hash: str


@dataclass(frozen=True)
class RepairGuardrails:
    """Preflight limits for a repair plan.

    ``max_fail_ratio`` is **deprecated in 2026-04**. Replaced by
    ``NoProgressPolicy`` + ``RepairOutcome``. The field is retained for
    backward compatibility with existing DAG presets and audit payloads,
    but the use case no longer consults it. Scheduled for removal after
    2026-07.
    """

    max_gap_tasks_per_run: int
    max_requested_bars_per_run: int
    max_range_days: int
    max_fail_ratio: float

    def check(self, plan: RepairPlan) -> list[GuardrailViolation]:
        violations: list[GuardrailViolation] = []
        if plan.gap_tasks > self.max_gap_tasks_per_run:
            violations.append(
                GuardrailViolation(
                    code="max_gap_tasks_per_run",
                    message="planned gap tasks exceed allowed maximum",
                )
            )
        if plan.requested_bars > self.max_requested_bars_per_run:
            violations.append(
                GuardrailViolation(
                    code="max_requested_bars_per_run",
                    message="requested bars exceed allowed maximum",
                )
            )
        if plan.range_days > self.max_range_days:
            violations.append(
                GuardrailViolation(
                    code="max_range_days",
                    message="requested range exceeds allowed maximum",
                )
            )
        return violations


def clamp_window_to_closed_bars(
    *,
    window: RepairWindow,
    timeframe: str,
    now_ts_ms: int,
    calendar: OKXCandleCalendar,
) -> RepairWindow:
    start_ts_ms = calendar.floor_open(window.start_ts_ms, timeframe)
    end_ts_ms = min(
        calendar.floor_open(window.end_ts_ms, timeframe),
        calendar.floor_open(now_ts_ms, timeframe),
    )
    if end_ts_ms < start_ts_ms:
        end_ts_ms = start_ts_ms
    return RepairWindow(start_ts_ms=start_ts_ms, end_ts_ms=end_ts_ms)


def clamp_window_to_closed_bars_business(
    *,
    window: RepairWindow,
    timeframe: str,
    now_ts_ms: int,
    week_anchor_ts_ms: int,
) -> RepairWindow:
    start_ts_ms = floor_to_timeframe_business(
        window.start_ts_ms, timeframe, week_anchor_ts_ms
    )
    end_ts_ms = min(
        floor_to_timeframe_business(window.end_ts_ms, timeframe, week_anchor_ts_ms),
        floor_to_timeframe_business(now_ts_ms, timeframe, week_anchor_ts_ms),
    )
    if end_ts_ms < start_ts_ms:
        end_ts_ms = start_ts_ms
    return RepairWindow(start_ts_ms=start_ts_ms, end_ts_ms=end_ts_ms)


def detect_gap_tasks(
    *,
    timestamps: list[int],
    timeframe: str,
    window: RepairWindow,
    calendar: OKXCandleCalendar,
) -> list[GapTask]:
    if window.is_empty:
        return []

    existing = {ts for ts in timestamps if window.start_ts_ms <= ts < window.end_ts_ms}
    tasks: list[GapTask] = []
    task_start: int | None = None
    missing_bars = 0
    cursor = window.start_ts_ms

    while cursor < window.end_ts_ms:
        if cursor not in existing:
            if task_start is None:
                task_start = cursor
            missing_bars += 1
        elif task_start is not None:
            tasks.append(
                GapTask(
                    start_ts_ms=task_start,
                    end_ts_ms=cursor,
                    missing_bars=missing_bars,
                )
            )
            task_start = None
            missing_bars = 0
        cursor = calendar.next_open(cursor, timeframe)

    if task_start is not None:
        tasks.append(
            GapTask(
                start_ts_ms=task_start,
                end_ts_ms=window.end_ts_ms,
                missing_bars=missing_bars,
            )
        )
    return tasks


def count_expected_bars(
    *, window: RepairWindow, timeframe: str, calendar: OKXCandleCalendar
) -> int:
    if window.is_empty:
        return 0

    count = 0
    cursor = window.start_ts_ms
    while cursor < window.end_ts_ms:
        count += 1
        cursor = calendar.next_open(cursor, timeframe)
    return count


def reconcile_coverage(
    *,
    timestamps: list[int],
    timeframe: str,
    window: RepairWindow,
    calendar: OKXCandleCalendar,
) -> CoverageReconciliation:
    expected_bars = count_expected_bars(
        window=window,
        timeframe=timeframe,
        calendar=calendar,
    )
    expected_opens = set(
        list_expected_timestamps(
            window.start_ts_ms,
            window.end_ts_ms,
            timeframe,
            calendar=calendar,
        )
    )
    stored_in_window = [
        ts for ts in timestamps if window.start_ts_ms <= ts < window.end_ts_ms
    ]
    valid_bars = len(set(stored_in_window) & expected_opens)
    gap_tasks = detect_gap_tasks(
        timestamps=stored_in_window,
        timeframe=timeframe,
        window=window,
        calendar=calendar,
    )
    missing_bars = sum(task.missing_bars for task in gap_tasks)
    invalid_extra_rows = sum(1 for ts in stored_in_window if ts not in expected_opens)
    return CoverageReconciliation(
        expected_bars=expected_bars,
        valid_bars=valid_bars,
        missing_bars=missing_bars,
        invalid_extra_rows=invalid_extra_rows,
    )


def summarize_repair_verification(
    *,
    timestamps: list[int],
    timeframe: str,
    window: RepairWindow,
    calendar: OKXCandleCalendar,
) -> RepairVerificationSummary:
    remaining_gap_tasks = detect_gap_tasks(
        timestamps=timestamps,
        timeframe=timeframe,
        window=window,
        calendar=calendar,
    )
    return RepairVerificationSummary(
        method=RepairVerificationMethod.GAP_DETECTION,
        remaining_gap_tasks=len(remaining_gap_tasks),
        remaining_requested_bars=sum(task.missing_bars for task in remaining_gap_tasks),
    )


def sanitize_repair_candle(
    candle: Mapping[str, Any],
    *,
    fetched_at: datetime,
) -> dict[str, Any]:
    return {
        "timestamp": candle["ts"],
        "open": candle["open"],
        "high": candle["high"],
        "low": candle["low"],
        "close": candle["close"],
        "volume": candle["volume"],
        "vol_ccy": candle.get("volCcy"),
        "vol_usd": candle.get("volUsd"),
        "fetched_at": fetched_at,
    }


def validate_ohlcv_row(row: Mapping[str, Any]) -> bool:
    values = _coerce_ohlcv_values(row)
    if values is None:
        return False
    open_price, high_price, low_price, close_price, volume = values
    if any(value <= 0 for value in (open_price, high_price, low_price, close_price)):
        return False
    if volume < 0:
        return False
    if high_price < low_price:
        return False
    return (
        low_price <= open_price <= high_price and low_price <= close_price <= high_price
    )


def _coerce_ohlcv_values(
    row: object,
) -> tuple[float, float, float, float, float] | None:
    getter = getattr(row, "get", None)
    if not callable(getter):
        return None
    try:
        values = tuple(
            getter(name) for name in ("open", "high", "low", "close", "volume")
        )
    except Exception:
        return None
    if any(not _is_finite_number(value) for value in values):
        return None
    return (
        float(values[0]),
        float(values[1]),
        float(values[2]),
        float(values[3]),
        float(values[4]),
    )


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def merge_gaps(ts_list: list[int], interval_ms: int) -> list[tuple[int, int]]:
    """Merge a list of missing timestamps into half-open (start, end) gap ranges."""
    if not ts_list:
        return []
    sorted_ts = sorted(ts_list)
    ranges: list[tuple[int, int]] = []
    start = sorted_ts[0]
    prev = sorted_ts[0]
    for ts in sorted_ts[1:]:
        if ts > prev + interval_ms:
            ranges.append((start, prev + interval_ms))
            start = ts
        prev = ts
    ranges.append((start, prev + interval_ms))
    return ranges


def validate_repair_candles(
    *,
    candles: Sequence[Mapping[str, Any]],
    task_window: RepairWindow,
    closed_until_ts_ms: int,
) -> list[Mapping[str, Any]]:
    validated: list[Mapping[str, Any]] = []
    for candle in candles:
        timestamp = int(candle["ts"])
        if timestamp < task_window.start_ts_ms or timestamp >= task_window.end_ts_ms:
            continue
        if timestamp >= closed_until_ts_ms:
            continue
        validated.append(candle)
    return validated
