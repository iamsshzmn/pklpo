from __future__ import annotations

import sys


def test_get_trace_ids_returns_placeholders_without_active_span() -> None:
    from src.logging.tracing import get_trace_ids

    assert get_trace_ids() == ("-", "-")


def test_configure_tracing_disabled_does_not_import_otel_sdk() -> None:
    for module_name in (
        "opentelemetry.sdk.trace",
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
    ):
        sys.modules.pop(module_name, None)

    from src.logging.tracing import configure_tracing, get_trace_ids

    configure_tracing(enabled=False)

    assert get_trace_ids() == ("-", "-")
    assert "opentelemetry.sdk.trace" not in sys.modules
    assert "opentelemetry.exporter.otlp.proto.grpc.trace_exporter" not in sys.modules


def test_start_span_is_safe_when_tracing_disabled() -> None:
    from src.logging.tracing import (
        configure_tracing,
        get_trace_ids,
        set_span_attributes,
        start_span,
    )

    configure_tracing(enabled=False)

    with start_span("swap_sync.batch", run_id="run-otel-disabled"):
        set_span_attributes({"processed_count": 1})
        assert get_trace_ids() == ("-", "-")


def test_enabled_span_exposes_non_empty_trace_ids_without_tempo() -> None:
    from src.logging.tracing import configure_tracing, get_trace_ids, start_span

    assert configure_tracing(
        enabled=True,
        service_name="pklpo-test",
        otlp_endpoint="http://127.0.0.1:4317",
        sample_ratio=1.0,
    )

    try:
        with start_span("swap_sync.batch", run_id="run-otel-enabled"):
            trace_id, span_id = get_trace_ids()
            assert trace_id != "-"
            assert span_id != "-"
    finally:
        configure_tracing(enabled=False)


def test_enabled_span_force_flushes_after_exit(monkeypatch) -> None:
    from src.logging import tracing

    flush_calls: list[bool] = []

    class _Provider:
        @staticmethod
        def force_flush() -> None:
            flush_calls.append(True)

    assert tracing.configure_tracing(
        enabled=True,
        service_name="pklpo-test",
        otlp_endpoint="http://127.0.0.1:4317",
        sample_ratio=1.0,
    )
    monkeypatch.setattr(tracing, "_TRACER_PROVIDER", _Provider())

    try:
        with tracing.start_span("pipeline_monitoring.collect", run_id="run-flush"):
            assert flush_calls == []
    finally:
        tracing.configure_tracing(enabled=False)

    assert flush_calls == [True]
