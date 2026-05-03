"""
Unit tests for Market Selection Data Quality Gate.

Covers: fill_rate, gap_rate, lag, thresholds per TF, eligible, quality_score
(clamp(fill)*clamp(1-gap)), reason_flags (LOW_FILL, HIGH_GAPS, STALE_DATA, …).
"""

from __future__ import annotations

import pytest

from src.market_selection.domain.quality_gate import DataQualityGate, ReasonFlag


class TestQualityGateEvaluate:
    """Tests for DataQualityGate.evaluate()."""

    def test_eligible_when_all_pass(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """When fill_rate >= fill_min, gap_rate <= gap_max, warmup and lag OK -> eligible."""
        result = quality_gate.evaluate(
            symbol="BTCUSDT",
            timeframe="5m",
            valid_bars=9000,
            expected_bars=8640,
            gaps_count=50,
            data_lag_seconds=5 * 60,
            volume_present=True,
        )
        assert result.eligible is True
        assert result.fill_rate >= 0.97
        assert result.gap_rate <= 0.015
        assert ReasonFlag.LOW_FILL not in result.reason_flags
        assert ReasonFlag.HIGH_GAPS not in result.reason_flags
        assert ReasonFlag.STALE_DATA not in result.reason_flags
        assert 0 <= result.quality_score <= 1

    def test_low_fill_flag(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """fill_rate < fill_min -> LOW_FILL, not eligible for 5m."""
        result = quality_gate.evaluate(
            symbol="X",
            timeframe="5m",
            valid_bars=8000,
            expected_bars=8640,
            gaps_count=0,
            data_lag_seconds=0,
            volume_present=True,
        )
        assert result.fill_rate < 0.97
        assert ReasonFlag.LOW_FILL in result.reason_flags
        assert result.eligible is False

    def test_high_gaps_flag(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """gap_rate > gap_max -> HIGH_GAPS, not eligible."""
        result = quality_gate.evaluate(
            symbol="X",
            timeframe="5m",
            valid_bars=9000,
            expected_bars=8640,
            gaps_count=200,
            data_lag_seconds=0,
            volume_present=True,
        )
        assert result.gap_rate > 0.015
        assert ReasonFlag.HIGH_GAPS in result.reason_flags
        assert result.eligible is False

    def test_stale_data_flag(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """data_lag_seconds > lag_max -> STALE_DATA for 5m (15 min)."""
        result = quality_gate.evaluate(
            symbol="X",
            timeframe="5m",
            valid_bars=9000,
            expected_bars=8640,
            gaps_count=0,
            data_lag_seconds=20 * 60,
            volume_present=True,
        )
        assert ReasonFlag.STALE_DATA in result.reason_flags
        assert result.eligible is False

    def test_insufficient_warmup_flag(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """valid_bars < warmup_min_bars -> INSUFFICIENT_WARMUP."""
        result = quality_gate.evaluate(
            symbol="X",
            timeframe="5m",
            valid_bars=200,
            expected_bars=8640,
            gaps_count=0,
            data_lag_seconds=0,
            volume_present=True,
        )
        assert result.valid_bars < 280
        assert ReasonFlag.INSUFFICIENT_WARMUP in result.reason_flags
        assert result.eligible is False

    def test_no_volume_flag(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """volume_present=False -> NO_VOLUME."""
        result = quality_gate.evaluate(
            symbol="X",
            timeframe="5m",
            valid_bars=9000,
            expected_bars=8640,
            gaps_count=0,
            data_lag_seconds=0,
            volume_present=False,
        )
        assert ReasonFlag.NO_VOLUME in result.reason_flags
        assert result.eligible is False

    def test_thresholds_per_tf_1h(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """1H: fill_min=0.99, gap_max=0.005, lag_max=180 min."""
        # valid_bars >= 2160*0.99 ≈ 2138.4 для fill_rate >= 0.99
        result = quality_gate.evaluate(
            symbol="X",
            timeframe="1H",
            valid_bars=2140,
            expected_bars=2160,
            gaps_count=5,
            data_lag_seconds=60 * 60,
            volume_present=True,
        )
        assert result.fill_rate >= 0.99
        assert result.gap_rate <= 0.005
        assert result.data_lag_seconds <= 180 * 60
        assert result.eligible is True


class TestQualityScoreFormula:
    """Tests for quality_score = clamp(fill)*clamp(1-gap)."""

    def test_quality_score_perfect(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """fill_rate=1, gap_rate=0 -> quality_score=1."""
        result = quality_gate.evaluate(
            symbol="X",
            timeframe="5m",
            valid_bars=8640,
            expected_bars=8640,
            gaps_count=0,
            data_lag_seconds=0,
            volume_present=True,
        )
        assert result.fill_rate == 1.0
        assert result.gap_rate == 0.0
        assert result.quality_score == 1.0

    def test_quality_score_at_threshold(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """fill_rate=fill_min, gap_rate=0 -> fill_component=0, quality_score=0."""
        result = quality_gate.evaluate(
            symbol="X",
            timeframe="5m",
            valid_bars=int(8640 * 0.97),
            expected_bars=8640,
            gaps_count=0,
            data_lag_seconds=0,
            volume_present=True,
        )
        assert result.fill_rate == pytest.approx(0.97, rel=1e-3)
        assert result.quality_score == pytest.approx(0.0, abs=1e-6)

    def test_quality_score_between(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """quality_score is in [0, 1] and increases with better fill and lower gaps."""
        r1 = quality_gate.evaluate(
            symbol="A",
            timeframe="5m",
            valid_bars=8500,
            expected_bars=8640,
            gaps_count=20,
            data_lag_seconds=0,
            volume_present=True,
        )
        r2 = quality_gate.evaluate(
            symbol="B",
            timeframe="5m",
            valid_bars=8600,
            expected_bars=8640,
            gaps_count=5,
            data_lag_seconds=0,
            volume_present=True,
        )
        assert 0 <= r1.quality_score <= 1
        assert 0 <= r2.quality_score <= 1
        assert r2.quality_score >= r1.quality_score


class TestDetectGaps:
    """Tests for detect_gaps()."""

    def test_no_gaps_when_regular(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """Regular 5m spacing -> no gaps (delta = 5*60*1000 ms)."""
        base = 1000000000000
        step = 5 * 60 * 1000
        timestamps = [base + i * step for i in range(100)]
        count = quality_gate.detect_gaps(timestamps, "5m")
        assert count == 0

    def test_gap_when_delta_too_large(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """Delta > 1.5 * tf_ms -> counted as gap."""
        base = 1000000000000
        step = 5 * 60 * 1000
        timestamps = [base, base + step, base + step * 3]
        count = quality_gate.detect_gaps(timestamps, "5m")
        assert count >= 1

    def test_empty_or_single_no_gaps(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """Less than 2 timestamps -> 0 gaps."""
        assert quality_gate.detect_gaps([], "5m") == 0
        assert quality_gate.detect_gaps([1000], "5m") == 0


class TestExpectedBars:
    """Tests for calculate_expected_bars()."""

    def test_5m_30d(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """5m over 30 days: 30*24*60/5 = 8640 bars."""
        n = quality_gate.calculate_expected_bars("5m", 30)
        expected = 30 * 24 * 12
        assert n == expected

    def test_1h_90d(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """1H over 90 days: 90*24 bars."""
        n = quality_gate.calculate_expected_bars("1H", 90)
        assert n == 90 * 24


class TestBatchEvaluateAndSummarize:
    """Tests for batch_evaluate and summarize_results."""

    def test_batch_evaluate(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """batch_evaluate returns list of QualityResult."""
        data = [
            {
                "symbol": "A",
                "timeframe": "5m",
                "valid_bars": 9000,
                "expected_bars": 8640,
                "gaps_count": 10,
                "data_lag_seconds": 0,
                "volume_present": True,
            },
            {
                "symbol": "B",
                "timeframe": "5m",
                "valid_bars": 5000,
                "expected_bars": 8640,
                "gaps_count": 100,
                "data_lag_seconds": 0,
                "volume_present": True,
            },
        ]
        results = quality_gate.batch_evaluate(data)
        assert len(results) == 2
        assert results[0].symbol == "A"
        assert results[0].eligible is True
        assert results[1].symbol == "B"
        assert results[1].eligible is False

    def test_summarize_results(
        self,
        quality_gate: DataQualityGate,
    ) -> None:
        """summarize_results returns total, eligible, ineligible, reason_counts."""
        data = [
            {
                "symbol": "A",
                "timeframe": "5m",
                "valid_bars": 9000,
                "expected_bars": 8640,
                "gaps_count": 0,
                "data_lag_seconds": 0,
                "volume_present": True,
            },
            {
                "symbol": "B",
                "timeframe": "5m",
                "valid_bars": 100,
                "expected_bars": 8640,
                "gaps_count": 0,
                "data_lag_seconds": 0,
                "volume_present": True,
            },
        ]
        results = quality_gate.batch_evaluate(data)
        summary = quality_gate.summarize_results(results)
        assert summary["total"] == 2
        assert summary["eligible"] == 1
        assert summary["ineligible"] == 1
        assert "reason_counts" in summary
        assert summary["avg_quality_score"] >= 0
