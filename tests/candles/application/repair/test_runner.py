from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.candles.application.repair import runner
from src.candles.application.repair.planning import (
    RepairChunk,
    RepairGap,
    TailFirstRepairPlan,
)
from src.candles.application.repair.runner import run_repair_timeframe
from src.candles.application.repair.summary import RepairSummary
from src.candles.domain.okx_calendar import OKXCandleCalendar
from src.candles.domain.repair import (
    RepairExecutionMode,
    RepairStrategy,
    RepairVerificationMethod,
    RepairWindow,
)

UTC_CAL = OKXCandleCalendar(week_anchor_ts_ms=0)


@dataclass
class _CoverageQueryStub:
    coverage_bounds: tuple[int | None, int | None] = (None, None)

    async def get_coverage_bounds(
        self,
        *,
        symbol: str,
        timeframe: str,
        end_ts_ms: int,
    ) -> tuple[int | None, int | None]:
        del symbol, timeframe, end_ts_ms
        return self.coverage_bounds

    async def list_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[int]:
        del symbol, timeframe, start_ts_ms, end_ts_ms
        return []


def _summary(
    *,
    start_ts_ms: int,
    end_ts_ms: int,
    remaining_gap_tasks: int,
    remaining_requested_bars: int | None = None,
) -> RepairSummary:
    if remaining_requested_bars is None:
        remaining_requested_bars = remaining_gap_tasks
    return RepairSummary(
        mode=RepairExecutionMode.APPLY,
        strategy=RepairStrategy.GAP_REPAIR,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        window=RepairWindow(start_ts_ms=start_ts_ms, end_ts_ms=end_ts_ms),
        gap_tasks=1,
        requested_bars=1,
        remaining_gap_tasks=remaining_gap_tasks,
        remaining_requested_bars=remaining_requested_bars,
        verification_method=RepairVerificationMethod.GAP_DETECTION,
        rows_written=1,
        fetch_calls=1,
        verified=remaining_gap_tasks == 0 and remaining_requested_bars == 0,
        padding_bars=0,
    )


def _plan(
    *gaps: tuple[tuple[int, int], list[tuple[int, int]]],
    closed_until_ts_ms: int = 600_000,
) -> TailFirstRepairPlan:
    normalized_gaps: list[RepairGap] = []
    for (gap_start_ts_ms, gap_end_ts_ms), chunks in gaps:
        normalized_gaps.append(
            RepairGap(
                start_ts_ms=gap_start_ts_ms,
                end_ts_ms=gap_end_ts_ms,
                missing_bars=len(chunks),
                chunks=tuple(
                    RepairChunk(
                        start_ts_ms=chunk_start_ts_ms,
                        end_ts_ms=chunk_end_ts_ms,
                        requested_bars=1,
                    )
                    for chunk_start_ts_ms, chunk_end_ts_ms in chunks
                ),
            )
        )
    return TailFirstRepairPlan(
        start_ts_ms=normalized_gaps[-1].start_ts_ms
        if normalized_gaps
        else closed_until_ts_ms,
        end_ts_ms=closed_until_ts_ms,
        closed_until_ts_ms=closed_until_ts_ms,
        gaps=tuple(normalized_gaps),
    )


@pytest.mark.asyncio
async def test_run_repair_timeframe_executes_newest_chunks_first_with_replanning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coverage_query = _CoverageQueryStub()
    plans = iter(
        [
            _plan(
                ((300_000, 500_000), [(400_000, 500_000), (300_000, 400_000)]),
                ((100_000, 200_000), [(100_000, 200_000)]),
            ),
            _plan(
                ((300_000, 400_000), [(300_000, 400_000)]),
                ((100_000, 200_000), [(100_000, 200_000)]),
            ),
            _plan(
                ((100_000, 200_000), [(100_000, 200_000)]),
            ),
            _plan(),
        ]
    )

    async def _fake_plan_tail_first_repair(**kwargs) -> TailFirstRepairPlan:
        del kwargs
        return next(plans)

    monkeypatch.setattr(runner, "plan_tail_first_repair", _fake_plan_tail_first_repair)

    calls: list[tuple[int, int]] = []

    async def _execute_once(*, start_ts_ms: int, end_ts_ms: int) -> RepairSummary:
        calls.append((start_ts_ms, end_ts_ms))
        return _summary(
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
            remaining_gap_tasks=0,
            remaining_requested_bars=0,
        )

    summary = await run_repair_timeframe(
        validated={
            "symbol": "BTC-USDT-SWAP",
            "repair_strategy": "gap-repair",
            "padding_bars": 0,
        },
        timeframe="1m",
        start_ts_ms=None,
        end_ts_ms=None,
        window_hours=6,
        max_range_days=7,
        now_ts_ms=600_000,
        auto_apply_window=True,
        coverage_query=coverage_query,
        execute_once=_execute_once,
        auto_apply_iteration_limit=10,
        chunk_size_bars=2,
        calendar=UTC_CAL,
    )

    assert calls == [
        (400_000, 500_000),
        (300_000, 400_000),
        (100_000, 200_000),
    ]
    assert summary.window.start_ts_ms == 400_000
    assert summary.window.end_ts_ms == 600_000
    assert summary.auto_apply_incomplete is False


@pytest.mark.asyncio
async def test_run_repair_timeframe_stops_gracefully_on_incomplete_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coverage_query = _CoverageQueryStub()

    async def _fake_plan_tail_first_repair(**kwargs) -> TailFirstRepairPlan:
        del kwargs
        return _plan(
            ((300_000, 500_000), [(400_000, 500_000), (300_000, 400_000)]),
            ((100_000, 200_000), [(100_000, 200_000)]),
        )

    monkeypatch.setattr(runner, "plan_tail_first_repair", _fake_plan_tail_first_repair)

    calls: list[tuple[int, int]] = []

    async def _execute_once(*, start_ts_ms: int, end_ts_ms: int) -> RepairSummary:
        calls.append((start_ts_ms, end_ts_ms))
        return _summary(
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
            remaining_gap_tasks=1,
            remaining_requested_bars=1,
        )

    summary = await run_repair_timeframe(
        validated={
            "symbol": "BTC-USDT-SWAP",
            "repair_strategy": "gap-repair",
            "padding_bars": 0,
        },
        timeframe="1m",
        start_ts_ms=None,
        end_ts_ms=None,
        window_hours=6,
        max_range_days=7,
        now_ts_ms=600_000,
        auto_apply_window=True,
        coverage_query=coverage_query,
        execute_once=_execute_once,
        auto_apply_iteration_limit=10,
        chunk_size_bars=2,
        calendar=UTC_CAL,
    )

    assert calls == [(400_000, 500_000)]
    assert summary.window.start_ts_ms == 400_000
    assert summary.window.end_ts_ms == 600_000
    assert summary.remaining_gap_tasks == 1
    assert summary.auto_apply_incomplete is True


@pytest.mark.asyncio
async def test_run_repair_timeframe_marks_partial_when_chunk_limit_is_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coverage_query = _CoverageQueryStub()
    plans = iter(
        [
            _plan(
                ((300_000, 500_000), [(400_000, 500_000), (300_000, 400_000)]),
            ),
            _plan(
                ((300_000, 400_000), [(300_000, 400_000)]),
                ((100_000, 200_000), [(100_000, 200_000)]),
            ),
        ]
    )

    async def _fake_plan_tail_first_repair(**kwargs) -> TailFirstRepairPlan:
        del kwargs
        return next(plans)

    monkeypatch.setattr(runner, "plan_tail_first_repair", _fake_plan_tail_first_repair)

    calls: list[tuple[int, int]] = []

    async def _execute_once(*, start_ts_ms: int, end_ts_ms: int) -> RepairSummary:
        calls.append((start_ts_ms, end_ts_ms))
        return _summary(
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
            remaining_gap_tasks=0,
            remaining_requested_bars=0,
        )

    summary = await run_repair_timeframe(
        validated={
            "symbol": "BTC-USDT-SWAP",
            "repair_strategy": "gap-repair",
            "padding_bars": 0,
        },
        timeframe="1m",
        start_ts_ms=None,
        end_ts_ms=None,
        window_hours=6,
        max_range_days=7,
        now_ts_ms=600_000,
        auto_apply_window=True,
        coverage_query=coverage_query,
        execute_once=_execute_once,
        auto_apply_iteration_limit=1,
        chunk_size_bars=2,
        calendar=UTC_CAL,
    )

    assert calls == [(400_000, 500_000)]
    assert summary.window.start_ts_ms == 400_000
    assert summary.window.end_ts_ms == 600_000
    assert summary.remaining_gap_tasks == 1
    assert summary.auto_apply_incomplete is True
