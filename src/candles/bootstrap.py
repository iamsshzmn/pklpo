"""Composition root helpers for the candles bounded context."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandlesAirflowCallbacks:
    """Public Airflow callback bundle assembled at the composition root."""

    on_failure_callback: object | None
    on_success_callback: object | None
    on_retry_callback: object | None


def create_candles_airflow_callbacks() -> CandlesAirflowCallbacks:
    """Expose Airflow alert callbacks through the public bootstrap boundary."""
    from src.features.infrastructure.alerts import (
        AlertLevel,
        extract_alert_context,
        get_alert_dispatcher,
        success_callback,
    )

    def retry_callback(context: dict[str, object]) -> None:
        alert_ctx = extract_alert_context(context)
        alert_ctx.level = AlertLevel.WARNING
        alert_ctx.error_message = "Task scheduled for retry"
        get_alert_dispatcher().notify_all(alert_ctx)

    return CandlesAirflowCallbacks(
        on_failure_callback=lambda context: get_alert_dispatcher().notify_all(
            extract_alert_context(context)
        ),
        on_success_callback=success_callback,
        on_retry_callback=retry_callback,
    )
