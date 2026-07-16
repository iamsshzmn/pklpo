from __future__ import annotations


def _facts(
    *,
    timeframe: str = "1H",
    actual_bars_since_segment_start: int,
    is_partial_event_bucket: bool = False,
    segment_id: str = "seg-gram",
    segment_start_ts: int = 1_781_000_000_000,
):
    from src.identity.application.segment_eligibility import SegmentEligibilityFacts

    return SegmentEligibilityFacts(
        series_id="TON-USDT-SWAP",
        timeframe=timeframe,
        segment_id=segment_id,
        segment_start_ts=segment_start_ts,
        actual_bars_since_segment_start=actual_bars_since_segment_start,
        is_partial_event_bucket=is_partial_event_bucket,
    )


def test_eligibility_fail_closed_after_gap() -> None:
    """Right after the TON->GRAM gap, ton_gram must NOT immediately look
    eligible just because the composite series has thousands of pre-gap TON
    bars. Warmup is counted from segment_start_ts only."""
    from src.identity.application.segment_eligibility import (
        evaluate_segment_eligibility,
    )

    verdict = evaluate_segment_eligibility(
        _facts(timeframe="1H", actual_bars_since_segment_start=10)
    )

    assert verdict.state == "insufficient_history"
    assert verdict.can_compute_features is True
    assert verdict.can_score is False
    assert verdict.can_train_ml is False
    assert verdict.warmup_start_ts == verdict.segment_start_ts
    assert verdict.reason == "warmup_from_segment_start_not_satisfied"


def test_eligibility_becomes_eligible_once_segment_warmup_satisfied() -> None:
    from src.identity.application.segment_eligibility import (
        evaluate_segment_eligibility,
    )

    verdict = evaluate_segment_eligibility(
        _facts(timeframe="1H", actual_bars_since_segment_start=500)
    )

    assert verdict.state == "eligible"
    assert verdict.can_compute_features is True
    assert verdict.can_score is True
    assert verdict.can_train_ml is True


def test_partial_bucket_not_trainable() -> None:
    """A bucket whose interval crosses the migration/event boundary must
    never be scoreable or trainable, even with plenty of bars."""
    from src.identity.application.segment_eligibility import (
        evaluate_segment_eligibility,
    )

    verdict = evaluate_segment_eligibility(
        _facts(
            timeframe="1H",
            actual_bars_since_segment_start=600,
            is_partial_event_bucket=True,
        )
    )

    assert verdict.state == "incomplete_history"
    assert verdict.can_compute_features is True
    assert verdict.can_score is False
    assert verdict.can_train_ml is False
    assert verdict.reason == "partial_event_bucket_not_trainable"


def test_context_only_timeframe_never_scores_even_when_eligible() -> None:
    from src.identity.application.segment_eligibility import (
        evaluate_segment_eligibility,
    )

    verdict = evaluate_segment_eligibility(
        _facts(timeframe="1W", actual_bars_since_segment_start=280)
    )

    assert verdict.state == "eligible"
    assert verdict.can_compute_features is True
    assert verdict.can_score is False
    assert verdict.can_train_ml is False
    assert verdict.reason == "context_only_timeframe"


def test_unregistered_timeframe_fails_closed_disabled() -> None:
    from src.identity.application.segment_eligibility import (
        evaluate_segment_eligibility,
    )

    verdict = evaluate_segment_eligibility(
        _facts(timeframe="1m", actual_bars_since_segment_start=100_000)
    )

    assert verdict.state == "disabled"
    assert verdict.can_compute_features is False
    assert verdict.can_score is False
    assert verdict.can_train_ml is False
