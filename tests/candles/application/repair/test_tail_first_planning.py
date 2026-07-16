from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from src.candles.application.repair.planning import plan_tail_first_repair
from src.candles.domain.okx_calendar import OKXCandleCalendar

UTC_CAL = OKXCandleCalendar(week_anchor_ts_ms=0)


@dataclass
class _CoverageQueryStub:
    coverage_bounds: tuple[int | None, int | None]
    timestamps: list[int]
    list_calls: list[dict[str, int | str]] = field(default_factory=list)

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
        self.list_calls.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_ts_ms": start_ts_ms,
                "end_ts_ms": end_ts_ms,
            }
        )
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


@pytest.mark.asyncio
async def test_plan_tail_first_repair_returns_newest_gap_first() -> None:
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(0, 480_000),
        timestamps=[0, 60_000, 120_000, 420_000, 480_000],
    )

    plan = await plan_tail_first_repair(
        coverage_query=coverage_query,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        max_range_days=1,
        now_ts_ms=601_000,
        chunk_size_bars=2,
        calendar=UTC_CAL,
    )

    assert coverage_query.list_calls == [
        {
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "start_ts_ms": 0,
            "end_ts_ms": 600_000,
        }
    ]
    assert [(gap.start_ts_ms, gap.end_ts_ms) for gap in plan.gaps] == [
        (540_000, 600_000),
        (180_000, 420_000),
    ]
    assert plan.closed_until_ts_ms == 600_000


@pytest.mark.asyncio
async def test_plan_tail_first_repair_splits_gap_into_descending_chunks() -> None:
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(180_000, 180_000),
        timestamps=[],
    )

    plan = await plan_tail_first_repair(
        coverage_query=coverage_query,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        max_range_days=1,
        now_ts_ms=481_000,
        chunk_size_bars=2,
        anchor_ts_ms=180_000,
        calendar=UTC_CAL,
    )

    assert len(plan.gaps) == 1
    assert [
        (chunk.start_ts_ms, chunk.end_ts_ms, chunk.requested_bars)
        for chunk in plan.gaps[0].chunks
    ] == [
        (360_000, 480_000, 2),
        (240_000, 360_000, 2),
        (180_000, 240_000, 1),
    ]


@pytest.mark.asyncio
async def test_plan_tail_first_repair_never_returns_future_or_unclosed_ranges() -> None:
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(None, None),
        timestamps=[],
    )
    anchor_metadata = _AnchorMetadataStub(
        listing_time_ts_ms=61_000,
        metadata_refreshed_at_ms=123_000,
    )

    plan = await plan_tail_first_repair(
        coverage_query=coverage_query,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        max_range_days=1,
        now_ts_ms=200_030,
        chunk_size_bars=5000,
        anchor_strategy="listing-date",
        anchor_metadata=anchor_metadata,
        calendar=UTC_CAL,
    )

    assert plan.closed_until_ts_ms == 180_000
    assert [(gap.start_ts_ms, gap.end_ts_ms) for gap in plan.gaps] == [
        (120_000, 180_000),
    ]
    assert [(chunk.start_ts_ms, chunk.end_ts_ms) for chunk in plan.gaps[0].chunks] == [
        (120_000, 180_000)
    ]
