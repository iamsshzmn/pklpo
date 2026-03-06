"""Legacy logging compatibility layer for features.

Deprecated: use ``src.logging`` for new code.
"""

from __future__ import annotations

import importlib.util
import warnings
from pathlib import Path

warnings.warn(
    "src.features.observability.logging is deprecated. "
    "Use src.logging instead for new code.",
    DeprecationWarning,
    stacklevel=2,
)


def _load_legacy_module():
    module_path = Path(__file__).resolve().parents[1] / "logging.py"
    spec = importlib.util.spec_from_file_location(
        "src.features.observability._logging_legacy_impl",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load legacy logging module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_legacy = _load_legacy_module()

LOG_DIR = _legacy.LOG_DIR
_build_console_handler = _legacy._build_console_handler
_build_formatter = _legacy._build_formatter
performance_timer = _legacy.performance_timer
log_batch_metrics = _legacy.log_batch_metrics
log_features_summary = _legacy.log_features_summary
log_bad_record = _legacy.log_bad_record
log_schema_mismatch = _legacy.log_schema_mismatch
log_sample_record = _legacy.log_sample_record


def _sync_legacy_log_dir() -> None:
    _legacy.LOG_DIR = LOG_DIR
    _legacy.LOG_DIR.mkdir(parents=True, exist_ok=True)


def _build_file_handler(filename: str, level: int, max_bytes: int, backup_count: int):
    _sync_legacy_log_dir()
    return _legacy._build_file_handler(filename, level, max_bytes, backup_count)


def get_features_logger(name: str | None = None):
    _sync_legacy_log_dir()
    return _legacy.get_features_logger(name)


def setup_features_logging(level: str = "INFO", verbose: bool = False):
    _sync_legacy_log_dir()
    return _legacy.setup_features_logging(level=level, verbose=verbose)


def log_feature_quality(logger, df, feature_name: str) -> None:
    _legacy.log_feature_quality(logger, df, feature_name)


# Re-export the canonical API as a fallback for callers using newer symbols.
from src.logging import (
    AggregatedMetric,
    CategoryAdapter,
    CategoryFilter,
    CompactFormatter,
    ContextFilter,
    JsonFormatter,
    LogAggregator,
    LogCategory,
    OperationContext,
    RunSummary,
    SensitiveDataFilter,
    Verbosity,
    create_run_summary,
    generate_run_id,
    get_category_logger,
    get_current_context,
    get_current_run_id,
    get_log_backup_count,
    get_log_dir,
    get_log_directory,
    get_log_file_max_bytes,
    get_log_format,
    get_log_level,
    get_logger,
    get_verbosity,
    is_category_enabled,
    log_function_call,
    log_operation,
    set_enabled_categories,
    set_log_context,
    set_verbosity,
    setup_logging,
    should_log,
)

__all__ = [
    "LOG_DIR",
    "AggregatedMetric",
    "CategoryAdapter",
    "CategoryFilter",
    "CompactFormatter",
    "ContextFilter",
    "JsonFormatter",
    "LogAggregator",
    "LogCategory",
    "OperationContext",
    "RunSummary",
    "SensitiveDataFilter",
    "Verbosity",
    "_build_console_handler",
    "_build_file_handler",
    "_build_formatter",
    "create_run_summary",
    "generate_run_id",
    "get_category_logger",
    "get_current_context",
    "get_current_run_id",
    "get_features_logger",
    "get_log_backup_count",
    "get_log_dir",
    "get_log_directory",
    "get_log_file_max_bytes",
    "get_log_format",
    "get_log_level",
    "get_logger",
    "get_verbosity",
    "is_category_enabled",
    "log_bad_record",
    "log_batch_metrics",
    "log_feature_quality",
    "log_features_summary",
    "log_function_call",
    "log_operation",
    "log_sample_record",
    "log_schema_mismatch",
    "performance_timer",
    "set_enabled_categories",
    "set_log_context",
    "set_verbosity",
    "setup_features_logging",
    "setup_logging",
    "should_log",
]
