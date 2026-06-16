"""Health metric re-exports for platform observability."""

from __future__ import annotations

from .metrics import push_dependency_health_metrics

__all__ = ["push_dependency_health_metrics"]
