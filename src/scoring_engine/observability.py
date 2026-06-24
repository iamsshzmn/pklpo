"""Thin observability boundary for the scoring engine.

Push Prometheus metrics to Pushgateway at the conclusion of a scoring run.
Called from CLI entry points or Airflow task callables — NOT from domain code.

Metrics published:
    pklpo_scoring_scored_total       — symbols successfully scored
    pklpo_scoring_score_errors_total — symbols that raised an error during scoring
"""

from __future__ import annotations

import logging
import os
from typing import Any

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


def push_scoring_metrics(
    scored_count: int,
    score_errors: int,
    extra: dict[str, Any] | None = None,
) -> bool:
    """Push scoring run summary to Prometheus Pushgateway.

    Args:
        scored_count: Number of symbols successfully scored.
        score_errors: Number of symbols that raised an error during scoring.
        extra: Optional dict for future extension (ignored for now).

    Returns:
        True if metrics were pushed successfully, False otherwise.
    """
    can_push, pushgateway_url = _can_push()
    if not can_push:
        logger.debug("Scoring metrics push skipped (Prometheus disabled or unconfigured)")
        return False

    try:
        from prometheus_client import CollectorRegistry, Counter, push_to_gateway

        registry = CollectorRegistry()
        scored_gauge = Counter(
            "pklpo_scoring_scored_total",
            "Total symbols successfully scored in this run",
            registry=registry,
        )
        errors_gauge = Counter(
            "pklpo_scoring_score_errors_total",
            "Total symbols that raised an error during scoring",
            registry=registry,
        )
        scored_gauge.inc(scored_count)
        errors_gauge.inc(score_errors)

        job_name = os.getenv("OBSERVABILITY_JOB_NAME", "scoring_engine")
        push_to_gateway(pushgateway_url, job=job_name, registry=registry)
        logger.info(
            "Scoring metrics pushed scored=%d errors=%d",
            scored_count,
            score_errors,
        )
        return True
    except Exception:
        logger.warning("Failed to push scoring metrics to Pushgateway", exc_info=True)
        return False
