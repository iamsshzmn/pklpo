"""Thin observability boundary for the trade recommender.

Push Prometheus metrics at the conclusion of a recommendations batch.
Called from CLI entry points — NOT from domain code.

Metrics published:
    pklpo_recommender_recommendations_generated_total
    pklpo_recommender_recommendation_errors_total
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


def push_recommender_metrics(
    recommendations_generated: int,
    recommendation_errors: int = 0,
) -> bool:
    """Push trade recommender run summary to Prometheus Pushgateway.

    Args:
        recommendations_generated: Number of trade recommendations produced.
        recommendation_errors: Number of score IDs that failed to produce a recommendation.

    Returns:
        True if metrics were pushed successfully, False otherwise.
    """
    can_push, pushgateway_url = _can_push()
    if not can_push:
        logger.debug("Recommender metrics push skipped (Prometheus disabled or unconfigured)")
        return False

    try:
        from prometheus_client import CollectorRegistry, Counter, push_to_gateway

        registry = CollectorRegistry()
        recs_counter = Counter(
            "pklpo_recommender_recommendations_generated_total",
            "Total trade recommendations generated in this run",
            registry=registry,
        )
        errors_counter = Counter(
            "pklpo_recommender_recommendation_errors_total",
            "Total score IDs that failed to produce a recommendation",
            registry=registry,
        )
        recs_counter.inc(recommendations_generated)
        errors_counter.inc(recommendation_errors)

        job_name = os.getenv("OBSERVABILITY_JOB_NAME", "trade_recommender")
        push_to_gateway(pushgateway_url, job=job_name, registry=registry)
        logger.info(
            "Recommender metrics pushed generated=%d errors=%d",
            recommendations_generated,
            recommendation_errors,
        )
        return True
    except Exception:
        logger.warning("Failed to push recommender metrics to Pushgateway", exc_info=True)
        return False
