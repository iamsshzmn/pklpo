"""Platform-layer port definitions.

Protocols used by bounded contexts to emit observability signals without
depending on concrete Prometheus / OpenTelemetry infrastructure.

Layer rule: domain → application → infrastructure. These protocols live in the
application boundary so domain and application code can type against them
without importing any infrastructure library.

Current ports:
    MetricsPort — emit metric observations (counter, gauge, histogram)

Design note (G-12):
    v1 consumers (candles, features) push metrics directly via prometheus_client
    CollectorRegistry. MetricsPort formalises the interface so future adapters
    (OTel, StatsD, in-memory test double) can be swapped without touching callers.
    Existing publishers become compatible by wrapping their push function with
    a MetricsPort adapter (see src/candles/observability/prometheus.py).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MetricsPort(Protocol):
    """Minimal interface for emitting metric observations.

    Implementations are responsible for batching, labelling, and transport.
    Callers must not assume synchronous delivery — implementations may buffer.

    Contract:
        - emit() is always safe to call even if the metrics backend is down.
          Implementations must not raise; they may log a warning and return False.
        - label values must not contain high-cardinality identifiers (e.g. run_id).
          See observability constraints in docs/ARCHITECTURE.md §7.
    """

    def emit(
        self,
        metric_name: str,
        value: float,
        metric_type: str = "gauge",
        labels: dict[str, str] | None = None,
    ) -> bool:
        """Emit a single metric observation.

        Args:
            metric_name: Fully qualified metric name, e.g. ``pklpo_cache_hits_total``.
            value:        Numeric value to record.
            metric_type:  One of ``"gauge"``, ``"counter"``, ``"histogram"``.
                          Implementations may ignore this for backends that
                          determine type from registration.
            labels:       Low-cardinality key/value pairs. Never include run_id.

        Returns:
            True if the observation was accepted, False if the backend is
            unavailable or the call was silently dropped.
        """
        ...
