from __future__ import annotations

from decimal import Decimal


def _bar(segment_id: str, timestamp: int, value: str):
    from src.identity.application.feature_reset_policy import SegmentedBar

    return SegmentedBar(
        segment_id=segment_id, timestamp=timestamp, value=Decimal(value)
    )


def test_feature_reset_policy_matrix_matches_model_14_11() -> None:
    from src.identity.application.feature_reset_policy import (
        FEATURE_RESET_POLICIES,
        get_feature_reset_policy,
    )

    expected = {
        "rsi": ("rolling", "reset_with_warmup"),
        "ema": ("rolling", "reset_with_warmup"),
        "atr": ("rolling", "reset_with_warmup"),
        "bollinger": ("rolling", "reset_with_warmup"),
        "obv": ("cumulative", "reset_cumulative"),
        "ad": ("cumulative", "reset_cumulative"),
        "pvt": ("cumulative", "reset_cumulative"),
        "nvi": ("cumulative", "reset_cumulative"),
        "pvi": ("cumulative", "reset_cumulative"),
        "vwap": ("cumulative", "reset_by_segment_session"),
        "returns": ("stateless", "no_cross_gap_return"),
        "volatility": ("rolling", "exclude_cross_gap_jump"),
    }

    names = {policy.indicator_name for policy in FEATURE_RESET_POLICIES}
    assert names == set(expected)

    for name, (statefulness, gap_behavior) in expected.items():
        policy = get_feature_reset_policy(name)
        assert policy.statefulness == statefulness
        assert policy.gap_behavior == gap_behavior
        # No indicator in the matrix is allowed to carry state across a
        # segment boundary — that is the entire point of §14.11.
        assert policy.cross_segment_allowed is False


def test_get_feature_reset_policy_fails_closed_for_unknown_indicator() -> None:
    from src.identity.application.feature_reset_policy import get_feature_reset_policy

    policy = get_feature_reset_policy("some_future_indicator_nobody_registered")

    assert policy.statefulness == "rolling"
    assert policy.gap_behavior == "reset_with_warmup"
    assert policy.cross_segment_allowed is False
    assert policy.warmup_bars > 0


def test_rolling_resets_on_segment_boundary() -> None:
    from src.identity.application.feature_reset_policy import (
        rolling_indicator_with_reset,
    )

    # TON segment: 5 bars of large, distinct values.
    # GRAM segment: 4 bars of small, distinct values.
    # If the rolling window ever crossed the boundary, early GRAM averages
    # would be pulled way up by TON's tail.
    bars = [
        _bar("seg-ton", 1, "1000"),
        _bar("seg-ton", 2, "1010"),
        _bar("seg-ton", 3, "1020"),
        _bar("seg-ton", 4, "1030"),
        _bar("seg-ton", 5, "1040"),
        _bar("seg-gram", 6, "10"),
        _bar("seg-gram", 7, "11"),
        _bar("seg-gram", 8, "12"),
        _bar("seg-gram", 9, "13"),
    ]

    def average(values):
        return sum(values) / len(values)

    result = rolling_indicator_with_reset(
        bars, window=3, warmup_bars=2, compute=average
    )

    # TON: warmup_bars=2 -> first 2 bars are None, then rolling window of <=3.
    assert result[0] is None
    assert result[1] is None
    assert result[2] == (Decimal("1000") + Decimal("1010") + Decimal("1020")) / 3
    assert result[3] == (Decimal("1010") + Decimal("1020") + Decimal("1030")) / 3
    assert result[4] == (Decimal("1020") + Decimal("1030") + Decimal("1040")) / 3

    # GRAM segment restarts warmup from its own segment_start, not TON's.
    assert result[5] is None  # 1st bar into seg-gram, warmup_bars=2
    assert result[6] is None  # 2nd bar into seg-gram
    # 3rd bar into seg-gram: window is capped at the segment start, so it only
    # ever sees GRAM values (10, 11, 12) — never TON's 1030/1040 tail.
    assert result[7] == (Decimal("10") + Decimal("11") + Decimal("12")) / 3
    assert result[8] == (Decimal("11") + Decimal("12") + Decimal("13")) / 3


def test_cumulative_resets_on_segment_boundary() -> None:
    from src.identity.application.feature_reset_policy import (
        cumulative_indicator_with_reset,
    )

    bars = [
        _bar("seg-ton", 1, "10"),
        _bar("seg-ton", 2, "20"),
        _bar("seg-ton", 3, "30"),
        _bar("seg-gram", 4, "5"),
        _bar("seg-gram", 5, "5"),
    ]

    def running_sum(total, bar):
        return total + bar.value

    result = cumulative_indicator_with_reset(
        bars, step=running_sum, reset_value=Decimal("0")
    )

    # TON accumulates normally: 10, 30, 60.
    assert result[0:3] == [Decimal("10"), Decimal("30"), Decimal("60")]

    # GRAM must restart from 0, not continue from TON's accumulated 60.
    assert result[3] == Decimal("5")
    assert result[4] == Decimal("10")


def test_continuous_does_not_cross_gap_returns() -> None:
    from src.identity.application.feature_reset_policy import returns_no_cross_gap

    bars = [
        _bar("seg-ton", 1, "100"),
        _bar("seg-ton", 2, "110"),
        _bar("seg-gram", 3, "50"),  # succession jump, not a real -55% move
        _bar("seg-gram", 4, "55"),
    ]

    result = returns_no_cross_gap(bars)

    assert result[0] is None  # first bar overall: no predecessor
    assert result[1] == (Decimal("110") - Decimal("100")) / Decimal("100")
    # The TON->GRAM boundary must not be computed as an ordinary return.
    assert result[2] is None
    # Within the GRAM segment, returns resume normally.
    assert result[3] == (Decimal("55") - Decimal("50")) / Decimal("50")
