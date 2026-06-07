"""Observability module - logging, metrics, tracing.

Single facade: import from here rather than from submodules.
  from src.features.observability import get_metrics, MetricsCollector
  from src.features.observability import PipelineMetrics, reset_metrics
  from src.features.observability import FeatureTracer, get_global_tracer
"""

from src.logging import (
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
from .prometheus import PipelineMetrics, get_metrics, reset_metrics
from .traceability import (
    FeatureMetadata,
    FeatureTracer,
    disable_tracing,
    enable_tracing,
    get_feature_metadata,
    get_global_tracer,
    track_feature,
)

__all__ = [
    "FeatureMetadata",
    "FeatureTracer",
    "LogAggregator",
    "LogCategory",
    "MetricsCollector",
    "PipelineMetrics",
    "RunSummary",
    "Verbosity",
    "create_run_summary",
    "disable_tracing",
    "enable_tracing",
    "get_category_logger",
    "get_current_run_id",
    "get_feature_metadata",
    "get_features_logger",
    "get_global_tracer",
    "get_metrics",
    "get_verbosity",
    "reset_metrics",
    "set_log_context",
    "set_verbosity",
    "should_log",
    "track_feature",
]
