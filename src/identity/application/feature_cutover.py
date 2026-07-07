"""Cutover seam: features -> facade for TON->GRAM only, + recalc (§12.12 п.8-9).

This module is the drop-in replacement for the raw, symbol-keyed OHLCV read
that feature computation uses today (`fetch_ohlcv_df` in
`src.features.infrastructure.db_operations`), scoped to the `ton_gram`
composite series only. It does not touch that production file; it provides
the tested seam a reviewed, minimal integration diff can call.

Why routing through `OhlcvFacade` here is safe by construction: Task 4.5's
shadow-mode comparison already proved raw-vs-facade parity for every trivial
series (290/290 clean) and explained-diff parity for the one composite
series (10/10 clean, all diffs accounted for by gap/segment metadata). This
module does not re-implement that logic; it just adapts `OhlcvFacadeRow` into
the shape feature computation needs (`FeatureBar`, carrying `segment_id`) and
feeds it through Task 5.1's segment-aware primitives so indicators are
provably continuous within a segment and reset at the gap boundary.

Fail-closed by inheritance: if `CONTINUOUS_READ_ENABLED` is off,
`OhlcvFacade.read_ohlcv` raises `ContinuousReadDisabledError` for composite
series (Task 4.2). `fetch_feature_bars_via_facade` does not catch that error
— callers must let it propagate so the `ton_gram` feature job pauses rather
than silently falling back to a partial/wrong raw read (§12.11).

The second half of this module is the §15.5 deterministic invalidation
boundary and a Protocol for enqueueing a precisely-bounded recalc entry
(reusing the existing `ops.indicator_recalc_queue` table; see
`src.identity.infrastructure.recalc_queue_repository.SqlRecalcQueueRepository`
for the SQL adapter) — a narrower, range-bounded alternative to the blanket
`0..MAX_BIGINT` recalc enqueued by the identity build job itself
(`src.identity.infrastructure.repository.INSERT_RECALC_QUEUE_SQL`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from src.identity.application.feature_reset_policy import SegmentedBar

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
    from decimal import Decimal

    from src.identity.application.ohlcv_facade import OhlcvFacade


@dataclass(frozen=True)
class FeatureBar:
    """OHLCV bar shaped for feature computation, carrying the segment_id the
    segment-aware primitives (Task 5.1) key resets on."""

    timestamp: int
    segment_id: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


async def fetch_feature_bars_via_facade(
    facade: OhlcvFacade,
    *,
    series_id: str,
    timeframe: str,
    start_ts: int,
    end_ts: int,
    as_of: datetime | None = None,
) -> list[FeatureBar]:
    """Facade-backed replacement for `fetch_ohlcv_df`, for the `ton_gram`
    composite series. Gap-marker rows are never requested
    (`include_gap_markers=False`) and are defensively dropped if a repository
    implementation returns one anyway — feature computation needs price
    bars, not gap markers; gap awareness comes from `segment_id` changing,
    not from a synthetic row.

    Raises `ContinuousReadDisabledError` unmodified when continuous reads are
    disabled (kill switch, §12.11) — this must propagate, not be swallowed.
    """
    rows = await facade.read_ohlcv(
        series_id=series_id,
        timeframe=timeframe,
        start_ts=start_ts,
        end_ts=end_ts,
        as_of=as_of,
        include_gap_markers=False,
    )
    return [_to_feature_bar(row) for row in rows if not row.is_gap]


def _to_feature_bar(row: object) -> FeatureBar:
    open_ = row.open
    high = row.high
    low = row.low
    close = row.close
    volume = row.volume
    if None in (open_, high, low, close, volume):
        raise ValueError(
            f"facade returned an incomplete non-gap bar at timestamp "
            f"{row.timestamp} for series {row.series_id} "
            f"(is_gap=False but a price/volume field is None)"
        )
    segment_id = row.segment_id
    if segment_id is None:
        raise ValueError(
            f"facade returned a non-gap bar with no segment_id at timestamp "
            f"{row.timestamp} for series {row.series_id} — "
            "segment-aware reset primitives require every bar to carry one"
        )
    return FeatureBar(
        timestamp=row.timestamp,
        segment_id=segment_id,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def to_segmented_bars(
    bars: Sequence[FeatureBar], *, field: str = "close"
) -> list[SegmentedBar]:
    """Adapt `FeatureBar`s into Task 5.1's `SegmentedBar` shape so the
    segment-aware primitives (`rolling_indicator_with_reset`,
    `cumulative_indicator_with_reset`, `returns_no_cross_gap`) can run
    directly on facade output."""
    return [
        SegmentedBar(
            segment_id=bar.segment_id,
            timestamp=bar.timestamp,
            value=getattr(bar, field),
        )
        for bar in bars
    ]


def compute_affected_recalc_range(
    *,
    changed_lower_bounds: Sequence[int],
    changed_upper_bounds: Sequence[int],
    last_built_ts: int | None,
) -> tuple[int, int]:
    """§15.5 deterministic invalidation/recalc boundary:

        affected_range = [
            min(changed valid_from / gap_start_ts / segment_start_ts),
            max(changed valid_to / gap_end_ts / segment_end_ts, last_built_ts),
        ]

    Callers pass every changed lower bound (`valid_from`, `gap_start_ts`,
    `segment_start_ts`) and every changed upper bound (`valid_to`,
    `gap_end_ts`, `segment_end_ts`) contributed by whatever identity metadata
    just changed. `last_built_ts` is the materialization watermark
    (`MAX(timestamp)` in `core.continuous_ohlcv_p` for the series/timeframe,
    the same deterministic-boundary concept Task 4.5's shadow-mode tool uses
    instead of wall-clock `now`) — recalc must always reach at least that far
    forward, or already-built rows downstream of the change would be left
    stale.

    Fails closed: empty bounds means the caller has no actual changed
    boundary to recalc from, which is a caller bug, not "recalc nothing" —
    raises `ValueError` rather than silently returning a no-op range. An
    inverted/empty computed range (start >= end) also raises, rather than
    silently enqueueing a range the `chk_irq_range` DB constraint would
    reject anyway.
    """
    if not changed_lower_bounds:
        raise ValueError("changed_lower_bounds must not be empty")
    if not changed_upper_bounds:
        raise ValueError("changed_upper_bounds must not be empty")

    range_start_ts = min(changed_lower_bounds)
    range_end_ts = max(changed_upper_bounds)
    if last_built_ts is not None:
        range_end_ts = max(range_end_ts, last_built_ts)

    if range_start_ts >= range_end_ts:
        raise ValueError(
            "computed affected range is empty or inverted: "
            f"start_ts={range_start_ts} >= end_ts={range_end_ts}"
        )

    return range_start_ts, range_end_ts


class RecalcQueueRepository(Protocol):
    async def enqueue(
        self,
        *,
        series_id: str,
        timeframe: str,
        range_start_ts: int,
        range_end_ts: int,
        source_dag: str,
        detail: dict[str, object],
    ) -> None:
        """Enqueue a precisely-bounded recalc entry into
        `ops.indicator_recalc_queue`."""
