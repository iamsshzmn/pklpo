"""
Data Quality Gate for Market Selection

Checks data quality per (symbol, timeframe) before scoring:
- fill_rate: proportion of bars with valid features
- gap_rate: proportion of time gaps
- data_lag: how stale the data is
- warmup: minimum bars requirement
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import QualityGateConfig


class ReasonFlag(StrEnum):
    """Exclusion and warning flags for quality gate."""

    # Quality issues
    LOW_FILL = "LOW_FILL"
    HIGH_GAPS = "HIGH_GAPS"
    INSUFFICIENT_WARMUP = "INSUFFICIENT_WARMUP"
    NO_VOLUME = "NO_VOLUME"
    STALE_DATA = "STALE_DATA"

    # Feature issues
    MISSING_METRIC_INPUT = "MISSING_METRIC_INPUT"
    SHORT_FEATURE_MISMATCH = "SHORT_FEATURE_MISMATCH"

    # Universe issues
    SMALL_UNIVERSE_FALLBACK = "SMALL_UNIVERSE_FALLBACK"
    UNIVERSE_FALLBACK_PREV = "UNIVERSE_FALLBACK_PREV"

    # Regime issues
    LOW_LIQ_IN_VOLATILE = "LOW_LIQ_IN_VOLATILE"
    STALE_REGIME = "STALE_REGIME"

    # Senior TF issues
    MISSING_SENIOR_TF = "MISSING_SENIOR_TF"
    TEMP_MISSING_SENIOR = "TEMP_MISSING_SENIOR"
    STRUCTURAL_MISSING_SENIOR = "STRUCTURAL_MISSING_SENIOR"
    SYSTEMIC_SENIOR_OUTAGE = "SYSTEMIC_SENIOR_OUTAGE"
    MISSING_4H_SOFT = "MISSING_4H_SOFT"
    MISSING_1H_SOFT = "MISSING_1H_SOFT"

    # History issues
    SHORT_HISTORY = "SHORT_HISTORY"


@dataclass
class QualityResult:
    """Result of quality gate evaluation for a single (symbol, timeframe)."""

    symbol: str
    timeframe: str

    # Core metrics
    fill_rate: float
    gap_rate: float
    data_lag_seconds: int
    valid_bars: int
    expected_bars: int

    # Derived
    eligible: bool
    quality_score: float
    reason_flags: list[ReasonFlag] = field(default_factory=list)

    # Optional details
    volume_present: bool = True
    feature_bars: int = 0  # bars with all key features present

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "fill_rate": self.fill_rate,
            "gap_rate": self.gap_rate,
            "data_lag_seconds": self.data_lag_seconds,
            "valid_bars": self.valid_bars,
            "expected_bars": self.expected_bars,
            "eligible": self.eligible,
            "quality_score": self.quality_score,
            "reason_flags": [f.value for f in self.reason_flags],
        }


class DataQualityGate:
    """
    Evaluates data quality for market selection.

    For each (symbol, timeframe), determines:
    - eligible: whether the pair can participate in scoring
    - quality_score: a 0-1 score reflecting data quality
    - reason_flags: specific issues found
    """

    def __init__(self, config: QualityGateConfig):
        self.config = config

    def evaluate(
        self,
        symbol: str,
        timeframe: str,
        valid_bars: int,
        expected_bars: int,
        gaps_count: int,
        data_lag_seconds: int,
        volume_present: bool = True,
        feature_bars: int | None = None,
    ) -> QualityResult:
        """
        Evaluate quality for a single (symbol, timeframe).

        Args:
            symbol: Trading pair symbol
            timeframe: Candle timeframe (5m, 15m, 1H, 4H)
            valid_bars: Number of bars with non-null key features
            expected_bars: Expected number of bars in window
            gaps_count: Number of time gaps detected
            data_lag_seconds: How stale the latest data is
            volume_present: Whether volume data exists
            feature_bars: Bars with ALL key features (optional)

        Returns:
            QualityResult with eligibility decision and score
        """
        thresholds = self.config.get_quality_thresholds(timeframe)
        fill_min = thresholds["fill_min"]
        gap_max = thresholds["gap_max"]
        lag_max_seconds = thresholds["lag_max_min"] * 60

        reason_flags: list[ReasonFlag] = []

        # Calculate rates
        if expected_bars > 0:
            fill_rate = valid_bars / expected_bars
            gap_rate = gaps_count / expected_bars
        else:
            fill_rate = 0.0
            gap_rate = 1.0
            reason_flags.append(ReasonFlag.INSUFFICIENT_WARMUP)

        # Check fill rate
        if fill_rate < fill_min:
            reason_flags.append(ReasonFlag.LOW_FILL)

        # Check gap rate
        if gap_rate > gap_max:
            reason_flags.append(ReasonFlag.HIGH_GAPS)

        # Check warmup
        warmup_min = self.config.warmup_min_bars
        if valid_bars < warmup_min:
            if ReasonFlag.INSUFFICIENT_WARMUP not in reason_flags:
                reason_flags.append(ReasonFlag.INSUFFICIENT_WARMUP)

        # Check volume
        if not volume_present:
            reason_flags.append(ReasonFlag.NO_VOLUME)

        # Check data lag
        if data_lag_seconds > lag_max_seconds:
            reason_flags.append(ReasonFlag.STALE_DATA)

        # Check feature completeness (if provided)
        if feature_bars is not None and feature_bars < valid_bars * 0.9:
            reason_flags.append(ReasonFlag.MISSING_METRIC_INPUT)

        # Determine eligibility
        eligible = (
            fill_rate >= fill_min
            and gap_rate <= gap_max
            and valid_bars >= warmup_min
            and volume_present
            and data_lag_seconds <= lag_max_seconds
        )

        # Calculate quality score
        quality_score = self._calculate_quality_score(
            fill_rate, gap_rate, fill_min, gap_max
        )

        return QualityResult(
            symbol=symbol,
            timeframe=timeframe,
            fill_rate=fill_rate,
            gap_rate=gap_rate,
            data_lag_seconds=data_lag_seconds,
            valid_bars=valid_bars,
            expected_bars=expected_bars,
            eligible=eligible,
            quality_score=quality_score,
            reason_flags=reason_flags,
            volume_present=volume_present,
            feature_bars=feature_bars or valid_bars,
        )

    def _calculate_quality_score(
        self,
        fill_rate: float,
        gap_rate: float,
        fill_min: float,
        gap_max: float,
    ) -> float:
        """
        Calculate quality score from fill and gap rates.

        Formula:
            quality_score = clamp((fill_rate - fill_min)/(1 - fill_min), 0, 1) *
                           clamp(1 - gap_rate/gap_max, 0, 1)
        """
        # Fill component: how much above minimum
        if fill_min >= 1.0:
            fill_component = 1.0 if fill_rate >= 1.0 else 0.0
        else:
            fill_component = max(0.0, min(1.0, (fill_rate - fill_min) / (1.0 - fill_min)))

        # Gap component: how much below maximum
        if gap_max <= 0:
            gap_component = 1.0 if gap_rate <= 0 else 0.0
        else:
            gap_component = max(0.0, min(1.0, 1.0 - gap_rate / gap_max))

        return fill_component * gap_component

    def calculate_expected_bars(self, timeframe: str, window_days: int) -> int:
        """Calculate expected number of bars for a TF and window."""
        tf_bar_ms = self.config.get_tf_bar_ms(timeframe)
        window_ms = window_days * 24 * 60 * 60 * 1000
        return window_ms // tf_bar_ms

    def detect_gaps(
        self,
        timestamps: list[int],
        timeframe: str,
    ) -> int:
        """
        Count gaps in timestamp sequence.

        A gap is when delta_t > gap_threshold_multiplier * tf_bar_ms

        Args:
            timestamps: List of timestamps in milliseconds, sorted ascending
            timeframe: Candle timeframe

        Returns:
            Number of gaps detected
        """
        if len(timestamps) < 2:
            return 0

        tf_bar_ms = self.config.get_tf_bar_ms(timeframe)
        gap_threshold = tf_bar_ms * self.config.gap_threshold_multiplier

        gaps_count = 0
        for i in range(1, len(timestamps)):
            delta = timestamps[i] - timestamps[i - 1]
            if delta > gap_threshold:
                gaps_count += 1

        return gaps_count

    def batch_evaluate(
        self,
        quality_data: list[dict],
    ) -> list[QualityResult]:
        """
        Evaluate quality for multiple (symbol, timeframe) pairs.

        Args:
            quality_data: List of dicts with keys:
                - symbol, timeframe, valid_bars, expected_bars,
                - gaps_count, data_lag_seconds, volume_present, feature_bars

        Returns:
            List of QualityResult objects
        """
        results = []
        for item in quality_data:
            result = self.evaluate(
                symbol=item["symbol"],
                timeframe=item["timeframe"],
                valid_bars=item["valid_bars"],
                expected_bars=item["expected_bars"],
                gaps_count=item["gaps_count"],
                data_lag_seconds=item["data_lag_seconds"],
                volume_present=item.get("volume_present", True),
                feature_bars=item.get("feature_bars"),
            )
            results.append(result)
        return results

    def summarize_results(
        self,
        results: list[QualityResult],
    ) -> dict:
        """Generate summary statistics for quality gate results."""
        if not results:
            return {"total": 0, "eligible": 0, "ineligible": 0}

        eligible_count = sum(1 for r in results if r.eligible)
        ineligible_count = len(results) - eligible_count

        # Count reasons
        reason_counts: dict[str, int] = {}
        for result in results:
            for flag in result.reason_flags:
                reason_counts[flag.value] = reason_counts.get(flag.value, 0) + 1

        # Average quality score (eligible only)
        eligible_results = [r for r in results if r.eligible]
        avg_quality = (
            sum(r.quality_score for r in eligible_results) / len(eligible_results)
            if eligible_results
            else 0.0
        )

        return {
            "total": len(results),
            "eligible": eligible_count,
            "ineligible": ineligible_count,
            "avg_quality_score": round(avg_quality, 4),
            "reason_counts": reason_counts,
        }
