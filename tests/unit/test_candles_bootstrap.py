"""Unit tests for the public candles bootstrap contract."""

from types import SimpleNamespace

import pytest

from src.candles import bootstrap as candles_bootstrap


def test_create_candles_airflow_callbacks_returns_public_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatcher_calls: list[object] = []

    class _Dispatcher:
        def notify_all(self, alert_ctx: object) -> dict[str, bool]:
            dispatcher_calls.append(alert_ctx)
            return {"observer": True}

    monkeypatch.setattr(
        "src.features.infrastructure.alerts.get_alert_dispatcher",
        lambda: _Dispatcher(),
    )
    monkeypatch.setattr(
        "src.features.infrastructure.alerts.extract_alert_context",
        lambda context: SimpleNamespace(
            level=None, error_message=None, context=context
        ),
    )
    monkeypatch.setattr(
        "src.features.infrastructure.alerts.success_callback",
        lambda context: {"ok": context},
    )

    callbacks = candles_bootstrap.create_candles_airflow_callbacks()

    assert isinstance(callbacks, candles_bootstrap.CandlesAirflowCallbacks)
    assert callable(callbacks.on_failure_callback)
    assert callable(callbacks.on_success_callback)
    assert callable(callbacks.on_retry_callback)

    callbacks.on_failure_callback({"task_id": "x"})
    callbacks.on_retry_callback({"task_id": "x"})

    assert len(dispatcher_calls) == 2
    assert dispatcher_calls[1].error_message == "Task scheduled for retry"
