"""Thin observability boundary for the signals pipeline.

Push Prometheus metrics after a signal lifecycle batch (promote/expire/cancel).
Called from application/CLI layer — NOT from domain code.

Metrics published:
    pklpo_signals_promoted_total
    pklpo_signals_expired_total
    pklpo_signals_cancelled_total
    pklpo_signal_freshness_seconds   — age of the most recent live signal (Gauge)
    pklpo_model_config_age_seconds   — age of the active model/config file (Gauge)
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _can_push() -> tuple[bool, str]:
    try:
        from prometheus_client import CollectorRegistry, Gauge, push_to_gateway  # noqa: F401
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


def push_signal_metrics(
    *,
    promoted: int = 0,
    expired: int = 0,
    cancelled: int = 0,
    signal_freshness_seconds: float | None = None,
    model_or_config_age_seconds: float | None = None,
) -> bool:
    """Push signal lifecycle metrics to Prometheus Pushgateway.

    Args:
        promoted:  Count of candidate→live promotions in this batch.
        expired:   Count of live signals that transitioned to expired.
        cancelled: Count of live signals that were cancelled.
        signal_freshness_seconds: Age in seconds of the most recent live signal.
            None skips the freshness gauge.
        model_or_config_age_seconds: Age in seconds of the active model/config.
            None skips the age gauge.

    Returns:
        True if metrics were pushed successfully, False otherwise.
    """
    can_push, pushgateway_url = _can_push()
    if not can_push:
        logger.debug("Signal metrics push skipped (Prometheus disabled or unconfigured)")
        return False

    try:
        from prometheus_client import CollectorRegistry, Counter, Gauge, push_to_gateway

        registry = CollectorRegistry()

        promoted_counter = Counter(
            "pklpo_signals_promoted_total",
            "Signals promoted from candidate to live in this batch",
            registry=registry,
        )
        expired_counter = Counter(
            "pklpo_signals_expired_total",
            "Live signals that expired in this batch",
            registry=registry,
        )
        cancelled_counter = Counter(
            "pklpo_signals_cancelled_total",
            "Live signals that were cancelled in this batch",
            registry=registry,
        )
        promoted_counter.inc(promoted)
        expired_counter.inc(expired)
        cancelled_counter.inc(cancelled)

        if signal_freshness_seconds is not None:
            freshness_gauge = Gauge(
                "pklpo_signal_freshness_seconds",
                "Age in seconds of the most recent live signal",
                registry=registry,
            )
            freshness_gauge.set(float(signal_freshness_seconds))

        if model_or_config_age_seconds is not None:
            model_age_gauge = Gauge(
                "pklpo_model_config_age_seconds",
                "Age in seconds of the active model or config file",
                registry=registry,
            )
            model_age_gauge.set(float(model_or_config_age_seconds))

        job_name = os.getenv("OBSERVABILITY_JOB_NAME", "signals_pipeline")
        push_to_gateway(pushgateway_url, job=job_name, registry=registry)
        logger.info(
            "Signal metrics pushed promoted=%d expired=%d cancelled=%d",
            promoted,
            expired,
            cancelled,
        )
        return True
    except Exception:
        logger.warning("Failed to push signal metrics to Pushgateway", exc_info=True)
        return False
