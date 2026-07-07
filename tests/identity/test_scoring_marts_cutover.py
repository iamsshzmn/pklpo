from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest


def _verdict(*, can_score: bool):
    from src.identity.application.segment_eligibility import SegmentEligibilityVerdict

    return SegmentEligibilityVerdict(
        series_id="TON-USDT-SWAP",
        timeframe="1H",
        segment_id="seg-gram",
        segment_start_ts=1_000,
        warmup_start_ts=1_000,
        actual_bars_since_segment_start=600,
        state="eligible" if can_score else "insufficient_history",
        can_compute_features=True,
        can_score=can_score,
        can_train_ml=can_score,
        reason="segment_warmup_satisfied"
        if can_score
        else "warmup_from_segment_start_not_satisfied",
    )


def test_series_is_ready_for_eval_true_when_score_eligible_and_caught_up() -> None:
    from src.identity.application.scoring_marts_cutover import series_is_ready_for_eval

    assert series_is_ready_for_eval(
        verdict=_verdict(can_score=True), eval_ts=5_000, last_bar_ts=5_000
    )


def test_series_is_ready_for_eval_false_when_not_score_eligible() -> None:
    """Fail-closed: even a perfectly fresh raw candle must not make a series
    'ready' if the segment-eligibility verdict says can_score=False."""
    from src.identity.application.scoring_marts_cutover import series_is_ready_for_eval

    assert not series_is_ready_for_eval(
        verdict=_verdict(can_score=False), eval_ts=5_000, last_bar_ts=9_000
    )


def test_series_is_ready_for_eval_false_when_lagging_behind_shared_eval_ts() -> None:
    from src.identity.application.scoring_marts_cutover import series_is_ready_for_eval

    assert not series_is_ready_for_eval(
        verdict=_verdict(can_score=True), eval_ts=5_000, last_bar_ts=4_000
    )
    assert not series_is_ready_for_eval(
        verdict=_verdict(can_score=True), eval_ts=5_000, last_bar_ts=None
    )


def test_classify_liquidity_gap_approved_when_covered_by_known_gap() -> None:
    from src.identity.application.scoring_marts_cutover import classify_liquidity_gap
    from src.identity.application.shadow_mode_compare import GapWindow

    known_gaps = [
        GapWindow(gap_start_ts=1_000, gap_end_ts=2_000, gap_type="succession")
    ]

    verdict = classify_liquidity_gap(
        prev_bar_ts=1_100, curr_bar_ts=1_900, known_gaps=known_gaps
    )
    assert verdict == "approved_migration_gap"


def test_classify_liquidity_gap_fails_closed_when_unclassified() -> None:
    """An unapproved/unclassified real outage must still count against
    quality — never silently excused just because a gap is 'plausible'."""
    from src.identity.application.scoring_marts_cutover import classify_liquidity_gap

    verdict = classify_liquidity_gap(
        prev_bar_ts=1_100, curr_bar_ts=1_900, known_gaps=[]
    )
    assert verdict == "unclassified_quality_gap"


def _feature_bar(*, timestamp: int, segment_id: str = "seg", close: str = "1"):
    from src.identity.application.feature_cutover import FeatureBar

    return FeatureBar(
        timestamp=timestamp,
        segment_id=segment_id,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=Decimal("10"),
    )


def test_bar_at_returns_matching_bar_and_none_when_missing() -> None:
    from src.identity.application.scoring_marts_cutover import bar_at

    bars = [
        _feature_bar(timestamp=1, close="10"),
        _feature_bar(timestamp=2, close="20"),
    ]

    found = bar_at(bars, 2)
    assert found is not None
    assert found.close == Decimal("20")
    assert bar_at(bars, 999) is None


class _StubExecutionResolverRepository:
    """Fixed 'GRAM after ts=1_900' active-member timeline, canonical alias
    already resolved (no aliasing needed for this test)."""

    async def resolve_alias(self, series_id, as_of):
        return series_id

    async def find_active_member(self, series_id, as_of):
        from src.identity.application.execution_resolver import ActiveMemberRow

        as_of_ms = int(as_of.timestamp() * 1000)
        if as_of_ms < 1_900:
            return ActiveMemberRow(
                source_venue="OKX",
                source_symbol="TON-USDT-SWAP",
                valid_from=0,
                valid_to=1_900,
                instrument_state="delisted",
            )
        return ActiveMemberRow(
            source_venue="OKX",
            source_symbol="GRAM-USDT-SWAP",
            valid_from=1_900,
            valid_to=None,
            instrument_state="live",
        )


@pytest.mark.asyncio
async def test_recommender_uses_series_id_history_and_resolver_for_execution_symbol() -> (
    None
):
    """The matrix row 6 acceptance, verbatim: the recommender must carry
    series_id="TON-USDT-SWAP" as the historical identity throughout, while
    the *current* execution symbol resolved via ExecutionResolver flips to
    GRAM once its member window becomes active — these must never be
    conflated."""
    from src.identity.application.execution_resolver import ExecutionResolver

    resolver = ExecutionResolver(_StubExecutionResolverRepository())

    before = await resolver.resolve_execution_symbol(
        "TON-USDT-SWAP", datetime.fromtimestamp(1.0, tz=UTC)
    )
    after = await resolver.resolve_execution_symbol(
        "TON-USDT-SWAP", datetime.fromtimestamp(2.0, tz=UTC)
    )

    # Historical identity (series_id) never changes...
    assert before.series_id == "TON-USDT-SWAP"
    assert after.series_id == "TON-USDT-SWAP"
    # ...while the resolved execution symbol does.
    assert before.source_symbol == "TON-USDT-SWAP"
    assert after.source_symbol == "GRAM-USDT-SWAP"
    assert after.is_tradeable is True


class _StubFacadeForBacktest:
    def __init__(self, rows=None, raises: Exception | None = None):
        self._rows = rows or []
        self._raises = raises

    async def read_ohlcv(self, **kwargs):
        if self._raises is not None:
            raise self._raises
        return self._rows


@pytest.mark.asyncio
async def test_backtest_series_provider_loads_bars_via_facade() -> None:
    from src.identity.application.ohlcv_facade import OhlcvFacadeRow
    from src.identity.application.scoring_marts_cutover import BacktestSeriesProvider

    row = OhlcvFacadeRow(
        series_id="TON-USDT-SWAP",
        timeframe="1H",
        timestamp=1,
        open=Decimal("1"),
        high=Decimal("1"),
        low=Decimal("1"),
        close=Decimal("1"),
        volume=Decimal("1"),
        segment_id="seg",
        source_venue="OKX",
        source_symbol="TON-USDT-SWAP",
        source_timestamp=1,
        bar_kind="native",
        data_status="complete",
        succession_id=None,
        adjustment_factor=Decimal("1"),
        is_gap=False,
        gap_type=None,
    )
    provider = BacktestSeriesProvider(_StubFacadeForBacktest(rows=[row]))

    bars = await provider.load_bars(
        series_id="TON-USDT-SWAP", timeframe="1H", start_ts=0, end_ts=10
    )
    assert len(bars) == 1
    assert bars[0].timestamp == 1


@pytest.mark.asyncio
async def test_backtest_series_provider_propagates_disabled_error() -> None:
    """Same kill-switch fail-closed guarantee as feature computation
    (Task 5.3): a composite backtest must pause, not silently fall back to
    the legacy `ohlcv` table."""
    from src.identity.application.ohlcv_facade import ContinuousReadDisabledError
    from src.identity.application.scoring_marts_cutover import BacktestSeriesProvider

    provider = BacktestSeriesProvider(
        _StubFacadeForBacktest(raises=ContinuousReadDisabledError("disabled"))
    )

    with pytest.raises(ContinuousReadDisabledError):
        await provider.load_bars(
            series_id="TON-USDT-SWAP", timeframe="1H", start_ts=0, end_ts=10
        )


def test_label_next_bar_direction_continuous_within_segment_and_none_at_boundary() -> (
    None
):
    from src.identity.application.feature_reset_policy import SegmentedBar
    from src.identity.application.scoring_marts_cutover import (
        label_next_bar_direction_no_cross_segment,
    )

    bars = [
        SegmentedBar(segment_id="seg-ton", timestamp=1, value=Decimal("10")),
        SegmentedBar(segment_id="seg-ton", timestamp=2, value=Decimal("12")),
        SegmentedBar(segment_id="seg-ton", timestamp=3, value=Decimal("11")),
        SegmentedBar(segment_id="seg-gram", timestamp=100, value=Decimal("1")),
        SegmentedBar(segment_id="seg-gram", timestamp=101, value=Decimal("2")),
    ]

    labels = label_next_bar_direction_no_cross_segment(bars)

    assert labels[0] == 1  # 10 -> 12, up
    assert labels[1] == 0  # 12 -> 11, down
    # Last bar of seg-ton must be None: the "next" bar is GRAM's first bar,
    # not a same-segment successor.
    assert labels[2] is None
    assert labels[3] == 1  # 1 -> 2, up, within seg-gram
    # Last bar overall has no successor at all.
    assert labels[4] is None
