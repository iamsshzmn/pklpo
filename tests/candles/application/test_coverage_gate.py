from __future__ import annotations


def test_coverage_gate_passes_for_contiguous_warmup_window() -> None:
    from src.candles.application.coverage_gate import evaluate_ohlcv_coverage

    timestamps = [i * 60_000 for i in range(500)]

    result = evaluate_ohlcv_coverage(
        timestamps_ms=timestamps,
        timeframe="1m",
        required_bars=500,
    )

    assert result.passed
    assert result.actual_bars == 500
    assert result.missing_count == 0


def test_coverage_gate_blocks_interior_gap_inside_warmup_window() -> None:
    from src.candles.application.coverage_gate import evaluate_ohlcv_coverage

    timestamps = [i * 60_000 for i in range(501) if i != 250]

    result = evaluate_ohlcv_coverage(
        timestamps_ms=timestamps,
        timeframe="1m",
        required_bars=500,
    )

    assert not result.passed
    assert result.reason == "interior_gap"
    assert result.missing_count == 1
    assert result.missing_timestamps_ms == (250 * 60_000,)


def test_coverage_gate_blocks_insufficient_history() -> None:
    from src.candles.application.coverage_gate import evaluate_ohlcv_coverage

    result = evaluate_ohlcv_coverage(
        timestamps_ms=[i * 3_600_000 for i in range(279)],
        timeframe="1H",
        required_bars=280,
    )

    assert not result.passed
    assert result.reason == "insufficient_history"
    assert result.actual_bars == 279
