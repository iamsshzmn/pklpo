from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.candles.domain.repair import (
    BackfillPlan,
    GuardrailViolation,
    RepairExecutionMode,
    RepairGuardrails,
    RepairPlan,
    RepairStrategy,
    RepairWindow,
    clamp_window_to_closed_bars,
    detect_gap_tasks,
    sanitize_repair_candle,
    validate_repair_candles,
)
from src.candles.domain.repair_timeframes import (
    expected_next_open,
    floor_to_timeframe,
    is_fixed_step_timeframe,
    window_padding,
)


def _ts(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
    return int(datetime(year, month, day, hour, minute, tzinfo=UTC).timestamp() * 1000)


def test_repair_execution_modes_and_strategies_are_explicit() -> None:
    assert RepairExecutionMode.DETECT_ONLY == "detect-only"
    assert RepairExecutionMode.DRY_RUN == "dry-run"
    assert RepairExecutionMode.APPLY == "apply"
    assert RepairStrategy.BACKFILL == "backfill"
    assert RepairStrategy.GAP_REPAIR == "gap-repair"


def test_sanitize_repair_candle_keeps_only_canonical_fields() -> None:
    fetched_at = datetime(2026, 4, 11, 12, 0, tzinfo=UTC)

    payload = sanitize_repair_candle(
        {
            "ts": 123,
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
            "volume": 10.0,
            "volCcy": 11.0,
            "volUsd": 12.0,
            "funding_rate": None,
            "open_interest": None,
        },
        fetched_at=fetched_at,
    )

    assert payload == {
        "timestamp": 123,
        "open": 1.0,
        "high": 2.0,
        "low": 0.5,
        "close": 1.5,
        "volume": 10.0,
        "vol_ccy": 11.0,
        "vol_usd": 12.0,
        "fetched_at": fetched_at,
    }


def test_clamp_window_to_closed_bars_excludes_current_open_bar() -> None:
    window = RepairWindow(
        start_ts_ms=_ts(2026, 4, 11, 10, 0),
        end_ts_ms=_ts(2026, 4, 11, 10, 6),
    )

    clamped = clamp_window_to_closed_bars(
        window=window,
        timeframe="1m",
        now_ts_ms=_ts(2026, 4, 11, 10, 5),
    )

    assert clamped == RepairWindow(
        start_ts_ms=_ts(2026, 4, 11, 10, 0),
        end_ts_ms=_ts(2026, 4, 11, 10, 5),
    )


def test_detect_gap_tasks_groups_consecutive_missing_bars() -> None:
    window = RepairWindow(
        start_ts_ms=_ts(2026, 4, 11, 10, 0),
        end_ts_ms=_ts(2026, 4, 11, 10, 7),
    )

    tasks = detect_gap_tasks(
        timestamps=[
            _ts(2026, 4, 11, 10, 0),
            _ts(2026, 4, 11, 10, 2),
            _ts(2026, 4, 11, 10, 5),
            _ts(2026, 4, 11, 10, 6),
        ],
        timeframe="1m",
        window=window,
    )

    assert [
        (task.start_ts_ms, task.end_ts_ms, task.missing_bars) for task in tasks
    ] == [
        (_ts(2026, 4, 11, 10, 1), _ts(2026, 4, 11, 10, 2), 1),
        (_ts(2026, 4, 11, 10, 3), _ts(2026, 4, 11, 10, 5), 2),
    ]


def test_repair_guardrails_block_apply_before_write() -> None:
    plan = RepairPlan(
        strategy=RepairStrategy.GAP_REPAIR,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        window=RepairWindow(_ts(2026, 4, 1), _ts(2026, 4, 2)),
        tasks=detect_gap_tasks(
            timestamps=[
                _ts(2026, 4, 11, 10, 1),
                _ts(2026, 4, 11, 10, 3),
            ],
            timeframe="1m",
            window=RepairWindow(_ts(2026, 4, 11, 10, 0), _ts(2026, 4, 11, 10, 5)),
        ),
    )
    guardrails = RepairGuardrails(
        max_gap_tasks_per_run=1,
        max_requested_bars_per_run=2,
        max_range_days=1,
        max_fail_ratio=0.2,
    )

    violations = guardrails.check(plan)

    assert violations == [
        GuardrailViolation(
            code="max_gap_tasks_per_run",
            message="planned gap tasks exceed allowed maximum",
        ),
        GuardrailViolation(
            code="max_requested_bars_per_run",
            message="requested bars exceed allowed maximum",
        ),
    ]


@pytest.mark.parametrize(
    ("timeframe", "expected"),
    [("1m", True), ("1W", True), ("1M", False)],
)
def test_is_fixed_step_timeframe(timeframe: str, expected: bool) -> None:
    assert is_fixed_step_timeframe(timeframe) is expected


def test_repair_timeframe_helpers_cover_month_edges() -> None:
    january = _ts(2026, 1, 31, 23, 59)

    assert floor_to_timeframe(january, "1M") == _ts(2026, 1, 1)
    assert expected_next_open(_ts(2026, 1, 1), "1M") == _ts(2026, 2, 1)


def test_window_padding_uses_step_size_for_fixed_frames() -> None:
    assert window_padding("1m", 3) == 180_000


def test_backfill_plan_uses_explicit_domain_type() -> None:
    plan = BackfillPlan(
        strategy=RepairStrategy.BACKFILL,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        window=RepairWindow(_ts(2026, 4, 11, 10, 0), _ts(2026, 4, 11, 10, 3)),
        tasks=detect_gap_tasks(
            timestamps=[],
            timeframe="1m",
            window=RepairWindow(_ts(2026, 4, 11, 10, 0), _ts(2026, 4, 11, 10, 3)),
        ),
    )

    assert isinstance(plan, BackfillPlan)
    assert plan.requested_bars == 3


def test_gap_planning_is_idempotent() -> None:
    window = RepairWindow(_ts(2026, 4, 11, 10, 0), _ts(2026, 4, 11, 10, 6))
    timestamps = [
        _ts(2026, 4, 11, 10, 0),
        _ts(2026, 4, 11, 10, 2),
        _ts(2026, 4, 11, 10, 5),
    ]

    first = detect_gap_tasks(timestamps=timestamps, timeframe="1m", window=window)
    second = detect_gap_tasks(timestamps=timestamps, timeframe="1m", window=window)

    assert first == second


def test_validate_repair_candles_filters_open_bar_and_out_of_window() -> None:
    validated = validate_repair_candles(
        candles=[
            {"ts": _ts(2026, 4, 11, 9, 59)},
            {"ts": _ts(2026, 4, 11, 10, 0)},
            {"ts": _ts(2026, 4, 11, 10, 1)},
            {"ts": _ts(2026, 4, 11, 10, 2)},
        ],
        task_window=RepairWindow(_ts(2026, 4, 11, 10, 0), _ts(2026, 4, 11, 10, 2)),
        closed_until_ts_ms=_ts(2026, 4, 11, 10, 2),
    )

    assert [candle["ts"] for candle in validated] == [
        _ts(2026, 4, 11, 10, 0),
        _ts(2026, 4, 11, 10, 1),
    ]
