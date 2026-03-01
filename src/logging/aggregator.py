"""Log aggregation for reducing log spam.

This module provides LogAggregator for collecting multiple log events
and emitting a single summary.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .config import should_log
from .levels import LogCategory, Verbosity

if TYPE_CHECKING:
    from logging import Logger

    from .logger import CategoryAdapter


@dataclass
class AggregatedMetric:
    """Single aggregated metric with statistics."""

    count: int = 0
    sum_value: float = 0.0
    min_value: float = float("inf")
    max_value: float = float("-inf")
    items: list[str] = field(default_factory=list)

    def add(self, value: float = 1.0, item: str | None = None) -> None:
        """Add a value to the metric."""
        self.count += 1
        self.sum_value += value
        self.min_value = min(self.min_value, value)
        self.max_value = max(self.max_value, value)
        if item:
            self.items.append(item)

    @property
    def avg(self) -> float:
        """Average value."""
        return self.sum_value / self.count if self.count > 0 else 0.0


class LogAggregator:
    """Aggregates multiple log events into a single summary.

    Use this to avoid log spam when processing many items.
    Instead of logging each item, collect metrics and emit a summary.

    Example:
        with LogAggregator(LogCategory.MERGE, "columns") as agg:
            for col in columns:
                result = process(col)
                agg.add("processed", col, fill_rate=result.fill_rate)
            if errors:
                agg.add_warning("skipped", reason)
        # Emits: [MERGE] columns: processed=26 (avg_fill=87.3%), skipped=2

    Args:
        category: Log category for the summary.
        operation: Operation name for the log message.
        logger: Optional logger instance. Uses category logger if not provided.
        min_verbosity: Minimum verbosity to emit summary (default: NORMAL).
    """

    def __init__(
        self,
        category: LogCategory,
        operation: str = "",
        logger: Logger | CategoryAdapter | None = None,
        min_verbosity: Verbosity = Verbosity.NORMAL,
    ) -> None:
        self.category = category
        self.operation = operation
        self._logger_override = logger
        self.min_verbosity = min_verbosity
        self.metrics: dict[str, AggregatedMetric] = {}
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.start_time = time.perf_counter()
        self._extra_info: dict[str, Any] = {}

    @property
    def logger(self) -> Logger | CategoryAdapter:
        """Get the logger, lazy-loading category logger if needed."""
        if self._logger_override is not None:
            return self._logger_override
        # Lazy import to avoid circular dependency
        from .logger import get_category_logger

        return get_category_logger(self.category)

    def add(
        self,
        metric_name: str,
        item: str | None = None,
        value: float = 1.0,
        **extra: Any,
    ) -> None:
        """Add an item to a named metric.

        Args:
            metric_name: Name of the metric (e.g., "processed", "skipped").
            item: Optional item identifier for detailed logging.
            value: Numeric value to aggregate (default 1.0 for counting).
            **extra: Extra key-value pairs to include in summary.
        """
        if metric_name not in self.metrics:
            self.metrics[metric_name] = AggregatedMetric()
        self.metrics[metric_name].add(value, item)
        self._extra_info.update(extra)

    def add_warning(self, message: str) -> None:
        """Add a warning to be included in summary."""
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        """Add an error to be included in summary."""
        self.errors.append(message)

    def set_extra(self, key: str, value: Any) -> None:
        """Set extra info to include in summary."""
        self._extra_info[key] = value

    @property
    def duration(self) -> float:
        """Get elapsed time since aggregator was created."""
        return time.perf_counter() - self.start_time

    def _build_summary(self) -> str:
        """Build the summary message."""
        parts = []

        if self.operation:
            parts.append(self.operation)

        # Add metrics
        metric_parts = []
        for name, metric in self.metrics.items():
            if metric.count > 0:
                avg_str = ""
                if metric.count > 1 and metric.sum_value != metric.count:
                    avg_str = f" (avg={metric.avg:.1f})"
                metric_parts.append(f"{name}={metric.count}{avg_str}")
        if metric_parts:
            parts.append(", ".join(metric_parts))

        # Add extra info
        if self._extra_info:
            extra_parts = [f"{k}={v}" for k, v in self._extra_info.items()]
            parts.append(", ".join(extra_parts))

        # Add duration
        if self.duration > 0.1:  # Only show if > 100ms
            parts.append(f"duration={self.duration:.2f}s")

        # Add warnings count
        if self.warnings:
            parts.append(f"warnings={len(self.warnings)}")

        return " | ".join(parts) if parts else "completed"

    def emit(self) -> None:
        """Emit the aggregated summary log."""
        if not should_log(self.category, self.min_verbosity):
            return

        summary = self._build_summary()
        self.logger.info(summary)

        # Log warnings at VERBOSE level
        if self.warnings and should_log(self.category, Verbosity.VERBOSE):
            for warning in self.warnings[:5]:  # Limit to first 5
                self.logger.warning(warning)
            if len(self.warnings) > 5:
                self.logger.warning(f"... and {len(self.warnings) - 5} more warnings")

        # Always log errors
        for error in self.errors:
            self.logger.error(error)

    def __enter__(self) -> LogAggregator:
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and emit summary."""
        if exc_type is not None:
            self.add_error(f"Exception: {exc_val}")
        self.emit()
