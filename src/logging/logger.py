"""Logger factory and utilities.

This module provides the main logger creation functions and utility helpers.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from logging import Logger
from typing import TYPE_CHECKING, Any

from .context import generate_run_id, get_current_run_id
from .filters import SensitiveDataFilter
from .handlers import _build_console_handler, _build_file_handler, get_log_directory
from .levels import LogCategory

if TYPE_CHECKING:
    from collections.abc import Iterable


# =============================================================================
# CATEGORY LOGGER
# =============================================================================


class CategoryAdapter(logging.LoggerAdapter[Logger]):
    """Logger adapter that adds category prefix to messages."""

    def __init__(self, logger: Logger, category: LogCategory) -> None:
        super().__init__(logger, {"category": category.value})
        self.category = category

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        """Add category prefix to message."""
        # Add category to extra for filtering
        extra = kwargs.get("extra", {}) if isinstance(kwargs, dict) else {}
        extra["category"] = self.category.value
        if isinstance(kwargs, dict):
            kwargs["extra"] = extra
        return f"[{self.category.value.upper()}] {msg}", kwargs


_category_loggers: dict[LogCategory, CategoryAdapter] = {}


def get_category_logger(category: LogCategory) -> CategoryAdapter:
    """Get a logger for a specific category.

    Args:
        category: Log category.

    Returns:
        Logger adapter that prefixes messages with category.

    Example:
        logger = get_category_logger(LogCategory.CALC)
        logger.info("Computing 24 indicators")
        # Output: [CALC] Computing 24 indicators
    """
    if category not in _category_loggers:
        base_logger = get_logger(category.value)
        _category_loggers[category] = CategoryAdapter(base_logger, category)
    return _category_loggers[category]


# =============================================================================
# BASE LOGGER
# =============================================================================

_base_logger: Logger | None = None


def _ensure_base_logger() -> Logger:
    """Ensure that the `pklpo` logger has handlers and context filter.

    Returns:
        Logger: Base project logger with ContextFilter attached.
    """
    global _base_logger

    if _base_logger is not None and _base_logger.handlers:
        return _base_logger

    logger = logging.getLogger("pklpo")
    if logger.handlers:
        _base_logger = logger
        return logger

    logger.setLevel(logging.DEBUG)

    # Add sensitive data filter at logger level (applies to all handlers)
    sensitive_filter = SensitiveDataFilter()
    logger.addFilter(sensitive_filter)

    # Build handlers (each handler has its own ContextFilter)
    log_dir = get_log_directory()
    handlers: Iterable[logging.Handler] = (
        _build_console_handler(),
        _build_file_handler("pklpo_debug.log", logging.DEBUG),
        _build_file_handler("pklpo_errors.log", logging.ERROR),
    )
    for handler in handlers:
        logger.addHandler(handler)

    logger.propagate = False
    _base_logger = logger
    return logger


def get_logger(name: str | None = None) -> Logger:
    """Return the base logger or a named child.

    Args:
        name: Child logger suffix (e.g., "features.calc").

    Returns:
        Logger: Configured logger.

    Example:
        logger = get_logger("mtf.context")
        logger.info("Processing...")
    """
    base = _ensure_base_logger()
    return base if not name else base.getChild(name)


# Backward compatibility aliases
def get_features_logger(name: str | None = None) -> Logger:
    """Return a features-specific logger.

    Deprecated: Use get_logger() instead.

    Args:
        name: Child logger suffix.

    Returns:
        Logger: Configured logger.
    """
    if name:
        return get_logger(f"features.{name}")
    return get_logger("features")


def setup_logging(level: str = "INFO", verbose: bool = False) -> Logger:
    """Initialize and configure the logging system.

    Args:
        level: Console handler threshold.
        verbose: Force DEBUG level.

    Returns:
        Logger: Base project logger.
    """
    logger = _ensure_base_logger()
    if verbose:
        os.environ["LOG_VERBOSE"] = "true"
    desired = (
        logging.DEBUG if verbose else getattr(logging, level.upper(), logging.INFO)
    )
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setLevel(desired)
    return logger


# Backward compatibility alias
def setup_features_logging(level: str = "INFO", verbose: bool = False) -> Logger:
    """Deprecated: Use setup_logging() instead."""
    return setup_logging(level, verbose)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def log_feature_quality(logger: Logger, df: Any, feature_name: str) -> None:
    """Log fill-rate diagnostics for a feature.

    Args:
        logger: Target logger.
        df: Series-like object with `notna`.
        feature_name: Feature identifier.
    """
    if not hasattr(df, "notna"):
        logger.warning("Feature %s has no notna()", feature_name)
        return
    total = len(df)
    if total <= 0:
        return
    non_null_raw = df.notna().sum()
    non_null = (
        int(non_null_raw.sum()) if hasattr(non_null_raw, "sum") else int(non_null_raw)
    )
    fill_rate = (non_null / total * 100) if total else 0
    if fill_rate <= 50:
        logger.warning(
            "Low fill rate for %s fill_rate=%.1f%% non_null=%d total=%d",
            feature_name,
            fill_rate,
            non_null,
            total,
        )


def log_batch_metrics(
    logger: Logger,
    batch_size: int,
    processed: int,
    errors: int = 0,
) -> None:
    """Log aggregated batch metrics.

    Args:
        logger: Target logger.
        batch_size: Number of rows in batch.
        processed: Number of processed rows.
        errors: Number of failed rows.
    """
    success_rate = (processed - errors) / batch_size * 100 if batch_size else 0
    logger.info(
        "Batch completed size=%d processed=%d errors=%d success=%.1f%%",
        batch_size,
        processed,
        errors,
        success_rate,
    )
    if errors:
        logger.warning(
            "Batch completed with errors size=%d processed=%d errors=%d success=%.1f%%",
            batch_size,
            processed,
            errors,
            success_rate,
        )


def log_features_summary(
    logger: Logger, summary: dict[str, dict[str, int]], symbol: str | None = None
) -> None:
    """Log summary statistics by timeframe.

    Args:
        logger: Target logger.
        summary: Dictionary mapping timeframe to statistics.
                 Example: {"1m": {"bars": 599, "features": 345, "saved": 345}}
        symbol: Optional symbol identifier for context.
    """
    logger.info("========== SUMMARY BY TIMEFRAMES ==========")
    if symbol:
        logger.info("Symbol: %s", symbol)
    total_saved = 0
    total_bars = 0
    total_features = 0
    for tf in sorted(summary.keys()):
        stats = summary[tf]
        bars = stats.get("bars", 0)
        features = stats.get("features", 0)
        saved = stats.get("saved", 0)
        logger.info(
            "%4s | bars=%d features=%d saved=%d",
            tf,
            bars,
            features,
            saved,
        )
        total_saved += saved
        total_bars += bars
        total_features += features
    logger.info("-------------------------------------------")
    logger.info(
        "TOTAL | bars=%d features=%d saved=%d", total_bars, total_features, total_saved
    )
    logger.info("===========================================\n")


def log_bad_record(
    logger: Logger, record: dict[str, Any], index: int, reason: str
) -> None:
    """Log problematic record that caused UPSERT failure.

    Args:
        logger: Target logger.
        record: Dictionary with record data.
        index: Record index in batch.
        reason: Error reason or exception message.
    """
    logger.error(
        "Bad record at index=%d reason=%s",
        index,
        reason,
    )
    logger.error("Record keys: %s", sorted(record.keys()))
    logger.error("Record sample (first 10 keys): %s", dict(list(record.items())[:10]))


def log_schema_mismatch(
    logger: Logger,
    missing_in_db: set[str],
    missing_in_df: set[str],
    type_conflicts: dict[str, tuple[str, str]],
) -> None:
    """Log schema inconsistencies between database and DataFrame.

    Args:
        logger: Target logger.
        missing_in_db: Columns present in DataFrame but missing in DB.
        missing_in_df: Columns present in DB but missing in DataFrame.
        type_conflicts: Dictionary mapping column name to (expected_type, actual_type).
    """
    if missing_in_db:
        logger.error("Columns missing in DB: %s", sorted(missing_in_db))
    if missing_in_df:
        logger.error("Columns missing in DataFrame: %s", sorted(missing_in_df))
    if type_conflicts:
        for col, (expected, actual) in sorted(type_conflicts.items()):
            logger.error(
                "Type mismatch for column=%s expected=%s actual=%s",
                col,
                expected,
                actual,
            )
    if missing_in_db or missing_in_df or type_conflicts:
        logger.error("Schema mismatch detected - fix before proceeding")


def log_sample_record(logger: Logger, record: dict[str, Any], stage: str) -> None:
    """Log sample record after processing stage for debugging.

    Args:
        logger: Target logger.
        record: Dictionary with record data.
        stage: Processing stage name (e.g., "normalize_numeric_columns").
    """
    logger.debug("Sample record after %s:", stage)
    logger.debug("  Keys: %s", sorted(record.keys()))
    logger.debug("  Sample (first 10 items): %s", dict(list(record.items())[:10]))


# =============================================================================
# RUN SUMMARY
# =============================================================================


@dataclass
class RunSummary:
    """Summary of a pipeline run for end-of-run logging.

    Collects metrics during pipeline execution and produces a summary log.
    """

    symbol: str
    timeframe: str
    run_id: str
    start_time: float = field(default_factory=time.perf_counter)

    # Metrics
    bars_processed: int = 0
    indicators_computed: int = 0
    rows_saved: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Fill rates by category
    fill_rates: dict[str, float] = field(default_factory=dict)

    # Status
    status: str = "ok"  # ok, partial, failed

    def add_error(self, error: str) -> None:
        """Add an error to the summary."""
        self.errors.append(error)
        self.status = "failed" if len(self.errors) > 0 else self.status

    def add_warning(self, warning: str) -> None:
        """Add a warning to the summary."""
        self.warnings.append(warning)
        if self.status == "ok":
            self.status = "partial"

    def set_fill_rate(self, category: str, rate: float) -> None:
        """Set fill rate for a category."""
        self.fill_rates[category] = rate

    @property
    def duration(self) -> float:
        """Calculate run duration in seconds."""
        return time.perf_counter() - self.start_time

    @property
    def avg_fill_rate(self) -> float:
        """Calculate average fill rate across all categories."""
        if not self.fill_rates:
            return 0.0
        return sum(self.fill_rates.values()) / len(self.fill_rates)

    def emit(self, log: logging.LoggerAdapter[Any] | Logger | None = None) -> None:
        """Emit the run summary to the log.

        Args:
            log: Logger to use. If None, uses category logger for PERF.
        """
        if log is None:
            log = get_category_logger(LogCategory.PERF)

        # Build summary line
        parts = [
            f"{self.symbol}/{self.timeframe}",
            f"status={self.status}",
            f"bars={self.bars_processed}",
            f"indicators={self.indicators_computed}",
            f"saved={self.rows_saved}",
            f"fill_rate={self.avg_fill_rate:.1%}",
            f"duration={self.duration:.2f}s",
        ]

        if self.errors:
            parts.append(f"errors={len(self.errors)}")

        log.info(" | ".join(parts))

        # Log errors if any
        for error in self.errors[:3]:  # Limit to first 3
            log.error(f"  Error: {error}")

        if len(self.errors) > 3:
            log.error(f"  ... and {len(self.errors) - 3} more errors")


def create_run_summary(
    symbol: str,
    timeframe: str,
    run_id: str | None = None,
) -> RunSummary:
    """Create a new RunSummary for tracking pipeline metrics.

    Args:
        symbol: Trading symbol.
        timeframe: Timeframe.
        run_id: Optional run ID. If None, uses current context or generates new.

    Returns:
        RunSummary instance for tracking metrics.

    Example:
        summary = create_run_summary("BTC-USDT", "1m")
        # ... pipeline execution ...
        summary.bars_processed = 1000
        summary.indicators_computed = 24
        summary.rows_saved = 950
        summary.emit()
    """
    if run_id is None:
        run_id = get_current_run_id() or generate_run_id()

    return RunSummary(
        symbol=symbol,
        timeframe=timeframe,
        run_id=run_id,
    )
