"""
Prometheus metrics push for data quality pipeline.

Pushes QualityReport check results to Pushgateway as Gauges.
Gracefully degrades to no-op if prometheus-client is not installed
or Pushgateway URL is not configured.

Severity mapping: ok=0, warn=1, critical=2.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

try:
    from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False

_SEVERITY_MAP = {"ok": 0, "warn": 1, "critical": 2}


def push_quality_metrics(report: object) -> bool:
    """Push QualityReport results to Prometheus Pushgateway.

    Args:
        report: QualityReport instance (typed as object to avoid circular import).

    Returns:
        True if push succeeded, False otherwise (never raises).
    """
    if not _HAS_PROMETHEUS:
        logger.debug("prometheus-client not installed — quality metrics push skipped")
        return False

    pushgateway_url = os.getenv("OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL", "")
    if not pushgateway_url:
        logger.debug("OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL not set — skipping push")
        return False

    enabled = os.getenv("OBSERVABILITY_PROMETHEUS_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    if not enabled:
        logger.debug("Prometheus metrics disabled via env — skipping push")
        return False

    try:
        registry = CollectorRegistry()
        severity_gauge = Gauge(
            "pklpo_dq_check_severity",
            "Data quality check severity (0=ok, 1=warn, 2=critical)",
            ["check_name", "symbol", "timeframe"],
            registry=registry,
        )
        value_gauge = Gauge(
            "pklpo_dq_check_value",
            "Data quality check measured value",
            ["check_name", "symbol", "timeframe"],
            registry=registry,
        )

        results = getattr(report, "results", [])
        for result in results:
            check_name = getattr(result, "check_name", "unknown")
            symbol = getattr(result, "symbol", "") or "all"
            timeframe = getattr(result, "timeframe", "") or "na"
            severity_str = str(getattr(result, "severity", "ok")).lower()
            value = getattr(result, "value", None)

            severity_gauge.labels(check_name, symbol, timeframe).set(
                _SEVERITY_MAP.get(severity_str, 0)
            )
            if value is not None:
                value_gauge.labels(check_name, symbol, timeframe).set(float(value))

        job_name = os.getenv("OBSERVABILITY_JOB_NAME", "data_quality_pipeline")
        push_to_gateway(pushgateway_url, job=job_name, registry=registry)
        logger.info(
            "Quality metrics pushed to %s (%d results)", pushgateway_url, len(results)
        )
        return True

    except Exception:
        logger.warning("Failed to push quality metrics to Pushgateway", exc_info=True)
        return False
