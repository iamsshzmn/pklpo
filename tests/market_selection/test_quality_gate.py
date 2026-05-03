"""
Тесты для quality gate.
"""

import pytest

from src.market_selection.application.config_projection import build_quality_gate_config
from src.market_selection.config import MarketSelectionConfig
from src.market_selection.domain.quality_gate import (
    DataQualityGate,
    QualityResult,
    ReasonFlag,
)


@pytest.fixture
def quality_gate():
    """Фикстура quality gate."""
    config = build_quality_gate_config(MarketSelectionConfig())
    return DataQualityGate(config)


def test_quality_gate_eligible_all_pass(quality_gate):
    result = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=1000,
        expected_bars=1000,
        gaps_count=0,
        data_lag_seconds=60,
        volume_present=True,
    )

    assert result.eligible is True
    assert result.fill_rate == pytest.approx(1.0)
    assert result.gap_rate == pytest.approx(0.0)
    assert result.quality_score > 0.9
    assert result.reason_flags == []


def test_quality_gate_low_fill(quality_gate):
    result = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=500,
        expected_bars=1000,
        gaps_count=0,
        data_lag_seconds=60,
        volume_present=True,
    )

    assert result.eligible is False
    assert result.fill_rate == pytest.approx(0.5)
    assert ReasonFlag.LOW_FILL in result.reason_flags


def test_quality_gate_high_gaps(quality_gate):
    result = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=1000,
        expected_bars=1000,
        gaps_count=20,
        data_lag_seconds=60,
        volume_present=True,
    )

    assert result.eligible is False
    assert ReasonFlag.HIGH_GAPS in result.reason_flags


def test_quality_gate_insufficient_warmup(quality_gate):
    result = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=100,
        expected_bars=1000,
        gaps_count=0,
        data_lag_seconds=60,
        volume_present=True,
    )

    assert result.eligible is False
    assert ReasonFlag.INSUFFICIENT_WARMUP in result.reason_flags


def test_quality_gate_no_volume(quality_gate):
    result = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=1000,
        expected_bars=1000,
        gaps_count=0,
        data_lag_seconds=60,
        volume_present=False,
    )

    assert result.eligible is False
    assert ReasonFlag.NO_VOLUME in result.reason_flags


def test_quality_gate_stale_data(quality_gate):
    result = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=1000,
        expected_bars=1000,
        gaps_count=0,
        data_lag_seconds=200 * 60,
        volume_present=True,
    )

    assert result.eligible is False
    assert ReasonFlag.STALE_DATA in result.reason_flags


def test_quality_gate_marks_missing_metric_input(quality_gate):
    result = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=1000,
        expected_bars=1000,
        gaps_count=0,
        data_lag_seconds=60,
        volume_present=True,
        feature_bars=850,
    )

    assert result.eligible is True
    assert ReasonFlag.MISSING_METRIC_INPUT in result.reason_flags
    assert result.feature_bars == 850


def test_quality_gate_quality_score_calculation(quality_gate):
    ideal = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=1000,
        expected_bars=1000,
        gaps_count=0,
        data_lag_seconds=60,
        volume_present=True,
    )
    assert ideal.quality_score == pytest.approx(1.0, abs=0.01)

    min_fill = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=990,
        expected_bars=1000,
        gaps_count=0,
        data_lag_seconds=60,
        volume_present=True,
    )
    assert min_fill.quality_score == pytest.approx(0.0, abs=0.1)

    max_gap = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=1000,
        expected_bars=1000,
        gaps_count=5,
        data_lag_seconds=60,
        volume_present=True,
    )
    assert max_gap.quality_score == pytest.approx(0.0, abs=0.1)


def test_quality_gate_calculate_expected_bars(quality_gate):
    assert quality_gate.calculate_expected_bars("1H", 30) == 720
    assert quality_gate.calculate_expected_bars("5m", 1) == 288


def test_quality_gate_detect_gaps(quality_gate):
    assert quality_gate.detect_gaps([1000, 61000, 121000, 181000], "1m") == 0
    assert quality_gate.detect_gaps([1000, 61000, 200000, 261000], "1m") >= 1
    assert quality_gate.detect_gaps([], "1m") == 0
    assert quality_gate.detect_gaps([1000], "1m") == 0


def test_quality_gate_batch_evaluate(quality_gate):
    quality_data = [
        {
            "symbol": "BTC-USDT",
            "timeframe": "1H",
            "valid_bars": 1000,
            "expected_bars": 1000,
            "gaps_count": 0,
            "data_lag_seconds": 60,
            "volume_present": True,
        },
        {
            "symbol": "ETH-USDT",
            "timeframe": "1H",
            "valid_bars": 500,
            "expected_bars": 1000,
            "gaps_count": 0,
            "data_lag_seconds": 60,
            "volume_present": True,
        },
    ]

    results = quality_gate.batch_evaluate(quality_data)
    assert len(results) == 2
    assert results[0].eligible is True
    assert results[1].eligible is False


def test_quality_gate_summarize_results(quality_gate):
    results = [
        QualityResult(
            symbol="BTC-USDT",
            timeframe="1H",
            fill_rate=1.0,
            gap_rate=0.0,
            data_lag_seconds=60,
            valid_bars=1000,
            expected_bars=1000,
            eligible=True,
            quality_score=1.0,
        ),
        QualityResult(
            symbol="ETH-USDT",
            timeframe="1H",
            fill_rate=0.5,
            gap_rate=0.0,
            data_lag_seconds=60,
            valid_bars=500,
            expected_bars=1000,
            eligible=False,
            quality_score=0.0,
            reason_flags=[ReasonFlag.LOW_FILL],
        ),
    ]

    summary = quality_gate.summarize_results(results)
    assert summary["total"] == 2
    assert summary["eligible"] == 1
    assert summary["ineligible"] == 1
    assert summary["avg_quality_score"] == pytest.approx(1.0)
    assert summary["reason_counts"]["LOW_FILL"] == 1
    assert quality_gate.summarize_results([]) == {
        "total": 0,
        "eligible": 0,
        "ineligible": 0,
    }
