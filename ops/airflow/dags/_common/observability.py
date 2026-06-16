"""Shared observability helpers for Airflow DAG tasks."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from src.logging import set_log_context

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping


def _context_value(context: Mapping[str, Any], key: str) -> Any:
    value = context.get(key)
    if value is not None:
        return value
    params = context.get("params")
    if isinstance(params, dict):
        return params.get(key)
    return None


def airflow_run_id(context: Mapping[str, Any], fallback: str) -> str:
    """Resolve the canonical structured run_id for an Airflow task."""
    dag_run = context.get("dag_run")
    run_id = getattr(dag_run, "run_id", None)
    if run_id:
        return str(run_id)
    return fallback


def airflow_task_id(context: Mapping[str, Any], fallback: str) -> str:
    """Resolve the Airflow task_id from a task context."""
    task_instance = context.get("ti") or context.get("task_instance")
    task_id = getattr(task_instance, "task_id", None)
    if task_id:
        return str(task_id)
    return fallback


@contextmanager
def airflow_log_context(
    context: Mapping[str, Any],
    *,
    component: str,
    task_id: str | None = None,
    **extra: Any,
) -> Generator[str, None, None]:
    """Bind Airflow task metadata to project structured logging."""
    resolved_task_id = task_id or airflow_task_id(context, fallback=component)
    run_id = airflow_run_id(context, fallback=component)
    symbol = _context_value(context, "symbol")
    timeframe = _context_value(context, "timeframe")
    with set_log_context(
        run_id=run_id,
        symbol=str(symbol) if symbol is not None else None,
        timeframe=str(timeframe) if timeframe is not None else None,
        component=component,
        task_id=resolved_task_id,
        **extra,
    ) as bound_run_id:
        yield bound_run_id
