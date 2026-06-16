"""Platform observability facade.

This package is re-export only. Implementations stay in their existing modules.
"""

from __future__ import annotations

from .airflow import airflow_log_context, airflow_run_id, airflow_task_id
from .context import (
    ContextFilter,
    generate_run_id,
    get_current_context,
    get_current_run_id,
    set_log_context,
)
from .error_types import ErrorType, classify_error_type
from .logging import get_category_logger, get_features_logger, get_logger
from .metrics import (
    push_dependency_health_metrics,
    push_feature_eligibility_metrics,
    push_market_selection_metrics,
    push_pipeline_monitoring_metrics,
    push_quality_metrics,
    push_swap_repair_metrics,
    push_swap_smoke_metrics,
    push_swap_sync_metrics,
)

__all__ = [
    "ContextFilter",
    "ErrorType",
    "classify_error_type",
    "airflow_log_context",
    "airflow_run_id",
    "airflow_task_id",
    "generate_run_id",
    "get_category_logger",
    "get_current_context",
    "get_current_run_id",
    "get_features_logger",
    "get_logger",
    "push_dependency_health_metrics",
    "push_feature_eligibility_metrics",
    "push_market_selection_metrics",
    "push_pipeline_monitoring_metrics",
    "push_quality_metrics",
    "push_swap_repair_metrics",
    "push_swap_smoke_metrics",
    "push_swap_sync_metrics",
    "set_log_context",
]
