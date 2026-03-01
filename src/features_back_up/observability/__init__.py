"""Observability module - logging, metrics, tracing, errors."""

from .error_handling import CalculationError, FeaturesError
from .logging import (
    LogAggregator,
    LogCategory,
    RunSummary,
    Verbosity,
    create_run_summary,
    get_category_logger,
    get_current_run_id,
    get_features_logger,
    get_verbosity,
    set_log_context,
    set_verbosity,
    should_log,
)
from .metrics import MetricsCollector

__all__ = [
    "CalculationError",
    "FeaturesError",
    "LogAggregator",
    "LogCategory",
    "MetricsCollector",
    "RunSummary",
    "Verbosity",
    "create_run_summary",
    "get_category_logger",
    "get_current_run_id",
    "get_features_logger",
    "get_verbosity",
    "set_log_context",
    "set_verbosity",
    "should_log",
]
