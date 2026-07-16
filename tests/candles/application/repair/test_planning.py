from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.candles.application.repair.planning import (
    plan_auto_apply_window,
    resolve_repair_window,
)
from src.candles.domain.okx_calendar import OKXCandleCalendar

UTC_CAL = OKXCandleCalendar(week_anchor_ts_ms=0)


@dataclass
class _CoverageQueryStub:
    coverage_bounds: tuple[int | None, int | None]
    first_gap_start_ts_ms: int | None
    gap_calls: list[dict[str, int | str]] | None = None

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
        if self.gap_calls is not None:
            self.gap_calls.append(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "start_ts_ms": start_ts_ms,
                    "end_ts_ms": end_ts_ms,
                }
            )
        return self.first_gap_start_ts_ms


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


def test_resolve_repair_window_rejects_partial_bounds() -> None:
    with pytest.raises(ValueError, match="requires both start and end"):
        resolve_repair_window(
            start_ts_ms=1,
            end_ts_ms=None,
            window_hours=6,
            now_ts_ms=10,
        )


def test_resolve_repair_window_clamps_explicit_end_to_now() -> None:
    window = resolve_repair_window(
        start_ts_ms=1_000,
        end_ts_ms=20_000,
        window_hours=6,
        now_ts_ms=15_000,
    )

    assert window.start_ts_ms == 1_000
    assert window.end_ts_ms == 15_000


def test_resolve_repair_window_builds_default_hour_window() -> None:
    window = resolve_repair_window(
        start_ts_ms=None,
        end_ts_ms=None,
        window_hours=2,
        now_ts_ms=7_350_000,
    )

    assert window.end_ts_ms == 7_320_000
    assert window.start_ts_ms == 120_000


@pytest.mark.asyncio
async def test_plan_auto_apply_window_rejects_empty_coverage() -> None:
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(None, None),
        first_gap_start_ts_ms=None,
    )

    with pytest.raises(
        ValueError,
        match="requires existing coverage, anchor_ts_ms, or listing-date metadata",
    ):
        await plan_auto_apply_window(
            coverage_query=coverage_query,
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            max_range_days=7,
            now_ts_ms=100_000,
            calendar=UTC_CAL,
        )


@pytest.mark.asyncio
async def test_plan_auto_apply_window_reports_missing_listing_date_metadata() -> None:
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(None, None),
        first_gap_start_ts_ms=None,
    )
    anchor_metadata = _AnchorMetadataStub(
        listing_time_ts_ms=61_000,
        metadata_refreshed_at_ms=None,
    )

    with pytest.raises(
        ValueError,
        match="listing-date anchor metadata lookup returned null freshness timestamp",
    ):
        await plan_auto_apply_window(
            coverage_query=coverage_query,
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            max_range_days=7,
            now_ts_ms=100_000,
            anchor_strategy="listing-date",
            anchor_metadata=anchor_metadata,
            calendar=UTC_CAL,
        )


@pytest.mark.asyncio
async def test_plan_auto_apply_window_uses_explicit_anchor_on_empty_coverage() -> None:
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(None, None),
        first_gap_start_ts_ms=None,
    )

    plan = await plan_auto_apply_window(
        coverage_query=coverage_query,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        max_range_days=1,
        now_ts_ms=200_000_000,
        anchor_ts_ms=61_000,
        calendar=UTC_CAL,
    )

    assert plan.start_ts_ms == 120_000
    assert plan.end_ts_ms == 86_520_000
    assert plan.closed_until_ts_ms == 199_980_000


@pytest.mark.asyncio
async def test_plan_auto_apply_window_uses_listing_date_anchor_on_empty_coverage() -> (
    None
):
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(None, None),
        first_gap_start_ts_ms=None,
    )
    anchor_metadata = _AnchorMetadataStub(
        listing_time_ts_ms=61_000,
        metadata_refreshed_at_ms=123_000,
    )

    plan = await plan_auto_apply_window(
        coverage_query=coverage_query,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        max_range_days=1,
        now_ts_ms=200_000_000,
        anchor_strategy="listing-date",
        anchor_metadata=anchor_metadata,
        calendar=UTC_CAL,
    )

    assert plan.start_ts_ms == 120_000
    assert plan.end_ts_ms == 86_520_000
    assert plan.closed_until_ts_ms == 199_980_000


@pytest.mark.asyncio
async def test_plan_auto_apply_window_existing_coverage_uses_leading_anchor_before_first_candle() -> (
    None
):
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(3_600_000, 7_200_000),
        first_gap_start_ts_ms=None,
    )
    anchor_metadata = _AnchorMetadataStub(
        listing_time_ts_ms=61_000,
        metadata_refreshed_at_ms=123_000,
    )

    plan = await plan_auto_apply_window(
        coverage_query=coverage_query,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        max_range_days=1,
        now_ts_ms=200_000_000,
        anchor_strategy="listing-date",
        anchor_metadata=anchor_metadata,
        calendar=UTC_CAL,
    )

    assert plan.start_ts_ms == 120_000
    assert plan.end_ts_ms == 86_520_000
    assert plan.closed_until_ts_ms == 199_980_000


@pytest.mark.asyncio
async def test_plan_auto_apply_window_existing_coverage_without_leading_gap_keeps_internal_gap_path() -> (
    None
):
    gap_calls: list[dict[str, int | str]] = []
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(120_000, 10_000_000),
        first_gap_start_ts_ms=300_000,
        gap_calls=gap_calls,
    )
    anchor_metadata = _AnchorMetadataStub(
        listing_time_ts_ms=61_000,
        metadata_refreshed_at_ms=123_000,
    )

    plan = await plan_auto_apply_window(
        coverage_query=coverage_query,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        max_range_days=1,
        now_ts_ms=200_000_000,
        anchor_strategy="listing-date",
        anchor_metadata=anchor_metadata,
        calendar=UTC_CAL,
    )

    assert gap_calls == [
        {
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "start_ts_ms": 120_000,
            "end_ts_ms": 199_980_000,
        }
    ]
    assert plan.start_ts_ms == 300_000
    assert plan.end_ts_ms == 86_700_000
    assert plan.closed_until_ts_ms == 199_980_000


@pytest.mark.asyncio
async def test_plan_auto_apply_window_returns_noop_when_existing_coverage_has_no_gaps() -> (
    None
):
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(120_000, 10_000),
        first_gap_start_ts_ms=None,
    )
    anchor_metadata = _AnchorMetadataStub(
        listing_time_ts_ms=61_000,
        metadata_refreshed_at_ms=123_000,
    )

    plan = await plan_auto_apply_window(
        coverage_query=coverage_query,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        max_range_days=7,
        now_ts_ms=123_456,
        anchor_strategy="listing-date",
        anchor_metadata=anchor_metadata,
        calendar=UTC_CAL,
    )

    assert plan.start_ts_ms == 120_000
    assert plan.end_ts_ms == 120_000
    assert plan.closed_until_ts_ms == 120_000


@pytest.mark.asyncio
async def test_plan_auto_apply_window_limits_range_to_max_days() -> None:
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(1_000, 10_000),
        first_gap_start_ts_ms=5_000,
    )

    plan = await plan_auto_apply_window(
        coverage_query=coverage_query,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        max_range_days=1,
        now_ts_ms=200_000_000,
        calendar=UTC_CAL,
    )

    assert plan.start_ts_ms == 5_000
    assert plan.end_ts_ms == 86_405_000
    assert plan.closed_until_ts_ms == 199_980_000


@pytest.mark.asyncio
async def test_plan_auto_apply_window_1m_existing_coverage_uses_leading_anchor_before_first_candle() -> (
    None
):
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(1740787200000, 1743465600000),
        first_gap_start_ts_ms=None,
    )
    anchor_metadata = _AnchorMetadataStub(
        listing_time_ts_ms=1736899200000,
        metadata_refreshed_at_ms=1743552000000,
    )

    plan = await plan_auto_apply_window(
        coverage_query=coverage_query,
        symbol="BTC-USDT-SWAP",
        timeframe="1M",
        max_range_days=90,
        now_ts_ms=1740956400000,
        anchor_strategy="listing-date",
        anchor_metadata=anchor_metadata,
        calendar=UTC_CAL,
    )

    assert plan.start_ts_ms == 1738368000000
    assert plan.end_ts_ms == 1740787200000
    assert plan.closed_until_ts_ms == 1740787200000


@pytest.mark.asyncio
async def test_plan_auto_apply_window_rejects_listing_date_without_freshness_source() -> (
    None
):
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(None, None),
        first_gap_start_ts_ms=None,
    )
    anchor_metadata = _AnchorMetadataStub(
        listing_time_ts_ms=61_000,
        metadata_refreshed_at_ms=None,
    )

    with pytest.raises(
        ValueError,
        match="listing-date anchor metadata lookup returned null freshness timestamp",
    ):
        await plan_auto_apply_window(
            coverage_query=coverage_query,
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            max_range_days=1,
            now_ts_ms=200_000_000,
            anchor_strategy="listing-date",
            anchor_metadata=anchor_metadata,
            calendar=UTC_CAL,
        )


@pytest.mark.asyncio
async def test_plan_auto_apply_window_rejects_listing_date_when_anchor_metadata_is_none() -> (
    None
):
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(None, None),
        first_gap_start_ts_ms=None,
    )

    with pytest.raises(ValueError, match="requires anchor metadata"):
        await plan_auto_apply_window(
            coverage_query=coverage_query,
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            max_range_days=7,
            now_ts_ms=100_000,
            anchor_strategy="listing-date",
            anchor_metadata=None,
            calendar=UTC_CAL,
        )


@pytest.mark.asyncio
async def test_plan_auto_apply_window_rejects_listing_date_when_list_time_is_none() -> (
    None
):
    coverage_query = _CoverageQueryStub(
        coverage_bounds=(None, None),
        first_gap_start_ts_ms=None,
    )
    anchor_metadata = _AnchorMetadataStub(
        listing_time_ts_ms=None,
        metadata_refreshed_at_ms=123_000,
    )

    with pytest.raises(ValueError, match="null listing time"):
        await plan_auto_apply_window(
            coverage_query=coverage_query,
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            max_range_days=7,
            now_ts_ms=100_000,
            anchor_strategy="listing-date",
            anchor_metadata=anchor_metadata,
            calendar=UTC_CAL,
        )
