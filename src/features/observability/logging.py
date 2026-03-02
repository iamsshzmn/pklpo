"""Logging configuration for the features module."""

from __future__ import annotations

import logging
import os
import time
from functools import wraps
from logging import Formatter, Handler, Logger
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

T = TypeVar("T")

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _build_formatter() -> Formatter:
    """Return a formatter with unified message format.

    Returns:
        Formatter: Shared formatter for all handlers.
    """
    return Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )


def _build_console_handler() -> Handler:
    """Create a stream handler for stdout.

    Returns:
        Handler: Configured stream handler.
    """
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(_build_formatter())
    return handler


def _build_file_handler(
    filename: str, level: int, max_bytes: int, backup_count: int
) -> Handler:
    """Create a rotating file handler.

    Args:
        filename: Target log file name.
        level: Minimum log level.
        max_bytes: Max file size before rotation.
        backup_count: Number of backup files.

    Returns:
        Handler: Configured rotating handler.
    """
    handler = RotatingFileHandler(
        LOG_DIR / filename,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(_build_formatter())
    return handler


def _ensure_base_logger() -> Logger:
    """Ensure that the `pklpo.features` logger has handlers.

    Returns:
        Logger: Base features logger.
    """
    logger = logging.getLogger("pklpo.features")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    handlers: Iterable[Handler] = (
        _build_console_handler(),
        _build_file_handler("features_debug.log", logging.DEBUG, 5 * 1024 * 1024, 5),
        _build_file_handler("features_errors.log", logging.ERROR, 2 * 1024 * 1024, 3),
    )
    for handler in handlers:
        logger.addHandler(handler)

    logger.propagate = False
    return logger


def get_features_logger(name: str | None = None) -> Logger:
    """Return the base logger or a named child.

    Args:
        name: Child logger suffix.

    Returns:
        Logger: Configured logger.
    """
    base = _ensure_base_logger()
    return base if not name else base.getChild(name)


def setup_features_logging(level: str = "INFO", verbose: bool = False) -> Logger:
    """Adjust the console handler level and optionally enable verbose mode.

    Args:
        level: Console handler threshold.
        verbose: Force DEBUG level and set FEATURES_VERBOSE.

    Returns:
        Logger: Base features logger.
    """
    logger = _ensure_base_logger()
    if verbose:
        os.environ["FEATURES_VERBOSE"] = "true"
    desired = (
        logging.DEBUG if verbose else getattr(logging, level.upper(), logging.INFO)
    )
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setLevel(desired)
    return logger


def performance_timer(
    logger: Logger,
    operation_name: str,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Log execution time for wrapped functions.

    Args:
        logger: Target logger.
        operation_name: Human-readable operation name.

    Returns:
        Callable: Decorator preserving the wrapped function.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
            except Exception:
                duration = time.perf_counter() - start
                logger.error(
                    "Operation %s failed duration=%.3fs",
                    operation_name,
                    duration,
                    exc_info=True,
                )
                raise
            duration = time.perf_counter() - start
            logger.debug(
                "Operation %s completed duration=%.3fs",
                operation_name,
                duration,
            )
            return result

        return wrapper

    return decorator


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
    if fill_rate < 50:
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
