"""Airflow observability re-exports for platform observability."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from types import ModuleType

_COMMON_OBSERVABILITY_PATH = (
    Path(__file__).resolve().parents[3]
    / "ops"
    / "airflow"
    / "dags"
    / "_common"
    / "observability.py"
)


def _load_airflow_observability() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "src.pklpo_platform._airflow_common_observability",
        _COMMON_OBSERVABILITY_PATH,
    )
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Could not load Airflow observability from {_COMMON_OBSERVABILITY_PATH}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_airflow_observability = _load_airflow_observability()

airflow_log_context: Any = _airflow_observability.airflow_log_context
airflow_run_id: Any = _airflow_observability.airflow_run_id
airflow_task_id: Any = _airflow_observability.airflow_task_id

__all__ = [
    "airflow_log_context",
    "airflow_run_id",
    "airflow_task_id",
]
