"""Unified project logging.

Important:
- If this module is imported as top-level `logging`, we proxy to stdlib logging.
- If imported as `src.logging`, we expose project logging helpers.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import sysconfig


def _load_stdlib_logging() -> None:
    stdlib_dir = sysconfig.get_path("stdlib")
    if not stdlib_dir:
        raise ImportError("Could not resolve stdlib path for logging")

    spec = importlib.machinery.PathFinder.find_spec("logging", [stdlib_dir])
    if spec is None or spec.loader is None:
        raise ImportError("Could not load stdlib logging module")

    module = importlib.util.module_from_spec(spec)
    sys.modules["logging"] = module
    spec.loader.exec_module(module)
    globals().update(module.__dict__)


if __name__ == "logging":
    _load_stdlib_logging()
else:
    from .aggregator import AggregatedMetric, LogAggregator
    from .config import (
        get_log_backup_count,
        get_log_dir,
        get_log_file_max_bytes,
        get_log_format,
        get_log_level,
        get_verbosity,
        is_category_enabled,
        set_enabled_categories,
        set_verbosity,
        should_log,
    )
    from .context import (
        ContextFilter,
        generate_run_id,
        get_current_context,
        get_current_run_id,
        set_log_context,
    )
    from .decorators import (
        OperationContext,
        log_function_call,
        log_operation,
        performance_timer,
    )
    from .filters import CategoryFilter, SensitiveDataFilter
    from .formatters import CompactFormatter, JsonFormatter, _build_formatter
    from .handlers import (
        _build_console_handler,
        _build_file_handler,
        get_log_directory,
    )
    from .levels import LogCategory, Verbosity
    from .logger import (
        CategoryAdapter,
        RunSummary,
        create_run_summary,
        get_category_logger,
        get_features_logger,
        get_logger,
        log_bad_record,
        log_batch_metrics,
        log_feature_quality,
        log_features_summary,
        log_sample_record,
        log_schema_mismatch,
        setup_features_logging,
        setup_logging,
    )
    from .tracing import (
        configure_tracing,
        get_trace_ids,
        set_span_attributes,
        start_span,
    )

    # Backward compatibility: LOG_DIR as a property-like access
    LOG_DIR = get_log_directory()

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
        "configure_tracing",
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
        "get_trace_ids",
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
        "set_span_attributes",
        "set_verbosity",
        "setup_features_logging",
        "setup_logging",
        "should_log",
        "start_span",
    ]
