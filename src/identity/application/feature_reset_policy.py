"""Feature reset policy matrix + segment-aware calculation primitives.

§14.11 (feature reset policy matrix) + §13.7 (features must be computed per
segment_id). The central mistake this guards against: stitching TON+GRAM into
one continuous price series and then feeding a stateful indicator (rolling or
cumulative) straight across the succession boundary as if nothing happened.
Indicators have memory; a gap is an event boundary, not a normal price move.

This module is the single source of truth for:

- which indicators are stateless / rolling / cumulative, and what must happen
  to them at a segment boundary (`FEATURE_RESET_POLICIES`);
- the segment-aware primitives feature jobs use to actually enforce that
  (`rolling_indicator_with_reset`, `cumulative_indicator_with_reset`,
  `returns_no_cross_gap`) so behavior is not reimplemented ad hoc per job.

Consumers key policies by `segment_id` (from `core.series_segments` /
`OhlcvFacadeRow.segment_id`), not by raw symbol — a segment boundary is where
`source_symbol` changes (succession) or a classified gap sits, matching the
facade's own segment_id assignment (§12.3, §14.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

Statefulness = Literal["stateless", "rolling", "cumulative"]

GapBehavior = Literal[
    "reset_with_warmup",
    "reset_cumulative",
    "reset_by_segment_session",
    "no_cross_gap_return",
    "exclude_cross_gap_jump",
]

# Fail-closed default for any indicator not explicitly classified below: treat
# it as the strictest stateful case (rolling reset + warmup, no cross-segment
# carry-over) rather than silently allowing it to leak across a gap.
_DEFAULT_UNKNOWN_WARMUP_BARS = 14


@dataclass(frozen=True)
class FeatureResetPolicy:
    indicator_name: str
    statefulness: Statefulness
    gap_behavior: GapBehavior
    warmup_bars: int
    cross_segment_allowed: bool


# §14.11 matrix, verbatim.
FEATURE_RESET_POLICIES: tuple[FeatureResetPolicy, ...] = (
    FeatureResetPolicy("rsi", "rolling", "reset_with_warmup", 14, False),
    FeatureResetPolicy("ema", "rolling", "reset_with_warmup", 21, False),
    FeatureResetPolicy("atr", "rolling", "reset_with_warmup", 14, False),
    FeatureResetPolicy("bollinger", "rolling", "reset_with_warmup", 20, False),
    FeatureResetPolicy("obv", "cumulative", "reset_cumulative", 0, False),
    FeatureResetPolicy("ad", "cumulative", "reset_cumulative", 0, False),
    FeatureResetPolicy("pvt", "cumulative", "reset_cumulative", 0, False),
    FeatureResetPolicy("nvi", "cumulative", "reset_cumulative", 0, False),
    FeatureResetPolicy("pvi", "cumulative", "reset_cumulative", 0, False),
    FeatureResetPolicy("vwap", "cumulative", "reset_by_segment_session", 0, False),
    FeatureResetPolicy("returns", "stateless", "no_cross_gap_return", 1, False),
    FeatureResetPolicy("volatility", "rolling", "exclude_cross_gap_jump", 2, False),
)

_POLICY_BY_NAME: dict[str, FeatureResetPolicy] = {
    policy.indicator_name: policy for policy in FEATURE_RESET_POLICIES
}


def get_feature_reset_policy(indicator_name: str) -> FeatureResetPolicy:
    """Look up the reset policy for an indicator family (e.g. "rsi", "ema").

    Unknown indicators fail closed: rolling reset + warmup, no cross-segment
    carry-over. This must never silently default to "safe to carry over" —
    that is exactly the cross-gap leakage this module exists to prevent.
    """
    policy = _POLICY_BY_NAME.get(indicator_name)
    if policy is not None:
        return policy
    return FeatureResetPolicy(
        indicator_name=indicator_name,
        statefulness="rolling",
        gap_behavior="reset_with_warmup",
        warmup_bars=_DEFAULT_UNKNOWN_WARMUP_BARS,
        cross_segment_allowed=False,
    )


@dataclass(frozen=True)
class SegmentedBar:
    """A single bar's input value, tagged with the segment it belongs to."""

    segment_id: str
    timestamp: int
    value: Decimal


def rolling_indicator_with_reset(
    bars: Sequence[SegmentedBar],
    *,
    window: int,
    warmup_bars: int,
    compute: Callable[[Sequence[Decimal]], Decimal],
) -> list[Decimal | None]:
    """Compute a rolling indicator whose lookback window never crosses a
    segment boundary, and whose first `warmup_bars` bars in a new segment are
    `None` (warmup), regardless of how much history the previous segment had.
    """
    results: list[Decimal | None] = []
    segment_start_idx = 0
    for i, bar in enumerate(bars):
        if i == 0 or bar.segment_id != bars[i - 1].segment_id:
            segment_start_idx = i

        bars_into_segment = i - segment_start_idx + 1
        if bars_into_segment <= warmup_bars:
            results.append(None)
            continue

        window_start = max(segment_start_idx, i - window + 1)
        window_values = [b.value for b in bars[window_start : i + 1]]
        results.append(compute(window_values))
    return results


def cumulative_indicator_with_reset(
    bars: Sequence[SegmentedBar],
    *,
    step: Callable[[Decimal, SegmentedBar], Decimal],
    reset_value: Decimal = Decimal("0"),
) -> list[Decimal]:
    """Compute a cumulative indicator (OBV/AD/PVT/NVI/PVI-style) that resets
    its running accumulator to `reset_value` at the first bar of every new
    segment — the previous segment's accumulated total must not carry over.
    """
    results: list[Decimal] = []
    running = reset_value
    previous_segment_id: str | None = None
    for bar in bars:
        if bar.segment_id != previous_segment_id:
            running = reset_value
        running = step(running, bar)
        results.append(running)
        previous_segment_id = bar.segment_id
    return results


def returns_no_cross_gap(bars: Sequence[SegmentedBar]) -> list[Decimal | None]:
    """Percent return per bar; `None` at the first bar of a segment (there is
    no same-segment predecessor to diff against — computing `(first GRAM
    close - last TON close) / last TON close` would treat an event boundary
    as an ordinary market move)."""
    results: list[Decimal | None] = []
    for i, bar in enumerate(bars):
        if i == 0 or bar.segment_id != bars[i - 1].segment_id:
            results.append(None)
            continue
        previous_value = bars[i - 1].value
        if previous_value == 0:
            results.append(None)
            continue
        results.append((bar.value - previous_value) / previous_value)
    return results
