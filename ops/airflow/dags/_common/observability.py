"""Shared observability helpers for Airflow DAG tasks."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from src.logging import configure_tracing, set_log_context, start_span

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

_TRACING_CONFIGURED = False


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


def _ensure_tracing_configured() -> None:
    global _TRACING_CONFIGURED
    if _TRACING_CONFIGURED:
        return
    configure_tracing()
    _TRACING_CONFIGURED = True


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
    symbol_value = str(symbol) if symbol is not None else None
    timeframe_value = str(timeframe) if timeframe is not None else None
    span_attributes = {
        "run_id": run_id,
        "component": component,
        "task_id": resolved_task_id,
    }
    if symbol_value is not None:
        span_attributes["symbol"] = symbol_value
    if timeframe_value is not None:
        span_attributes["timeframe"] = timeframe_value

    _ensure_tracing_configured()
    started_at = time.perf_counter()
    with start_span(
        f"airflow.{component}.{resolved_task_id}",
        run_id=run_id,
        attributes=span_attributes,
    ) as span:
        try:
            with set_log_context(
                run_id=run_id,
                symbol=symbol_value,
                timeframe=timeframe_value,
                component=component,
                task_id=resolved_task_id,
                **extra,
            ) as bound_run_id:
                yield bound_run_id
        except Exception as exc:
            span.set_attribute("status", "error")
            span.set_attribute("error_type", type(exc).__name__)
            span.set_attribute("error.reason", str(exc)[:500])
            raise
        else:
            span.set_attribute("status", "ok")
        finally:
            span.set_attribute("duration_seconds", time.perf_counter() - started_at)
