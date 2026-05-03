from __future__ import annotations

from datetime import UTC, datetime
from itertools import pairwise

import pytest
from hypothesis import given, strategies as st

from src.candles.domain.repair import (
    GapRange,
    LastNClosedBarsOutcome,
    LastNClosedBarsPlan,
    RepairGuardrails,
    RepairPlan,
    RepairStrategy,
    RepairWindow,
    clamp_window_to_closed_bars,
    detect_gap_tasks,
    merge_gaps,
    summarize_repair_verification,
    validate_ohlcv_row,
    validate_repair_candles,
)


def test_detect_gap_tasks_groups_adjacent_missing_bars() -> None:
    window = RepairWindow(start_ts_ms=0, end_ts_ms=6 * 60_000)
    timestamps = [0, 60_000, 4 * 60_000]

    tasks = detect_gap_tasks(timestamps=timestamps, timeframe="1m", window=window)

    assert tasks == [
        type(tasks[0])(start_ts_ms=2 * 60_000, end_ts_ms=4 * 60_000, missing_bars=2),
        type(tasks[1])(start_ts_ms=5 * 60_000, end_ts_ms=6 * 60_000, missing_bars=1),
    ]


@given(existing_indexes=st.sets(st.integers(min_value=0, max_value=31)))
def test_detect_gap_tasks_property_based_for_sorted_non_overlapping_ranges(
    existing_indexes: set[int],
) -> None:
    step = 60_000
    bars = 32
    window = RepairWindow(start_ts_ms=0, end_ts_ms=bars * step)
    timestamps = sorted(index * step for index in existing_indexes)

    tasks = detect_gap_tasks(timestamps=timestamps, timeframe="1m", window=window)

    assert tasks == sorted(tasks, key=lambda task: task.start_ts_ms)
    assert all(window.start_ts_ms <= task.start_ts_ms < task.end_ts_ms <= window.end_ts_ms for task in tasks)
    assert all(left.end_ts_ms <= right.start_ts_ms for left, right in pairwise(tasks))

    missing_indexes: set[int] = set()
    for task in tasks:
        assert (task.end_ts_ms - task.start_ts_ms) // step == task.missing_bars
        task_start_index = task.start_ts_ms // step
        task_end_index = task.end_ts_ms // step
        missing_indexes.update(range(task_start_index, task_end_index))

    assert missing_indexes == set(range(bars)) - existing_indexes


def test_clamp_window_to_closed_bars_excludes_current_open_bar() -> None:
    now_ts_ms = int(datetime(2026, 4, 11, 12, 3, 30, tzinfo=UTC).timestamp() * 1000)
    window = RepairWindow(
        start_ts_ms=int(datetime(2026, 4, 11, 12, 0, 15, tzinfo=UTC).timestamp() * 1000),
        end_ts_ms=int(datetime(2026, 4, 11, 12, 5, 15, tzinfo=UTC).timestamp() * 1000),
    )

    normalized = clamp_window_to_closed_bars(window=window, timeframe="1m", now_ts_ms=now_ts_ms)

    assert normalized == RepairWindow(
        start_ts_ms=int(datetime(2026, 4, 11, 12, 0, tzinfo=UTC).timestamp() * 1000),
        end_ts_ms=int(datetime(2026, 4, 11, 12, 3, tzinfo=UTC).timestamp() * 1000),
    )


def test_validate_repair_candles_keeps_only_closed_rows_inside_task_window() -> None:
    task_window = RepairWindow(start_ts_ms=60_000, end_ts_ms=4 * 60_000)
    candles = [
        {"ts": 0},
        {"ts": 60_000},
        {"ts": 2 * 60_000},
        {"ts": 4 * 60_000},
        {"ts": 5 * 60_000},
    ]

    validated = validate_repair_candles(
        candles=candles,
        task_window=task_window,
        closed_until_ts_ms=3 * 60_000,
    )

    assert validated == [{"ts": 60_000}, {"ts": 2 * 60_000}]


def test_summarize_repair_verification_reports_remaining_gap_tasks() -> None:
    window = RepairWindow(start_ts_ms=0, end_ts_ms=4 * 60_000)
    timestamps = [0, 2 * 60_000]

    verification = summarize_repair_verification(
        timestamps=timestamps,
        timeframe="1m",
        window=window,
    )

    assert verification.remaining_gap_tasks == 2
    assert verification.remaining_requested_bars == 2
    assert verification.method.value == "gap-detection"


def test_merge_gaps_empty_list() -> None:
    assert merge_gaps([], interval_ms=60_000) == []


def test_merge_gaps_single_timestamp() -> None:
    assert merge_gaps([100_000], interval_ms=60_000) == [(100_000, 160_000)]


def test_merge_gaps_adjacent_timestamps_merged_into_one_range() -> None:
    ts = [0, 60_000, 120_000]
    result = merge_gaps(ts, interval_ms=60_000)
    assert result == [(0, 180_000)]


def test_merge_gaps_non_adjacent_timestamps_produce_separate_ranges() -> None:
    ts = [0, 60_000, 300_000, 360_000]
    result = merge_gaps(ts, interval_ms=60_000)
    assert result == [(0, 120_000), (300_000, 420_000)]


def test_merge_gaps_unsorted_input_is_handled() -> None:
    ts = [300_000, 0, 60_000]
    result = merge_gaps(ts, interval_ms=60_000)
    assert result == [(0, 120_000), (300_000, 360_000)]


def test_merge_gaps_all_disjoint() -> None:
    ts = [0, 200_000, 400_000]
    result = merge_gaps(ts, interval_ms=60_000)
    assert result == [(0, 60_000), (200_000, 260_000), (400_000, 460_000)]


def test_guardrails_report_multiple_violations() -> None:
    guardrails = RepairGuardrails(
        max_gap_tasks_per_run=1,
        max_requested_bars_per_run=2,
        max_range_days=0,
        max_fail_ratio=0.5,
    )
    plan = RepairPlan(
        strategy=RepairStrategy.GAP_REPAIR,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        window=RepairWindow(start_ts_ms=0, end_ts_ms=86_400_000),
        tasks=[
            type("GapTaskProxy", (), {"missing_bars": 2})(),
            type("GapTaskProxy", (), {"missing_bars": 2})(),
        ],
    )

    violations = guardrails.check(plan)

    assert [violation.code for violation in violations] == [
        "max_gap_tasks_per_run",
        "max_requested_bars_per_run",
        "max_range_days",
    ]


def test_last_n_closed_bars_plan_is_frozen_and_keeps_domain_shape() -> None:
    plan = LastNClosedBarsPlan(
        symbol="BTC-USDT-SWAP",
        tf="1m",
        window_start=0,
        closed_until=180_000,
        expected_count=3,
        missing_ts=[60_000],
        corrupted_ts=[120_000],
        repair_ranges=[GapRange(start_ts_ms=60_000, end_ts_ms=180_000)],
        status="partial",
    )

    assert plan.symbol == "BTC-USDT-SWAP"
    assert plan.tf == "1m"
    assert plan.expected_count == 3
    assert plan.repair_ranges == [GapRange(start_ts_ms=60_000, end_ts_ms=180_000)]


def test_last_n_closed_bars_outcome_is_separate_from_repair_result_shape() -> None:
    outcome = LastNClosedBarsOutcome(
        status="ok",
        unresolved_timestamps=[60_000],
        affected_recalc_range=(0, 180_000),
        corrupted_count=1,
        repaired_count=2,
        run_id="run-1",
        algo_version="v1",
        params_hash="abc123",
    )

    assert outcome.status == "ok"
    assert outcome.unresolved_timestamps == [60_000]
    assert outcome.affected_recalc_range == (0, 180_000)
    assert outcome.corrupted_count == 1
    assert outcome.repaired_count == 2


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"open": 10, "high": 12, "low": 9, "close": 11, "volume": 5}, True),
        ({"open": None, "high": 12, "low": 9, "close": 11, "volume": 5}, False),
        ({"open": 10, "high": None, "low": 9, "close": 11, "volume": 5}, False),
        ({"open": 10, "high": 12, "low": None, "close": 11, "volume": 5}, False),
        ({"open": 10, "high": 12, "low": 9, "close": None, "volume": 5}, False),
        ({"open": 10, "high": 12, "low": 9, "close": 11, "volume": None}, False),
        ({"open": 0, "high": 12, "low": 9, "close": 11, "volume": 5}, False),
        ({"open": 10, "high": 12, "low": 0, "close": 11, "volume": 5}, False),
        ({"open": 10, "high": 0, "low": 9, "close": 11, "volume": 5}, False),
        ({"open": 10, "high": 12, "low": 9, "close": 0, "volume": 5}, False),
        ({"open": 10, "high": 8, "low": 9, "close": 10, "volume": 5}, False),
        ({"open": 8, "high": 12, "low": 9, "close": 10, "volume": 5}, False),
        ({"open": 13, "high": 12, "low": 9, "close": 10, "volume": 5}, False),
        ({"open": 10, "high": 12, "low": 9, "close": 8, "volume": 5}, False),
        ({"open": 10, "high": 12, "low": 9, "close": 13, "volume": 5}, False),
    ],
)
def test_validate_ohlcv_row_matches_corrupted_detection(
    row: dict[str, int | None],
    expected: bool,
) -> None:
    assert validate_ohlcv_row(row) is expected
