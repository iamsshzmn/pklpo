from __future__ import annotations

from src.candles.application.repair.progress import NoProgressTracker
from src.candles.domain.repair import NoProgressPolicy


def test_no_progress_tracker_resets_after_positive_progress() -> None:
    tracker = NoProgressTracker(policy=NoProgressPolicy(), timeframe="1H")

    tracker.record(progress=0)
    tracker.record(progress=-3)
    assert tracker.snapshot() == {
        "timeframe": "1H",
        "critical": True,
        "consecutive_no_progress": 2,
        "consecutive_blocked": 0,
        "threshold": 3,
    }

    tracker.record(progress=1)

    assert tracker.should_escalate() is False
    assert tracker.snapshot() == {
        "timeframe": "1H",
        "critical": True,
        "consecutive_no_progress": 0,
        "consecutive_blocked": 0,
        "threshold": 3,
    }


def test_no_progress_tracker_escalates_at_threshold_for_critical_timeframe() -> None:
    tracker = NoProgressTracker(policy=NoProgressPolicy(), timeframe="1H")

    tracker.record(progress=0)
    tracker.record(progress=0)
    assert tracker.should_escalate() is False

    tracker.record(progress=0)

    assert tracker.should_escalate() is True


def test_no_progress_tracker_does_not_escalate_for_non_critical_timeframe() -> None:
    tracker = NoProgressTracker(policy=NoProgressPolicy(), timeframe="1D")

    tracker.record(progress=0)
    tracker.record(progress=0)
    tracker.record(progress=0)
    tracker.record(progress=-1)

    assert tracker.should_escalate() is False
    assert tracker.snapshot() == {
        "timeframe": "1D",
        "critical": False,
        "consecutive_no_progress": 4,
        "consecutive_blocked": 0,
        "threshold": 3,
    }


def test_no_progress_tracker_snapshot_shape() -> None:
    tracker = NoProgressTracker(
        policy=NoProgressPolicy(
            critical_timeframes=frozenset({"1m"}),
            no_progress_threshold=5,
        ),
        timeframe="1m",
    )

    assert tracker.snapshot() == {
        "timeframe": "1m",
        "critical": True,
        "consecutive_no_progress": 0,
        "consecutive_blocked": 0,
        "threshold": 5,
    }


def test_no_progress_tracker_tracks_blocked_without_escalation() -> None:
    tracker = NoProgressTracker(policy=NoProgressPolicy(), timeframe="1H")

    tracker.record(progress=0, blocked=True)
    tracker.record(progress=0, blocked=True)
    tracker.record(progress=0, blocked=True)

    assert tracker.should_escalate() is False
    assert tracker.snapshot() == {
        "timeframe": "1H",
        "critical": True,
        "consecutive_no_progress": 0,
        "consecutive_blocked": 3,
        "threshold": 3,
    }
