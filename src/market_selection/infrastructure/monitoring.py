"""
Monitoring and Metrics for Market Selection

Provides Prometheus-compatible metrics for:
- Pipeline execution (runs, duration, success/failure)
- Universe statistics (size, regime distribution)
- Quality gate metrics (eligible counts per TF)
- Scoring distributions

Metrics are exposed via:
1. In-memory collector for Airflow/CLI use
2. Optional Prometheus HTTP endpoint (if prometheus_client installed)
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# Try to import prometheus_client, fall back to no-op if not available
try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = None
    Gauge = None
    Histogram = None


@dataclass
class PipelineMetrics:
    """Metrics from a single pipeline run."""

    ts_version: int
    ts_eval: int
    success: bool
    status: str
    universe_size: int
    execution_time_seconds: float

    # Regime
    global_regime: str | None = None
    regime_strength: float = 0.0
    regime_stale: bool = False

    # Quality gate
    eligible_counts: dict[str, int] = field(default_factory=dict)
    total_symbols: int = 0

    # Scoring
    score_min: float = 0.0
    score_max: float = 1.0
    score_mean: float = 0.5
    score_std: float = 0.0

    # Errors
    error_message: str | None = None
    reason_flags: list[str] = field(default_factory=list)

    # Timestamp
    recorded_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "ts_version": self.ts_version,
            "ts_eval": self.ts_eval,
            "success": self.success,
            "status": self.status,
            "universe_size": self.universe_size,
            "execution_time_seconds": self.execution_time_seconds,
            "global_regime": self.global_regime,
            "regime_strength": self.regime_strength,
            "regime_stale": self.regime_stale,
            "eligible_counts": self.eligible_counts,
            "total_symbols": self.total_symbols,
            "score_min": self.score_min,
            "score_max": self.score_max,
            "score_mean": self.score_mean,
            "score_std": self.score_std,
            "error_message": self.error_message,
            "reason_flags": self.reason_flags,
            "recorded_at": self.recorded_at,
        }


class MarketSelectionMetrics:
    """
    Metrics collector for market selection pipeline.

    Supports two modes:
    1. In-memory collection (always available)
    2. Prometheus metrics (if prometheus_client installed)
    """

    def __init__(self, enable_prometheus: bool = False, prometheus_port: int = 9101):
        self._history: list[PipelineMetrics] = []
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)

        self._prometheus_enabled = enable_prometheus and PROMETHEUS_AVAILABLE

        if self._prometheus_enabled:
            self._init_prometheus_metrics(prometheus_port)
        elif enable_prometheus and not PROMETHEUS_AVAILABLE:
            logger.warning(
                "prometheus_client not installed. "
                "Install with: pip install prometheus_client"
            )

    def _init_prometheus_metrics(self, port: int) -> None:
        """Initialize Prometheus metrics."""
        # Counters
        self._prom_runs_total = Counter(
            "market_selection_runs_total",
            "Total number of market selection pipeline runs",
            ["status"],
        )
        self._prom_errors_total = Counter(
            "market_selection_errors_total",
            "Total number of pipeline errors",
            ["error_type"],
        )

        # Gauges
        self._prom_universe_size = Gauge(
            "market_selection_universe_size",
            "Current universe size",
        )
        self._prom_regime = Gauge(
            "market_selection_regime",
            "Current global regime (encoded)",
            ["regime"],
        )
        self._prom_eligible_count = Gauge(
            "market_selection_eligible_count",
            "Number of eligible symbols",
            ["timeframe"],
        )
        self._prom_last_run_time = Gauge(
            "market_selection_last_run_timestamp",
            "Timestamp of last successful run",
        )

        # Histograms
        self._prom_duration = Histogram(
            "market_selection_duration_seconds",
            "Pipeline execution duration",
            buckets=(1, 5, 10, 30, 60, 120, 300, 600),
        )
        self._prom_score = Histogram(
            "market_selection_score",
            "Final score distribution",
            buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
        )

        # Start HTTP server
        try:
            start_http_server(port)
            logger.info(f"Prometheus metrics server started on port {port}")
        except Exception as e:
            logger.error(f"Failed to start Prometheus server: {e}")

    def record_pipeline_run(self, metrics: PipelineMetrics) -> None:
        """Record metrics from a pipeline run."""
        self._history.append(metrics)

        # Update counters
        status_key = "success" if metrics.success else "failed"
        self._counters[f"runs_{status_key}"] += 1
        self._counters["runs_total"] += 1

        # Update gauges
        self._gauges["universe_size"] = metrics.universe_size
        self._gauges["last_execution_time"] = metrics.execution_time_seconds

        if metrics.global_regime:
            self._gauges["regime"] = self._encode_regime(metrics.global_regime)
            self._gauges[f"regime_{metrics.global_regime.lower()}"] = 1.0

        for tf, count in metrics.eligible_counts.items():
            self._gauges[f"eligible_{tf}"] = count

        # Update histograms
        self._histograms["execution_time"].append(metrics.execution_time_seconds)

        # Update Prometheus metrics if enabled
        if self._prometheus_enabled:
            self._update_prometheus(metrics)

        # Log summary
        logger.info(
            f"Pipeline metrics recorded: "
            f"success={metrics.success}, "
            f"universe_size={metrics.universe_size}, "
            f"regime={metrics.global_regime}, "
            f"duration={metrics.execution_time_seconds:.2f}s"
        )

    def _update_prometheus(self, metrics: PipelineMetrics) -> None:
        """Update Prometheus metrics."""
        status = "success" if metrics.success else "failed"
        self._prom_runs_total.labels(status=status).inc()

        if not metrics.success and metrics.error_message:
            error_type = metrics.reason_flags[0] if metrics.reason_flags else "unknown"
            self._prom_errors_total.labels(error_type=error_type).inc()

        self._prom_universe_size.set(metrics.universe_size)
        self._prom_duration.observe(metrics.execution_time_seconds)

        if metrics.global_regime:
            # Set current regime to 1, others to 0
            for regime in ["TREND_UP", "TREND_DOWN", "RANGE", "VOLATILE"]:
                value = 1 if regime == metrics.global_regime else 0
                self._prom_regime.labels(regime=regime).set(value)

        for tf, count in metrics.eligible_counts.items():
            self._prom_eligible_count.labels(timeframe=tf).set(count)

        if metrics.success:
            self._prom_last_run_time.set(time.time())

    def record_scores(self, scores: list[float]) -> None:
        """Record score distribution for histogram."""
        if not scores:
            return

        import statistics

        self._gauges["score_min"] = min(scores)
        self._gauges["score_max"] = max(scores)
        self._gauges["score_mean"] = statistics.mean(scores)
        self._gauges["score_std"] = statistics.stdev(scores) if len(scores) > 1 else 0.0

        self._histograms["scores"].extend(scores)

        if self._prometheus_enabled:
            for score in scores:
                self._prom_score.observe(score)

    def record_error(self, error_type: str, message: str) -> None:
        """Record an error."""
        self._counters[f"error_{error_type}"] += 1
        logger.error(f"Market selection error ({error_type}): {message}")

        if self._prometheus_enabled:
            self._prom_errors_total.labels(error_type=error_type).inc()

    @staticmethod
    def _encode_regime(regime: str) -> float:
        """Encode regime as numeric value for Gauge."""
        mapping = {
            "TREND_UP": 1.0,
            "TREND_DOWN": 2.0,
            "RANGE": 3.0,
            "VOLATILE": 4.0,
        }
        return mapping.get(regime, 0.0)

    def get_summary(self) -> dict[str, Any]:
        """Get metrics summary."""
        if not self._history:
            return {"error": "No metrics history"}

        recent = self._history[-10:]
        success_count = sum(1 for m in recent if m.success)

        return {
            "total_runs": self._counters["runs_total"],
            "success_runs": self._counters["runs_success"],
            "failed_runs": self._counters["runs_failed"],
            "success_rate": success_count / len(recent) if recent else 0.0,
            "current_universe_size": self._gauges.get("universe_size", 0),
            "last_execution_time": self._gauges.get("last_execution_time", 0),
            "avg_execution_time": (
                sum(self._histograms["execution_time"])
                / len(self._histograms["execution_time"])
                if self._histograms["execution_time"]
                else 0.0
            ),
            "recent_regimes": [m.global_regime for m in recent if m.global_regime],
            "prometheus_enabled": self._prometheus_enabled,
        }

    def get_recent_history(self, count: int = 10) -> list[dict[str, Any]]:
        """Get recent pipeline run history."""
        return [m.to_dict() for m in self._history[-count:]]

    def get_eligible_counts(self) -> dict[str, int]:
        """Get current eligible counts per TF."""
        return {
            k.replace("eligible_", ""): int(v)
            for k, v in self._gauges.items()
            if k.startswith("eligible_")
        }

    def get_regime_distribution(self, last_n: int = 24) -> dict[str, int]:
        """Get regime distribution over last N runs."""
        recent = self._history[-last_n:]
        distribution: dict[str, int] = defaultdict(int)

        for m in recent:
            if m.global_regime:
                distribution[m.global_regime] += 1

        return dict(distribution)

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        self._history.clear()
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()


# Global metrics instance
_metrics_instance: MarketSelectionMetrics | None = None


def get_metrics(
    enable_prometheus: bool = False,
    prometheus_port: int = 9101,
) -> MarketSelectionMetrics:
    """Get or create the global metrics instance."""
    global _metrics_instance

    if _metrics_instance is None:
        _metrics_instance = MarketSelectionMetrics(
            enable_prometheus=enable_prometheus,
            prometheus_port=prometheus_port,
        )

    return _metrics_instance


def record_pipeline_metrics(
    ts_version: int,
    ts_eval: int,
    success: bool,
    status: str,
    universe_size: int,
    execution_time_seconds: float,
    global_regime: str | None = None,
    regime_strength: float = 0.0,
    regime_stale: bool = False,
    eligible_counts: dict[str, int] | None = None,
    total_symbols: int = 0,
    error_message: str | None = None,
    reason_flags: list[str] | None = None,
) -> None:
    """Convenience function to record pipeline metrics."""
    metrics = PipelineMetrics(
        ts_version=ts_version,
        ts_eval=ts_eval,
        success=success,
        status=status,
        universe_size=universe_size,
        execution_time_seconds=execution_time_seconds,
        global_regime=global_regime,
        regime_strength=regime_strength,
        regime_stale=regime_stale,
        eligible_counts=eligible_counts or {},
        total_symbols=total_symbols,
        error_message=error_message,
        reason_flags=reason_flags or [],
    )

    get_metrics().record_pipeline_run(metrics)


class MarketSelectionMonitoring:
    """Adapter exposing monitoring through an application port."""

    def record_error(self, error_type: str, message: str) -> None:
        get_metrics().record_error(error_type, message)

    def record_pipeline_metrics(
        self,
        *,
        ts_version: int,
        ts_eval: int,
        success: bool,
        status: str,
        universe_size: int,
        execution_time_seconds: float,
        global_regime: str | None = None,
        regime_strength: float = 0.0,
        regime_stale: bool = False,
        eligible_counts: dict[str, int] | None = None,
        total_symbols: int = 0,
        error_message: str | None = None,
        reason_flags: list[str] | None = None,
    ) -> None:
        record_pipeline_metrics(
            ts_version=ts_version,
            ts_eval=ts_eval,
            success=success,
            status=status,
            universe_size=universe_size,
            execution_time_seconds=execution_time_seconds,
            global_regime=global_regime,
            regime_strength=regime_strength,
            regime_stale=regime_stale,
            eligible_counts=eligible_counts,
            total_symbols=total_symbols,
            error_message=error_message,
            reason_flags=reason_flags,
        )


class MarketSelectionPushMonitoring:
    """``MonitoringPort`` adapter that pushes metrics to Pushgateway.

    This is the production adapter for Airflow DAG runs.  It replaces the
    ``start_http_server`` pull pattern with a fire-and-forget push on each
    pipeline completion, consistent with how every other in-loop DAG delivers
    metrics (``push_swap_sync_metrics``, ``push_swap_repair_metrics``, …).

    ``record_error`` logs only; error counts surface through the ERROR-level
    logs already captured by Loki (and the ``level="ERROR"`` fallback on the
    Error Events panel added in T6.4).
    """

    def record_error(self, error_type: str, message: str) -> None:
        logger.error("Market selection error (%s): %s", error_type, message)

    def record_pipeline_metrics(
        self,
        *,
        ts_version: int,
        ts_eval: int,
        success: bool,
        status: str,
        universe_size: int,
        execution_time_seconds: float,
        global_regime: str | None = None,
        regime_strength: float = 0.0,
        regime_stale: bool = False,
        eligible_counts: dict[str, int] | None = None,
        total_symbols: int = 0,
        error_message: str | None = None,
        reason_flags: list[str] | None = None,
    ) -> None:
        metrics = PipelineMetrics(
            ts_version=ts_version,
            ts_eval=ts_eval,
            success=success,
            status=status,
            universe_size=universe_size,
            execution_time_seconds=execution_time_seconds,
            global_regime=global_regime,
            regime_strength=regime_strength,
            regime_stale=regime_stale,
            eligible_counts=eligible_counts or {},
            total_symbols=total_symbols,
            error_message=error_message,
            reason_flags=reason_flags or [],
        )
        from src.pklpo_platform.observability.metrics import (
            push_market_selection_metrics,
        )

        push_market_selection_metrics(metrics.to_dict())
