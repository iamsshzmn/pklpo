from __future__ import annotations

from dataclasses import dataclass

from src.features.domain.timeframe import timeframe_to_seconds


@dataclass(frozen=True)
class CoverageGateResult:
    passed: bool
    reason: str | None
    expected_bars: int
    actual_bars: int
    coverage_ratio: float
    missing_timestamps_ms: tuple[int, ...]

    @property
    def missing_count(self) -> int:
        return len(self.missing_timestamps_ms)


def evaluate_ohlcv_coverage(
    *,
    timestamps_ms: list[int] | tuple[int, ...],
    timeframe: str,
    required_bars: int,
    min_coverage_ratio: float = 1.0,
    end_ts_ms: int | None = None,
) -> CoverageGateResult:
    """Validate contiguous OHLCV coverage inside the warm-up window."""
    if required_bars <= 0:
        return CoverageGateResult(
            passed=True,
            reason=None,
            expected_bars=0,
            actual_bars=0,
            coverage_ratio=1.0,
            missing_timestamps_ms=(),
        )

    step_ms = timeframe_to_seconds(timeframe) * 1000
    unique_timestamps = sorted({int(ts) for ts in timestamps_ms})
    if end_ts_ms is not None:
        unique_timestamps = [ts for ts in unique_timestamps if ts < end_ts_ms]
    if not unique_timestamps:
        return CoverageGateResult(
            passed=False,
            reason="no_data",
            expected_bars=required_bars,
            actual_bars=0,
            coverage_ratio=0.0,
            missing_timestamps_ms=(),
        )

    window_end_ts = unique_timestamps[-1]
    window_start_ts = window_end_ts - ((required_bars - 1) * step_ms)
    actual_window = {
        ts for ts in unique_timestamps if window_start_ts <= ts <= window_end_ts
    }
    missing = tuple(
        ts
        for ts in range(window_start_ts, window_end_ts + step_ms, step_ms)
        if ts not in actual_window
    )
    actual_bars = len(actual_window)
    coverage_ratio = actual_bars / required_bars
    passed = not missing and coverage_ratio >= min_coverage_ratio
    reason = None
    if not passed:
        reason = (
            "insufficient_history"
            if len(unique_timestamps) < required_bars
            else "interior_gap"
        )
    return CoverageGateResult(
        passed=passed,
        reason=reason,
        expected_bars=required_bars,
        actual_bars=actual_bars,
        coverage_ratio=coverage_ratio,
        missing_timestamps_ms=missing,
    )
