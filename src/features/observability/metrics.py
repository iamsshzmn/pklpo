"""
Metrics module for features calculation.

This module implements specific metrics as specified in the plan:
- features.rows_written
- fill_rate.<group>
- rows_last_24h
- upsert_failures

REFACTORED (Stage 1): Thread-safe metrics using threading.local().
Each thread/async task gets its own metrics context.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from logging import Logger
from typing import Any

import numpy as np
import pandas as pd

from ..specs import PHASE_2_REQUIRED_FEATURES
from .logging import get_features_logger

logger = get_features_logger("features.metrics")

# Thread-local storage for metrics isolation
_thread_local = threading.local()


@dataclass
class FeatureMetrics:
    """Container for feature calculation metrics."""

    # Core metrics from plan
    rows_written: int = 0
    rows_last_24h: int = 0
    upsert_failures: int = 0

    # Fill rate metrics by group
    fill_rates: dict[str, float] = field(default_factory=dict)

    # Additional metrics
    calculation_time_ms: float = 0.0
    feature_count: int = 0
    symbol: str = ""
    timeframe: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Quality metrics
    nan_ratio: float = 0.0
    outlier_ratio: float = 0.0
    data_quality_score: float = 1.0


class MetricsCollector:
    """
    Collects and manages feature calculation metrics.

    REFACTORED (Stage 1): Thread-safe implementation using threading.local().
    Each thread/async task gets isolated metrics context, preventing
    race conditions during parallel execution.
    """

    def __init__(self):
        self.logger = get_features_logger("features.metrics")
        # Shared history with lock for thread-safe access
        self._metrics_history: list[FeatureMetrics] = []
        self._history_lock = threading.Lock()

    def _get_thread_context(self) -> dict[str, Any]:
        """Get or create thread-local context."""
        if not hasattr(_thread_local, "metrics_context"):
            _thread_local.metrics_context = {
                "current_metrics": None,
                "start_time": None,
            }
        # Cast to satisfy type checker (threading.local attributes are Any)
        context = _thread_local.metrics_context
        assert isinstance(context, dict)
        return context

    @property
    def _current_metrics(self) -> FeatureMetrics | None:
        """Get current metrics from thread-local storage."""
        return self._get_thread_context().get("current_metrics")

    @_current_metrics.setter
    def _current_metrics(self, value: FeatureMetrics | None) -> None:
        """Set current metrics in thread-local storage."""
        self._get_thread_context()["current_metrics"] = value

    @property
    def _start_time(self) -> float | None:
        """Get start time from thread-local storage."""
        return self._get_thread_context().get("start_time")

    @_start_time.setter
    def _start_time(self, value: float | None) -> None:
        """Set start time in thread-local storage."""
        self._get_thread_context()["start_time"] = value

    def start_calculation(
        self, symbol: str, timeframe: str, feature_count: int
    ) -> None:
        """Start tracking a new calculation (thread-safe)."""
        self._current_metrics = FeatureMetrics(
            symbol=symbol, timeframe=timeframe, feature_count=feature_count
        )
        self._start_time = time.time()
        self.logger.info(f"Started metrics collection for {symbol} {timeframe}")

    def record_rows_written(self, count: int) -> None:
        """Record number of rows written to database."""
        if self._current_metrics:
            self._current_metrics.rows_written = count
            self.logger.debug(f"Recorded {count} rows written")

    def record_rows_last_24h(self, count: int) -> None:
        """Record number of rows in last 24 hours."""
        if self._current_metrics:
            self._current_metrics.rows_last_24h = count
            self.logger.debug(f"Recorded {count} rows in last 24h")

    def record_upsert_failure(self) -> None:
        """Record an upsert failure."""
        if self._current_metrics:
            self._current_metrics.upsert_failures += 1
            self.logger.warning(
                f"Recorded upsert failure (total: {self._current_metrics.upsert_failures})"
            )

    def record_fill_rate(self, group_name: str, fill_rate: float) -> None:
        """Record fill rate for a feature group."""
        if self._current_metrics:
            self._current_metrics.fill_rates[group_name] = fill_rate
            self.logger.debug(f"Recorded fill rate for {group_name}: {fill_rate:.2%}")

    def record_quality_metrics(
        self, nan_ratio: float, outlier_ratio: float, quality_score: float
    ) -> None:
        """Record data quality metrics."""
        if self._current_metrics:
            self._current_metrics.nan_ratio = nan_ratio
            self._current_metrics.outlier_ratio = outlier_ratio
            self._current_metrics.data_quality_score = quality_score
            self.logger.debug(
                f"Recorded quality metrics: nan_ratio={nan_ratio:.2%}, outlier_ratio={outlier_ratio:.2%}, score={quality_score:.2f}"
            )

    def finish_calculation(self) -> FeatureMetrics | None:
        """
        Finish tracking and return final metrics (thread-safe).

        REFACTORED: Returns None instead of raising if no active calculation.
        This prevents errors during parallel execution.
        """
        current = self._current_metrics
        start = self._start_time

        if not current or start is None:
            self.logger.warning(
                "finish_calculation called but no active calculation in this thread"
            )
            return None

        # Calculate total time
        current.calculation_time_ms = (time.time() - start) * 1000

        # Store in history (thread-safe)
        with self._history_lock:
            self._metrics_history.append(current)

        # Log final metrics
        self._log_final_metrics(current)

        # Reset thread-local state
        self._current_metrics = None
        self._start_time = None

        return current

    def _log_final_metrics(self, metrics: FeatureMetrics) -> None:
        """Log final metrics in the format specified by plan."""
        self.logger.info(f"METRICS: {metrics.symbol} {metrics.timeframe}")
        self.logger.info(f"  features.rows_written: {metrics.rows_written}")
        self.logger.info(f"  rows_last_24h: {metrics.rows_last_24h}")
        self.logger.info(f"  upsert_failures: {metrics.upsert_failures}")
        self.logger.info(f"  calculation_time_ms: {metrics.calculation_time_ms:.1f}")

        # Log fill rates by group
        for group_name, fill_rate in metrics.fill_rates.items():
            self.logger.info(f"  fill_rate.{group_name}: {fill_rate:.2%}")

        # Log quality metrics
        self.logger.info(f"  data_quality_score: {metrics.data_quality_score:.2f}")
        self.logger.info(f"  nan_ratio: {metrics.nan_ratio:.2%}")
        self.logger.info(f"  outlier_ratio: {metrics.outlier_ratio:.2%}")

    def get_recent_metrics(self, count: int = 10) -> list[FeatureMetrics]:
        """Get recent metrics history (thread-safe)."""
        with self._history_lock:
            return self._metrics_history[-count:] if self._metrics_history else []

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get summary statistics from metrics history (thread-safe)."""
        with self._history_lock:
            if not self._metrics_history:
                return {"error": "No metrics history available"}

            recent_metrics = self._metrics_history[-10:]  # Last 10 calculations

        return {
            "total_calculations": len(self._metrics_history),
            "recent_calculations": len(recent_metrics),
            "avg_rows_written": sum(m.rows_written for m in recent_metrics)
            / len(recent_metrics),
            "avg_calculation_time_ms": sum(
                m.calculation_time_ms for m in recent_metrics
            )
            / len(recent_metrics),
            "total_upsert_failures": sum(m.upsert_failures for m in recent_metrics),
            "avg_data_quality_score": sum(m.data_quality_score for m in recent_metrics)
            / len(recent_metrics),
            "symbols_processed": list({m.symbol for m in recent_metrics}),
            "timeframes_processed": list({m.timeframe for m in recent_metrics}),
        }

    def has_active_calculation(self) -> bool:
        """Check if there's an active calculation in current thread."""
        return self._current_metrics is not None


# Global metrics collector instance
_legacy_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return _legacy_metrics_collector


def start_calculation_metrics(symbol: str, timeframe: str, feature_count: int) -> None:
    """Start tracking metrics for a calculation."""
    _legacy_metrics_collector.start_calculation(symbol, timeframe, feature_count)


def record_rows_written(count: int) -> None:
    """Record number of rows written."""
    _legacy_metrics_collector.record_rows_written(count)


def record_rows_last_24h(count: int) -> None:
    """Record number of rows in last 24 hours."""
    _legacy_metrics_collector.record_rows_last_24h(count)


def record_upsert_failure() -> None:
    """Record an upsert failure."""
    _legacy_metrics_collector.record_upsert_failure()


def record_fill_rate(group_name: str, fill_rate: float) -> None:
    """Record fill rate for a feature group."""
    _legacy_metrics_collector.record_fill_rate(group_name, fill_rate)


@dataclass
class FeatureQualityMetrics:
    """Quality metrics for a single feature column."""

    feature_name: str
    fill_rate: float
    non_null_count: int
    total_count: int
    has_constant_values: bool
    has_infinite_values: bool
    has_negative_values: bool
    min_value: float | None
    max_value: float | None
    mean_value: float | None
    std_value: float | None


@dataclass
class BatchMetrics:
    """Metrics describing batch processing."""

    batch_size: int
    processed_count: int
    error_count: int
    success_rate: float
    duration_seconds: float
    features_calculated: int
    features_failed: int


@dataclass
class Phase2ComplianceMetrics:
    """Metrics describing Phase 2 compliance."""

    required_features: list[str]
    present_features: list[str]
    missing_features: list[str]
    compliance_rate: float
    fill_rates: dict[str, float]


FEATURE_GROUP_DEFINITIONS: dict[str, set[str]] = {
    "moving_averages": {
        "ema_8",
        "ema_12",
        "ema_21",
        "ema_26",
        "ema_50",
        "ema_200",
        "sma_10",
        "sma_20",
        "sma_34",
        "sma_50",
        "sma_200",
    },
    "oscillators": {
        "rsi_14",
        "stochrsi_k",
        "stochrsi_d",
        "willr",
        "cci",
        "ultosc",
    },
    "volatility": {"atr_14", "bb_upper", "bb_lower", "bb_width"},
    "volume": {"obv", "vwap"},
    "macd": {"macd", "macd_signal", "macd_histogram"},
}


class _MetricsLoggerAdapter:
    """Provide a logger with log_metrics helper used in tests."""

    def __init__(self, logger: Logger):
        self._logger = logger

    def __getattr__(self, item: str) -> Any:
        return getattr(self._logger, item)

    def log_metrics(self, message: str, payload: Any | None = None) -> None:
        if payload is None:
            self._logger.info("METRICS %s", message)
        else:
            self._logger.info("METRICS %s %s", message, payload)


class FeaturesMetricsCollector:
    """High-level metrics collector used in tests/documentation."""

    def __init__(self):
        self.logger = _MetricsLoggerAdapter(
            get_features_logger("features.metrics.report")
        )
        self.metrics_history: list[dict[str, Any]] = []

    @staticmethod
    def _safe_std(series: pd.Series) -> float | None:
        std_value = series.std()
        return float(std_value) if pd.notna(std_value) else None

    @staticmethod
    def _fill_rate(series: pd.Series) -> float:
        total = len(series)
        if total == 0:
            return 0.0
        return round(float(series.notna().sum()) / total * 100.0, 2)

    def collect_feature_quality(
        self, df: pd.DataFrame, feature_name: str
    ) -> FeatureQualityMetrics:
        total_count = len(df)
        if feature_name not in df.columns:
            self.logger.warning("Feature %s not found in DataFrame", feature_name)
            return FeatureQualityMetrics(
                feature_name=feature_name,
                fill_rate=0.0,
                non_null_count=0,
                total_count=total_count,
                has_constant_values=False,
                has_infinite_values=False,
                has_negative_values=False,
                min_value=None,
                max_value=None,
                mean_value=None,
                std_value=None,
            )

        series = df[feature_name]
        non_null = int(series.notna().sum())
        fill_rate = self._fill_rate(series)
        finite_series = series.replace([np.inf, -np.inf], pd.NA).dropna()
        has_constant = bool(finite_series.nunique() <= 1) if non_null else False
        has_infinite = bool(np.isinf(series.dropna()).any())
        has_negative = bool((series.dropna() < 0).any())
        min_value = float(series.min()) if non_null else None
        max_value = float(series.max()) if non_null else None
        mean_value = float(series.mean()) if non_null else None
        std_value = self._safe_std(series.dropna())

        if has_constant:
            self.logger.warning("Feature %s has constant values", feature_name)
        if has_infinite:
            self.logger.warning("Feature %s has infinite values", feature_name)

        return FeatureQualityMetrics(
            feature_name=feature_name,
            fill_rate=fill_rate,
            non_null_count=non_null,
            total_count=total_count,
            has_constant_values=has_constant,
            has_infinite_values=has_infinite,
            has_negative_values=has_negative,
            min_value=min_value,
            max_value=max_value,
            mean_value=mean_value,
            std_value=std_value,
        )

    def collect_batch_metrics(
        self,
        batch_size: int,
        processed_count: int,
        error_count: int,
        duration_seconds: float,
        features_calculated: int,
        features_failed: int,
    ) -> BatchMetrics:
        success_count = max(processed_count - error_count, 0)
        success_rate = (success_count / batch_size * 100) if batch_size else 0.0
        metrics = BatchMetrics(
            batch_size=batch_size,
            processed_count=processed_count,
            error_count=error_count,
            success_rate=round(success_rate, 2),
            duration_seconds=duration_seconds,
            features_calculated=features_calculated,
            features_failed=features_failed,
        )

        self.logger.log_metrics("batch_processing", asdict(metrics))
        if error_count > 0:
            self.logger.warning(
                "Batch processing completed with %s errors", error_count
            )
        return metrics

    def collect_phase2_compliance(self, df: pd.DataFrame) -> Phase2ComplianceMetrics:
        required = list(PHASE_2_REQUIRED_FEATURES)
        present = [f for f in required if f in df.columns]
        missing = [f for f in required if f not in present]
        fill_rates = {f: self._fill_rate(df[f]) for f in present}
        compliance_rate = len(present) / len(required) * 100 if required else 100.0

        if missing:
            self.logger.warning(
                "Missing Phase 2 features: %s", ", ".join(sorted(missing))
            )

        return Phase2ComplianceMetrics(
            required_features=required,
            present_features=present,
            missing_features=missing,
            compliance_rate=round(compliance_rate, 2),
            fill_rates=fill_rates,
        )

    def collect_feature_group_metrics(self, df: pd.DataFrame) -> dict[str, Any]:
        groups: dict[str, Any] = {}
        for group_name, feature_set in FEATURE_GROUP_DEFINITIONS.items():
            present = [feature for feature in feature_set if feature in df.columns]
            if not present:
                continue
            fill_rates = [self._fill_rate(df[feature]) for feature in present]
            avg_fill_rate = sum(fill_rates) / len(fill_rates) if fill_rates else 0.0
            groups[group_name] = {
                "feature_count": len(present),
                "avg_fill_rate": round(avg_fill_rate, 2),
                "features": present,
            }

        self.logger.log_metrics("feature_groups", groups)
        return groups

    def generate_summary_report(
        self,
        feature_metrics: list[FeatureQualityMetrics],
        batch_metrics: BatchMetrics | None,
        phase2_metrics: Phase2ComplianceMetrics | None,
        group_metrics: dict[str, Any] | None,
    ) -> dict[str, Any]:
        problematic = [
            m.feature_name
            for m in feature_metrics
            if m.fill_rate < 80 or m.has_constant_values or m.has_infinite_values
        ]
        overview = {
            "total_features": len(feature_metrics),
            "features_with_issues": len(problematic),
            "avg_fill_rate": (
                round(
                    sum(m.fill_rate for m in feature_metrics) / len(feature_metrics), 2
                )
                if feature_metrics
                else 0.0
            ),
            "problematic_features": problematic,
        }

        summary = {
            "timestamp": datetime.now(UTC).isoformat(),
            "overview": overview,
            "batch_processing": asdict(batch_metrics) if batch_metrics else None,
            "phase2_compliance": asdict(phase2_metrics) if phase2_metrics else None,
            "feature_groups": group_metrics or {},
            "individual_features": [asdict(m) for m in feature_metrics],
        }

        self.metrics_history.append(summary)
        self.logger.info("Generated features summary report")
        return summary

    def export_metrics(self, file_path: str, fmt: str = "json") -> None:
        if not self.metrics_history:
            self.logger.warning("No metrics history to export")
            return

        if fmt.lower() == "json":
            with open(file_path, "w") as fp:
                json.dump(self.metrics_history, fp, ensure_ascii=False, indent=2)
            return

        if fmt.lower() == "csv":
            df_history = pd.DataFrame(self.metrics_history)
            df_history.to_csv(file_path, index=False)
            return

        raise ValueError(f"Unsupported export format: {fmt}")


# Public collector instance used in tests and demos
metrics_collector = FeaturesMetricsCollector()


def record_quality_metrics(
    nan_ratio: float, outlier_ratio: float, quality_score: float
) -> None:
    """Record data quality metrics."""
    _legacy_metrics_collector.record_quality_metrics(
        nan_ratio, outlier_ratio, quality_score
    )


def finish_calculation_metrics() -> FeatureMetrics | None:
    """
    Finish tracking and return final metrics.

    REFACTORED (Stage 1): Returns None if no active calculation,
    instead of raising ValueError. Safe for parallel execution.
    """
    return _legacy_metrics_collector.finish_calculation()


def get_metrics_summary() -> dict[str, Any]:
    """Get metrics summary."""
    return _legacy_metrics_collector.get_metrics_summary()


def calculate_fill_rates(
    df: pd.DataFrame, feature_groups: dict[str, list[str]]
) -> dict[str, float]:
    """
    Calculate fill rates for feature groups.

    Args:
        df: DataFrame with features
        feature_groups: Dictionary mapping group names to feature lists

    Returns:
        Dictionary mapping group names to fill rates
    """
    fill_rates = {}

    for group_name, features in feature_groups.items():
        # Filter features that exist in DataFrame
        existing_features = [f for f in features if f in df.columns]

        if not existing_features:
            fill_rates[group_name] = 0.0
            continue

        # Calculate average fill rate for the group
        group_df = df[existing_features]
        non_null_counts = group_df.notna().sum()
        total_count = len(group_df)
        group_fill_rates = non_null_counts / total_count
        avg_fill_rate = group_fill_rates.mean()

        fill_rates[group_name] = avg_fill_rate

    return fill_rates


def calculate_quality_score(df: pd.DataFrame) -> tuple[float, float, float]:
    """
    Calculate data quality score.

    Args:
        df: DataFrame with features

    Returns:
        Tuple of (nan_ratio, outlier_ratio, quality_score)
    """
    # Exclude OHLCV and timestamp columns
    exclude_cols = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "ts",
        "timestamp",
        "symbol",
        "timeframe",
        "calculated_at",
        "data_quality_status",
        "data_status",
        "failed_groups",
    ]
    feature_cols = [col for col in df.columns if col not in exclude_cols]

    if not feature_cols:
        return 1.0, 0.0, 0.0

    # Work strictly with numeric columns to avoid dtype-related failures.
    feature_df = df[feature_cols].select_dtypes(include=["number"])
    numeric_cols = list(feature_df.columns)

    # Calculate NaN ratio
    total_cells = len(feature_df) * len(numeric_cols)
    nan_cells = feature_df.isna().sum().sum()
    nan_ratio = nan_cells / total_cells if total_cells > 0 else 1.0

    # Calculate outlier ratio.
    # Robust logic:
    # - coerce values to numeric;
    # - ignore inf/-inf and NA in IQR calculation;
    # - skip problematic columns instead of failing the whole symbol/timeframe.
    outlier_count = 0
    skipped_columns: list[str] = []
    for col in numeric_cols:
        try:
            series = pd.to_numeric(feature_df[col], errors="coerce")
            series = series.replace([np.inf, -np.inf], np.nan).dropna()
            if series.empty:
                continue

            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1
            if not (pd.notna(IQR) and np.isfinite(IQR) and IQR > 0):
                continue

            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            outlier_mask = (series < lower_bound) | (series > upper_bound)
            outlier_count += int(outlier_mask.sum())
        except Exception:
            skipped_columns.append(col)
            continue

    if skipped_columns:
        logger.warning(
            "Skipped %d columns during outlier calculation due to invalid data: %s",
            len(skipped_columns),
            ", ".join(skipped_columns[:10]),
        )

    outlier_ratio = outlier_count / total_cells if total_cells > 0 else 0.0

    # Calculate quality score (0.0 = worst, 1.0 = best)
    quality_score = max(0.0, 1.0 - nan_ratio - outlier_ratio)

    return nan_ratio, outlier_ratio, quality_score


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    # Add parent directory to path for imports
    sys.path.append(str(Path(__file__).parent.parent.parent))

    parser = argparse.ArgumentParser(description="Feature metrics")
    parser.add_argument(
        "--show-summary", action="store_true", help="Show metrics summary"
    )
    parser.add_argument(
        "--show-recent", type=int, default=5, help="Show recent metrics"
    )

    args = parser.parse_args()

    collector = get_metrics_collector()

    if args.show_summary:
        summary = collector.get_metrics_summary()
        print("Metrics Summary:")
        for key, value in summary.items():
            print(f"  {key}: {value}")

    if args.show_recent:
        recent = collector.get_recent_metrics(args.show_recent)
        print(f"\nRecent Metrics ({len(recent)} calculations):")
        for i, metrics in enumerate(recent):
            print(f"  {i+1}. {metrics.symbol} {metrics.timeframe}")
            print(f"     rows_written: {metrics.rows_written}")
            print(f"     calculation_time_ms: {metrics.calculation_time_ms:.1f}")
            print(f"     data_quality_score: {metrics.data_quality_score:.2f}")
