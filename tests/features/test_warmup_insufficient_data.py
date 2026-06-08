from __future__ import annotations

import pytest


@pytest.mark.parametrize("timeframe", ["1H", "4H", "1D"])
@pytest.mark.parametrize("bars", [199, 233, 279, 280])
def test_research_timeframes_skip_when_below_recommended_warmup(
    timeframe: str,
    bars: int,
) -> None:
    from src.candles.application.coverage_gate import evaluate_ohlcv_coverage
    from src.features.domain.timeframe import timeframe_to_seconds
    from src.features.domain.warmup_contract import build_warmup_contract

    contract = build_warmup_contract()
    step_ms = timeframe_to_seconds(timeframe) * 1000
    timestamps = [i * step_ms for i in range(bars)]

    result = evaluate_ohlcv_coverage(
        timestamps_ms=timestamps,
        timeframe=timeframe,
        required_bars=contract.recommended_bars,
    )

    assert not result.passed
    assert result.reason == "insufficient_history"


@pytest.mark.parametrize("timeframe", ["1H", "4H", "1D"])
def test_research_timeframes_pass_at_recommended_warmup(timeframe: str) -> None:
    from src.candles.application.coverage_gate import evaluate_ohlcv_coverage
    from src.features.domain.timeframe import timeframe_to_seconds
    from src.features.domain.warmup_contract import build_warmup_contract

    contract = build_warmup_contract()
    step_ms = timeframe_to_seconds(timeframe) * 1000
    timestamps = [i * step_ms for i in range(contract.recommended_bars)]

    result = evaluate_ohlcv_coverage(
        timestamps_ms=timestamps,
        timeframe=timeframe,
        required_bars=contract.recommended_bars,
    )

    assert result.passed


def test_weekly_context_timeframe_passes_at_operational_warmup() -> None:
    from src.candles.application.coverage_gate import evaluate_ohlcv_coverage
    from src.features.domain.timeframe import timeframe_to_seconds
    from src.features.domain.warmup_contract import build_warmup_contract

    contract = build_warmup_contract()
    step_ms = timeframe_to_seconds("1W") * 1000
    timestamps = [i * step_ms for i in range(contract.operational_min_bars)]

    result = evaluate_ohlcv_coverage(
        timestamps_ms=timestamps,
        timeframe="1W",
        required_bars=contract.operational_min_bars,
    )

    assert result.passed


def test_cumulative_indicators_are_explicitly_classified() -> None:
    from src.features.domain.warmup_contract import build_warmup_contract

    contract = build_warmup_contract()

    assert {"ad", "obv", "vwap"}.issubset(contract.cumulative_features)
    assert contract.cumulative_features.isdisjoint(contract.lookahead_features)
