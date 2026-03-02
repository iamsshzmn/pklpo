"""
Prometheus metrics exporter for features pipeline.

Provides counters, gauges, and histograms for data quality monitoring.
Uses Pushgateway for batch job metrics (Airflow tasks don't serve HTTP).

Graceful degradation: if prometheus-client is not installed or Pushgateway
is unavailable, all operations are no-ops with warnings.

Usage:
    from src.features.observability.prometheus import get_metrics

    metrics = get_metrics()
    metrics.record_rows_written("BTC-USDT-SWAP", "1m", 1500)
    metrics.record_freshness_lag("BTC-USDT-SWAP", "1m", 45.2)
    metrics.observe_calc_duration("BTC-USDT-SWAP", "1m", 3.14)
    metrics.push()  # push to gateway (if configured)
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager

logger = logging.getLogger("features.observability.prometheus")

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        push_to_gateway,
    )

    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False

_LABEL_NAMES = ["symbol", "timeframe"]


class _NoOpMetric:
    """No-op stand-in when prometheus-client is not available."""

    def labels(self, *_args: str, **_kwargs: str) -> _NoOpMetric:
        return self

    def inc(self, amount: float = 1) -> None:
        pass

    def set(self, value: float) -> None:
        pass

    def observe(self, amount: float) -> None:
        pass


class PipelineMetrics:
    """Prometheus metrics for the features pipeline.

    All metric operations accept ``symbol`` and ``timeframe`` labels.
    If ``prometheus-client`` is not installed, every method is a silent no-op.
    """

    def __init__(self) -> None:
        self._registry: CollectorRegistry | None = None
        self._enabled = False
        self._pushgateway_url = ""
        self._job_name = "features_pipeline"
        self._prefix = "pklpo"

        if not _HAS_PROMETHEUS:
            logger.info(
                "prometheus-client not installed — metrics disabled"
            )
            self._init_noop()
            return

        self._init_from_settings()

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------

    def _init_from_settings(self) -> None:
        """Read config from Settings and create real or noop metrics."""
        try:
            from src.config import get_settings

            obs = get_settings().observability
            self._enabled = obs.prometheus_enabled
            self._pushgateway_url = obs.prometheus_pushgateway_url
            self._job_name = obs.job_name
            self._prefix = obs.metrics_prefix
        except Exception:
            logger.debug("Could not load ObservabilitySettings, using defaults")

        if not self._enabled:
            logger.debug("Prometheus metrics disabled via settings")
            self._init_noop()
            return

        self._registry = CollectorRegistry()
        self._create_metrics()
        logger.info("Prometheus metrics initialized (prefix=%s)", self._prefix)

    def _init_noop(self) -> None:
        noop = _NoOpMetric()
        # Counters
        self.rows_written_total = noop
        self.upsert_failures_total = noop
        self.duplicates_detected_total = noop
        # Gauges
        self.freshness_lag_seconds = noop
        self.fill_rate = noop
        self.hole_rate = noop
        self.quality_score = noop
        self.batch_size_current = noop
        # Histograms
        self.calc_duration_seconds = noop
        self.upsert_duration_seconds = noop
        self.batch_size_distribution = noop

    def _create_metrics(self) -> None:
        assert self._registry is not None
        p = self._prefix

        # --- Counters ---
        self.rows_written_total = Counter(
            f"{p}_features_rows_written_total",
            "Total indicator rows written to database",
            _LABEL_NAMES,
            registry=self._registry,
        )
        self.upsert_failures_total = Counter(
            f"{p}_upsert_failures_total",
            "Total UPSERT operation failures",
            _LABEL_NAMES,
            registry=self._registry,
        )
        self.duplicates_detected_total = Counter(
            f"{p}_duplicate_rows_detected_total",
            "Total duplicate rows detected and skipped",
            _LABEL_NAMES,
            registry=self._registry,
        )

        # --- Gauges ---
        self.freshness_lag_seconds = Gauge(
            f"{p}_data_freshness_lag_seconds",
            "Data freshness lag relative to expected bar close",
            _LABEL_NAMES,
            registry=self._registry,
        )
        self.fill_rate = Gauge(
            f"{p}_data_fill_rate",
            "Data fill rate (0.0-1.0)",
            _LABEL_NAMES,
            registry=self._registry,
        )
        self.hole_rate = Gauge(
            f"{p}_data_hole_rate",
            "Missing bars rate (0.0-1.0)",
            _LABEL_NAMES,
            registry=self._registry,
        )
        self.quality_score = Gauge(
            f"{p}_data_quality_score",
            "Composite data quality score (0.0-1.0)",
            _LABEL_NAMES,
            registry=self._registry,
        )
        self.batch_size_current = Gauge(
            f"{p}_batch_size_current",
            "Current UPSERT batch size",
            _LABEL_NAMES,
            registry=self._registry,
        )

        # --- Histograms ---
        self.calc_duration_seconds = Histogram(
            f"{p}_features_calculation_duration_seconds",
            "Time spent calculating features for one symbol/timeframe",
            _LABEL_NAMES,
            buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300),
            registry=self._registry,
        )
        self.upsert_duration_seconds = Histogram(
            f"{p}_upsert_duration_seconds",
            "Time spent on a single UPSERT batch",
            _LABEL_NAMES,
            buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
            registry=self._registry,
        )
        self.batch_size_distribution = Histogram(
            f"{p}_batch_size_distribution",
            "Distribution of UPSERT batch sizes",
            _LABEL_NAMES,
            buckets=(5, 10, 25, 50, 100, 150, 200),
            registry=self._registry,
        )

    # ------------------------------------------------------------------
    # Convenience recording helpers
    # ------------------------------------------------------------------

    def record_rows_written(
        self, symbol: str, timeframe: str, count: int
    ) -> None:
        self.rows_written_total.labels(symbol, timeframe).inc(count)

    def record_upsert_failure(self, symbol: str, timeframe: str) -> None:
        self.upsert_failures_total.labels(symbol, timeframe).inc()

    def record_duplicates(
        self, symbol: str, timeframe: str, count: int
    ) -> None:
        self.duplicates_detected_total.labels(symbol, timeframe).inc(count)

    def record_freshness_lag(
        self, symbol: str, timeframe: str, lag_seconds: float
    ) -> None:
        self.freshness_lag_seconds.labels(symbol, timeframe).set(lag_seconds)

    def record_fill_rate(
        self, symbol: str, timeframe: str, rate: float
    ) -> None:
        self.fill_rate.labels(symbol, timeframe).set(rate)

    def record_hole_rate(
        self, symbol: str, timeframe: str, rate: float
    ) -> None:
        self.hole_rate.labels(symbol, timeframe).set(rate)

    def record_quality_score(
        self, symbol: str, timeframe: str, score: float
    ) -> None:
        self.quality_score.labels(symbol, timeframe).set(score)

    def record_batch_size(
        self, symbol: str, timeframe: str, size: int
    ) -> None:
        self.batch_size_current.labels(symbol, timeframe).set(size)
        self.batch_size_distribution.labels(symbol, timeframe).observe(size)

    def observe_calc_duration(
        self, symbol: str, timeframe: str, duration_seconds: float
    ) -> None:
        self.calc_duration_seconds.labels(symbol, timeframe).observe(
            duration_seconds
        )

    def observe_upsert_duration(
        self, symbol: str, timeframe: str, duration_seconds: float
    ) -> None:
        self.upsert_duration_seconds.labels(symbol, timeframe).observe(
            duration_seconds
        )

    @contextmanager
    def calc_timer(
        self, symbol: str, timeframe: str
    ) -> Generator[None, None, None]:
        """Context manager that measures and records calculation duration."""
        start = time.monotonic()
        yield
        elapsed = time.monotonic() - start
        self.observe_calc_duration(symbol, timeframe, elapsed)

    @contextmanager
    def upsert_timer(
        self, symbol: str, timeframe: str
    ) -> Generator[None, None, None]:
        """Context manager that measures and records upsert duration."""
        start = time.monotonic()
        yield
        elapsed = time.monotonic() - start
        self.observe_upsert_duration(symbol, timeframe, elapsed)

    # ------------------------------------------------------------------
    # Push
    # ------------------------------------------------------------------

    def push(self) -> bool:
        """Push metrics to Pushgateway.

        Returns True on success, False on failure (logged as warning).
        Always safe to call — never raises.
        """
        if not self._enabled or self._registry is None:
            return False

        if not self._pushgateway_url:
            logger.debug("No pushgateway URL configured, skipping push")
            return False

        try:
            push_to_gateway(
                self._pushgateway_url,
                job=self._job_name,
                registry=self._registry,
            )
            logger.debug("Metrics pushed to %s", self._pushgateway_url)
            return True
        except Exception:
            logger.warning(
                "Failed to push metrics to %s", self._pushgateway_url,
                exc_info=True,
            )
            return False

    @property
    def enabled(self) -> bool:
        return self._enabled


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_instance: PipelineMetrics | None = None


def get_metrics() -> PipelineMetrics:
    """Return the singleton PipelineMetrics instance."""
    global _instance
    if _instance is None:
        _instance = PipelineMetrics()
    return _instance


def reset_metrics() -> None:
    """Reset the singleton (useful for tests)."""
    global _instance
    _instance = None
