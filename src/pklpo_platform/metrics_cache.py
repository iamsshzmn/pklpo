"""Observability push helpers for the platform layer.

Push Prometheus metrics for platform-level subsystems (cache, locks, etc.).
Call from CLI entry points or Airflow task boundaries — NOT from hot paths.

Metrics published:
    pklpo_cache_hits_total    — cumulative cache hits since process start
    pklpo_cache_misses_total  — cumulative cache misses since process start
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _can_push() -> tuple[bool, str]:
    try:
        from prometheus_client import CollectorRegistry, push_to_gateway  # noqa: F401
    except ImportError:
        return False, ""

    pushgateway_url = os.getenv("OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL", "")
    enabled = os.getenv("OBSERVABILITY_PROMETHEUS_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    if not pushgateway_url or not enabled:
        return False, ""
    return True, pushgateway_url


def push_cache_metrics() -> bool:
    """Push platform cache hit/miss counters to Prometheus Pushgateway.

    Reads the in-memory counters from src.pklpo_platform.cache and pushes them as
    Gauges (snapshot semantics — Pushgateway replaces the previous value).

    Returns:
        True if metrics were pushed successfully, False otherwise.
    """
    can_push, pushgateway_url = _can_push()
    if not can_push:
        logger.debug("Cache metrics push skipped (Prometheus disabled or unconfigured)")
        return False

    try:
        from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

        from .cache import get_cache_stats

        stats = get_cache_stats()

        registry = CollectorRegistry()
        hits_gauge = Gauge(
            "pklpo_cache_hits_total",
            "Cumulative Redis cache hits since process start",
            registry=registry,
        )
        misses_gauge = Gauge(
            "pklpo_cache_misses_total",
            "Cumulative Redis cache misses since process start",
            registry=registry,
        )
        hits_gauge.set(float(stats["hits"]))
        misses_gauge.set(float(stats["misses"]))

        job_name = os.getenv("OBSERVABILITY_JOB_NAME", "platform_cache")
        push_to_gateway(pushgateway_url, job=job_name, registry=registry)
        logger.info(
            "Cache metrics pushed hits=%d misses=%d",
            stats["hits"],
            stats["misses"],
        )
        return True
    except Exception:
        logger.warning("Failed to push cache metrics to Pushgateway", exc_info=True)
        return False
