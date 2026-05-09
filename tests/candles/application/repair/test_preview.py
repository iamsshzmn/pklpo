from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from src.candles.application.repair.runner import preview_repair_timeframe
from src.candles.domain.okx_calendar import OKXCandleCalendar
from src.candles.domain.repair import (
    RepairExecutionMode,
    RepairGuardrails,
    RepairStrategy,
)

UTC_CAL = OKXCandleCalendar(week_anchor_ts_ms=0)


@dataclass
class _CoverageQueryStub:
    coverage_bounds: tuple[int | None, int | None]
    first_gap_start_ts_ms: int | None
    timestamps: list[int] = field(default_factory=list)

    async def get_coverage_bounds(
        self,
        *,
        symbol: str,
        timeframe: str,
        end_ts_ms: int,
    ) -> tuple[int | None, int | None]:
        del symbol, timeframe, end_ts_ms
        return self.coverage_bounds

    async def find_first_gap_start_ts_ms(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> int | None:
        del symbol, timeframe, start_ts_ms, end_ts_ms
        return self.first_gap_start_ts_ms

    async def list_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[int]:
        del symbol, timeframe
        return [ts for ts in self.timestamps if start_ts_ms <= ts < end_ts_ms]


@dataclass
class _AnchorMetadataStub:
    listing_time_ts_ms: int | None
    metadata_refreshed_at_ms: int | None = 1

    async def get_listing_anchor_metadata(self, *, symbol: str):
        del symbol
        return type(
            "ListingAnchorMetadata",
            (),
            {
                "list_time_ts_ms": self.listing_time_ts_ms,
                "metadata_refreshed_at_ms": self.metadata_refreshed_at_ms,
            },
        )()

    async def get_listing_time_ts_ms(self, *, symbol: str) -> int | None:
        del symbol
        return self.listing_time_ts_ms


def _guardrails(*, max_range_days: int = 7) -> RepairGuardrails:
    return RepairGuardrails(
        max_gap_tasks_per_run=10,
        max_requested_bars_per_run=100,
        max_range_days=max_range_days,
        max_fail_ratio=0.1,
    )


@pytest.mark.asyncio
async def test_preview_repair_timeframe_reports_single_window_plan() -> None:
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(None, None),
        first_gap_start_ts_ms=None,
        timestamps=[0, 120_000],
    )

    preview = await preview_repair_timeframe(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        mode=RepairExecutionMode.APPLY,
        strategy=RepairStrategy.GAP_REPAIR,
        start_ts_ms=0,
        end_ts_ms=180_000,
        window_hours=6,
        max_range_days=7,
        now_ts_ms=300_000,
        auto_apply_window=False,
        coverage_query=coverage_query,
        guardrails=_guardrails(),
        calendar=UTC_CAL,
    )

    assert preview.window.start_ts_ms == 0
    assert preview.window.end_ts_ms == 180_000
    assert preview.gap_tasks == 1
    assert preview.requested_bars == 1
    assert preview.expected_iteration_count == 1
    assert preview.guardrail_risk == "ok"


@pytest.mark.asyncio
async def test_preview_repair_timeframe_estimates_auto_apply_iterations() -> None:
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(None, None),
        first_gap_start_ts_ms=None,
        timestamps=[],
    )
    anchor_metadata = _AnchorMetadataStub(
        listing_time_ts_ms=61_000,
        metadata_refreshed_at_ms=123_000,
    )

    preview = await preview_repair_timeframe(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        mode=RepairExecutionMode.APPLY,
        strategy=RepairStrategy.BACKFILL,
        start_ts_ms=None,
        end_ts_ms=None,
        window_hours=6,
        max_range_days=1,
        now_ts_ms=200_000_000,
        auto_apply_window=True,
        coverage_query=coverage_query,
        guardrails=_guardrails(max_range_days=1),
        anchor_strategy="listing-date",
        anchor_metadata=anchor_metadata,
        calendar=UTC_CAL,
    )

    assert preview.auto_apply_window is True
    assert preview.window.start_ts_ms == 120_000
    assert preview.window.end_ts_ms == 199_980_000
    assert preview.expected_iteration_count == 3
    assert preview.guardrail_risk == "high"
    assert preview.guardrail_violations == (
        "max_requested_bars_per_run",
        "max_range_days",
    )
