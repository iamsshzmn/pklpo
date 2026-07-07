from __future__ import annotations

from decimal import Decimal

import pytest


def _facade_row(
    *,
    series_id: str = "TON-USDT-SWAP",
    timestamp: int,
    segment_id: str | None,
    close: str = "1",
    is_gap: bool = False,
):
    from src.identity.application.ohlcv_facade import OhlcvFacadeRow

    return OhlcvFacadeRow(
        series_id=series_id,
        timeframe="1H",
        timestamp=timestamp,
        open=None if is_gap else Decimal(close),
        high=None if is_gap else Decimal(close),
        low=None if is_gap else Decimal(close),
        close=None if is_gap else Decimal(close),
        volume=None if is_gap else Decimal("10"),
        segment_id=segment_id,
        source_venue=None if is_gap else "OKX",
        source_symbol=None if is_gap else "GRAM-USDT-SWAP",
        source_timestamp=None if is_gap else timestamp,
        bar_kind="gap_marker" if is_gap else "native",
        data_status="missing" if is_gap else "complete",
        succession_id=None,
        adjustment_factor=Decimal("1"),
        is_gap=is_gap,
        gap_type="succession" if is_gap else None,
    )


class _StubFacade:
    """Minimal stand-in for OhlcvFacade.read_ohlcv, returning a fixed row
    list regardless of arguments, or raising a fixed exception."""

    def __init__(self, rows=None, raises: Exception | None = None):
        self._rows = rows or []
        self._raises = raises
        self.calls: list[dict] = []

    async def read_ohlcv(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises is not None:
            raise self._raises
        return self._rows


@pytest.mark.asyncio
async def test_fetch_feature_bars_via_facade_maps_rows_and_drops_gap_markers() -> None:
    from src.identity.application.feature_cutover import (
        fetch_feature_bars_via_facade,
    )

    facade = _StubFacade(
        rows=[
            _facade_row(timestamp=1, segment_id="seg-ton", close="10"),
            _facade_row(timestamp=2, segment_id=None, is_gap=True),
            _facade_row(timestamp=3, segment_id="seg-gram", close="20"),
        ]
    )

    bars = await fetch_feature_bars_via_facade(
        facade,
        series_id="TON-USDT-SWAP",
        timeframe="1H",
        start_ts=0,
        end_ts=10,
    )

    assert [b.timestamp for b in bars] == [1, 3]
    assert [b.segment_id for b in bars] == ["seg-ton", "seg-gram"]
    assert bars[0].close == Decimal("10")
    assert bars[1].close == Decimal("20")
    # include_gap_markers must stay False: feature computation wants price
    # bars, gap-awareness comes from segment_id, not synthetic rows.
    assert facade.calls[0]["include_gap_markers"] is False


@pytest.mark.asyncio
async def test_fetch_feature_bars_via_facade_propagates_disabled_error() -> None:
    """Kill-switch fail-closed (§12.11): the facade's
    ContinuousReadDisabledError must propagate unmodified, never be
    swallowed into an empty/partial result."""
    from src.identity.application.ohlcv_facade import ContinuousReadDisabledError
    from src.identity.application.feature_cutover import (
        fetch_feature_bars_via_facade,
    )

    facade = _StubFacade(raises=ContinuousReadDisabledError("disabled"))

    with pytest.raises(ContinuousReadDisabledError):
        await fetch_feature_bars_via_facade(
            facade,
            series_id="TON-USDT-SWAP",
            timeframe="1H",
            start_ts=0,
            end_ts=10,
        )


@pytest.mark.asyncio
async def test_fetch_feature_bars_via_facade_fails_closed_on_missing_segment_id() -> (
    None
):
    """A non-gap row with segment_id=None is a repository contract
    violation, not a value to silently pass through — segment-aware reset
    primitives cannot key on a missing segment."""
    from src.identity.application.feature_cutover import (
        fetch_feature_bars_via_facade,
    )

    facade = _StubFacade(rows=[_facade_row(timestamp=1, segment_id=None, is_gap=False)])

    with pytest.raises(ValueError, match="segment_id"):
        await fetch_feature_bars_via_facade(
            facade,
            series_id="TON-USDT-SWAP",
            timeframe="1H",
            start_ts=0,
            end_ts=10,
        )


def test_segment_aware_primitives_stay_continuous_within_segment_and_reset_at_gap() -> (
    None
):
    """The concrete claim behind Task 5.3's acceptance criteria: indicators
    computed from facade-shaped ton_gram bars are continuous inside a
    segment and reset (warmup / None) exactly at the segment boundary."""
    from src.identity.application.feature_cutover import (
        FeatureBar,
        to_segmented_bars,
    )
    from src.identity.application.feature_reset_policy import (
        returns_no_cross_gap,
        rolling_indicator_with_reset,
    )

    ton_bars = [
        FeatureBar(
            timestamp=i,
            segment_id="seg-ton",
            open=Decimal(10 + i),
            high=Decimal(10 + i),
            low=Decimal(10 + i),
            close=Decimal(10 + i),
            volume=Decimal("1"),
        )
        for i in range(5)
    ]
    gram_bars = [
        FeatureBar(
            timestamp=100 + i,
            segment_id="seg-gram",
            open=Decimal(1 + i),
            high=Decimal(1 + i),
            low=Decimal(1 + i),
            close=Decimal(1 + i),
            volume=Decimal("1"),
        )
        for i in range(5)
    ]
    bars = ton_bars + gram_bars

    segmented = to_segmented_bars(bars)

    # Rolling average, window=3, warmup=2: within seg-ton it behaves like a
    # normal rolling window (continuous); at the first two bars of seg-gram
    # it must be None (re-warming up), not an average blending TON and GRAM
    # closes.
    averages = rolling_indicator_with_reset(
        segmented,
        window=3,
        warmup_bars=2,
        compute=lambda values: sum(values) / len(values),
    )
    assert averages[:2] == [None, None]
    assert averages[2] is not None  # continuous inside seg-ton
    assert averages[5] is None  # re-warmup right after the gap
    assert averages[6] is None
    assert averages[7] is not None  # continuous again inside seg-gram

    # Returns must be None at the first bar of each segment (no cross-gap
    # jump treated as a market move).
    returns = returns_no_cross_gap(segmented)
    assert returns[0] is None
    assert returns[5] is None
    assert returns[1] is not None
    assert returns[6] is not None


def test_compute_affected_recalc_range_basic() -> None:
    from src.identity.application.feature_cutover import (
        compute_affected_recalc_range,
    )

    start, end = compute_affected_recalc_range(
        changed_lower_bounds=[500, 300],
        changed_upper_bounds=[900, 700],
        last_built_ts=None,
    )
    assert (start, end) == (300, 900)


def test_compute_affected_recalc_range_extends_to_last_built_ts() -> None:
    """The materialization watermark must widen the range forward when it is
    later than every changed upper bound, or already-built rows downstream
    of the change would be left stale."""
    from src.identity.application.feature_cutover import (
        compute_affected_recalc_range,
    )

    start, end = compute_affected_recalc_range(
        changed_lower_bounds=[300],
        changed_upper_bounds=[700],
        last_built_ts=5_000,
    )
    assert (start, end) == (300, 5_000)


@pytest.mark.parametrize(
    "lower,upper",
    [([], [700]), ([300], [])],
)
def test_compute_affected_recalc_range_fails_closed_on_empty_bounds(
    lower, upper
) -> None:
    from src.identity.application.feature_cutover import (
        compute_affected_recalc_range,
    )

    with pytest.raises(ValueError):
        compute_affected_recalc_range(
            changed_lower_bounds=lower,
            changed_upper_bounds=upper,
            last_built_ts=None,
        )


def test_compute_affected_recalc_range_fails_closed_on_inverted_range() -> None:
    from src.identity.application.feature_cutover import (
        compute_affected_recalc_range,
    )

    with pytest.raises(ValueError):
        compute_affected_recalc_range(
            changed_lower_bounds=[900],
            changed_upper_bounds=[100],
            last_built_ts=None,
        )
