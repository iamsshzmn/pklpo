"""OpenTelemetry tracing integration.

This module is the single import point for OpenTelemetry SDK/exporter packages.
Imports stay lazy so default-disabled tracing does not affect lightweight
observability facade imports or environments that have not installed OTel yet.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

_TRACING_ENABLED = False
_TRACER_NAME = "pklpo"
_PROVIDER_CONFIGURED = False
_TRACER_PROVIDER: Any | None = None


@dataclass(frozen=True)
class _NoopSpan:
    """Minimal span object for disabled or unavailable tracing."""

    name: str

    def set_attribute(self, key: str, value: Any) -> None:
        return None


def _normalise_sample_ratio(value: float) -> float:
    return max(0.0, min(1.0, value))


def configure_tracing(
    *,
    enabled: bool | None = None,
    service_name: str | None = None,
    otlp_endpoint: str | None = None,
    sample_ratio: float | None = None,
    settings: Any | None = None,
) -> bool:
    """Configure OpenTelemetry tracing when explicitly enabled.

    Returns ``True`` only when the SDK/exporter setup succeeds. When tracing is
    disabled or OTel packages are unavailable, the function is a safe no-op.
    """
    global _PROVIDER_CONFIGURED, _TRACER_PROVIDER, _TRACING_ENABLED

    if settings is None and enabled is None:
        from src.config import get_settings

        settings = get_settings().observability

    if settings is not None:
        enabled = bool(settings.otel_enabled) if enabled is None else enabled
        service_name = service_name or settings.otel_service_name
        otlp_endpoint = otlp_endpoint or settings.otel_exporter_otlp_endpoint
        sample_ratio = (
            float(settings.otel_sample_ratio)
            if sample_ratio is None
            else sample_ratio
        )

    if enabled is not True:
        _TRACING_ENABLED = False
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    except ImportError:
        _TRACING_ENABLED = False
        return False

    if not _PROVIDER_CONFIGURED:
        resource = Resource.create({"service.name": service_name or "pklpo"})
        provider = TracerProvider(
            resource=resource,
            sampler=TraceIdRatioBased(_normalise_sample_ratio(sample_ratio or 1.0)),
        )
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint or "http://localhost:4317")
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _TRACER_PROVIDER = provider
        _PROVIDER_CONFIGURED = True

        for instrumentor in _build_optional_instrumentors():
            try:
                instrumentor.instrument()
            except Exception:
                pass

    _TRACING_ENABLED = True
    return True


def _build_optional_instrumentors() -> list[Any]:
    instrumentors: list[Any] = []
    try:
        from opentelemetry.instrumentation.aiohttp_client import (
            AioHttpClientInstrumentor,
        )
    except ImportError:
        pass
    else:
        instrumentors.append(AioHttpClientInstrumentor())

    try:
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
    except ImportError:
        pass
    else:
        instrumentors.append(AsyncPGInstrumentor())

    return instrumentors


def _force_flush_provider() -> None:
    provider = _TRACER_PROVIDER
    if provider is None:
        return
    try:
        provider.force_flush()
    except Exception:
        pass


def get_trace_ids() -> tuple[str, str]:
    """Return active ``trace_id`` and ``span_id`` or placeholders."""
    if not _TRACING_ENABLED:
        return "-", "-"

    try:
        from opentelemetry import trace
    except ImportError:
        return "-", "-"

    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return "-", "-"

    return f"{span_context.trace_id:032x}", f"{span_context.span_id:016x}"


def set_span_attributes(attributes: dict[str, Any]) -> None:
    """Set attributes on the active span when tracing is enabled."""
    if not _TRACING_ENABLED:
        return

    try:
        from opentelemetry import trace
    except ImportError:
        return

    span = trace.get_current_span()
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)


@contextmanager
def start_span(
    name: str,
    *,
    run_id: str | None = None,
    attributes: dict[str, Any] | None = None,
    **extra_attributes: Any,
) -> Iterator[Any]:
    """Start an OTel span when tracing is enabled, otherwise yield a no-op."""
    if not _TRACING_ENABLED:
        yield _NoopSpan(name)
        return

    try:
        from opentelemetry import trace
    except ImportError:
        yield _NoopSpan(name)
        return

    tracer = trace.get_tracer(_TRACER_NAME)
    try:
        with tracer.start_as_current_span(name) as span:
            if run_id is not None:
                span.set_attribute("run_id", run_id)
            for key, value in {**(attributes or {}), **extra_attributes}.items():
                if value is not None:
                    span.set_attribute(key, value)
            yield span
    finally:
        _force_flush_provider()
