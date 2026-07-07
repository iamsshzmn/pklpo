"""Segment-aware feature eligibility (§13.8, §14.10).

`ops.feature_eligibility` (candle-level, per `symbol`) already exists in the
candles bounded context. This module adds the identity-layer dimension that
sits on top of it for composite series: eligibility keyed by
`(series_id, timeframe, segment_id)`, where warmup is counted from
`segment_start_ts` — the start of the *current* segment (e.g. GRAM's start
after the TON->GRAM gap) — never from the composite series' full pre-gap
history.

Without this, `ton_gram` would look "eligible" the instant GRAM data starts
flowing, because the composite series as a whole has thousands of bars of
(mostly TON) history. That is exactly the cross-gap leakage this task exists
to prevent (§13.7/§13.8): right after a gap the correct state is
`data_status=warmup` at the bar level and `eligibility_status
=insufficient_history` at the series level, until the segment itself has
accumulated enough bars.

`is_partial_event_bucket` (§13.9) is a second, independent fail-closed gate:
a bucket whose interval crosses the migration/event boundary is not proof the
market traded the whole bucket, so it can never be scoreable or trainable —
even if the segment would otherwise have plenty of bars.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EligibilityState = Literal[
    "eligible",
    "insufficient_history",
    "incomplete_history",
    "invalid_history",
    "informational_only",
    "disabled",
]

TimeframeRole = Literal["full", "context", "informational", "inactive"]


@dataclass(frozen=True)
class SegmentTimeframePolicy:
    role: TimeframeRole
    warmup_bars_required: int


# Working baseline from §13.8; FULL timeframes can score once warmup is
# satisfied, CONTEXT timeframes compute features but never score/train.
DEFAULT_SEGMENT_TIMEFRAME_POLICIES: dict[str, SegmentTimeframePolicy] = {
    "1H": SegmentTimeframePolicy("full", 500),
    "4H": SegmentTimeframePolicy("full", 500),
    "1D": SegmentTimeframePolicy("full", 500),
    "1W": SegmentTimeframePolicy("context", 280),
}


@dataclass(frozen=True)
class SegmentEligibilityFacts:
    series_id: str
    timeframe: str
    segment_id: str
    segment_start_ts: int
    actual_bars_since_segment_start: int
    is_partial_event_bucket: bool = False


@dataclass(frozen=True)
class SegmentEligibilityVerdict:
    series_id: str
    timeframe: str
    segment_id: str
    segment_start_ts: int
    warmup_start_ts: int
    actual_bars_since_segment_start: int
    state: EligibilityState
    can_compute_features: bool
    can_score: bool
    can_train_ml: bool
    reason: str


def evaluate_segment_eligibility(
    facts: SegmentEligibilityFacts,
    *,
    policies: dict[str, SegmentTimeframePolicy] | None = None,
) -> SegmentEligibilityVerdict:
    policy = (policies or DEFAULT_SEGMENT_TIMEFRAME_POLICIES).get(
        facts.timeframe, SegmentTimeframePolicy("inactive", 0)
    )

    if policy.role == "inactive":
        return _verdict(
            facts,
            state="disabled",
            can_compute_features=False,
            can_score=False,
            can_train_ml=False,
            reason="timeframe_not_registered_for_segment_eligibility",
        )

    if facts.is_partial_event_bucket:
        # §13.9: the bucket interval crosses the migration/event boundary —
        # never scoreable or trainable, regardless of bar count.
        return _verdict(
            facts,
            state="incomplete_history",
            can_compute_features=True,
            can_score=False,
            can_train_ml=False,
            reason="partial_event_bucket_not_trainable",
        )

    if facts.actual_bars_since_segment_start < policy.warmup_bars_required:
        # §13.8: warmup counted from segment_start_ts, never from a prior
        # segment's (different source_symbol's) history.
        return _verdict(
            facts,
            state="insufficient_history",
            can_compute_features=True,
            can_score=False,
            can_train_ml=False,
            reason="warmup_from_segment_start_not_satisfied",
        )

    if policy.role == "context":
        return _verdict(
            facts,
            state="eligible",
            can_compute_features=True,
            can_score=False,
            can_train_ml=False,
            reason="context_only_timeframe",
        )

    return _verdict(
        facts,
        state="eligible",
        can_compute_features=True,
        can_score=True,
        can_train_ml=True,
        reason="segment_warmup_satisfied",
    )


def _verdict(
    facts: SegmentEligibilityFacts,
    *,
    state: EligibilityState,
    can_compute_features: bool,
    can_score: bool,
    can_train_ml: bool,
    reason: str,
) -> SegmentEligibilityVerdict:
    return SegmentEligibilityVerdict(
        series_id=facts.series_id,
        timeframe=facts.timeframe,
        segment_id=facts.segment_id,
        segment_start_ts=facts.segment_start_ts,
        warmup_start_ts=facts.segment_start_ts,
        actual_bars_since_segment_start=facts.actual_bars_since_segment_start,
        state=state,
        can_compute_features=can_compute_features,
        can_score=can_score,
        can_train_ml=can_train_ml,
        reason=reason,
    )
