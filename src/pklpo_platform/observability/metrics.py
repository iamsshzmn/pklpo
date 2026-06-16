"""Prometheus push helper re-exports for platform observability."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

_CANDLES_PROMETHEUS_PATH = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "candles"
    / "observability"
    / "prometheus.py"
)


def _load_candles_prometheus() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "src.pklpo_platform._candles_observability_prometheus",
        _CANDLES_PROMETHEUS_PATH,
    )
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Could not load candles prometheus helpers from {_CANDLES_PROMETHEUS_PATH}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_prometheus = _load_candles_prometheus()

push_market_selection_metrics: Any = _prometheus.push_market_selection_metrics
push_dependency_health_metrics: Any = _prometheus.push_dependency_health_metrics
push_feature_eligibility_metrics: Any = _prometheus.push_feature_eligibility_metrics
push_pipeline_monitoring_metrics: Any = _prometheus.push_pipeline_monitoring_metrics
push_quality_metrics: Any = _prometheus.push_quality_metrics
push_swap_repair_metrics: Any = _prometheus.push_swap_repair_metrics
push_swap_smoke_metrics: Any = _prometheus.push_swap_smoke_metrics
push_swap_sync_metrics: Any = _prometheus.push_swap_sync_metrics

__all__ = [
    "push_market_selection_metrics",
    "push_dependency_health_metrics",
    "push_feature_eligibility_metrics",
    "push_pipeline_monitoring_metrics",
    "push_quality_metrics",
    "push_swap_repair_metrics",
    "push_swap_smoke_metrics",
    "push_swap_sync_metrics",
]
