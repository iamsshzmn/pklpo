"""
Prometheus metrics push helpers for candles pipelines.

Supports:
- quality pipeline metrics
- swap_ohlcv sync runtime metrics
- swap_ohlcv smoke validation metrics
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, push_to_gateway

    _HAS_PROMETHEUS = True
except ImportError:  # pragma: no cover
    _HAS_PROMETHEUS = False

_SEVERITY_MAP = {"ok": 0, "warn": 1, "critical": 2}


def _prometheus_enabled() -> bool:
    return os.getenv("OBSERVABILITY_PROMETHEUS_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    )


def _can_push() -> tuple[bool, str]:
    if not _HAS_PROMETHEUS:
        logger.debug("prometheus-client not installed; metrics push skipped")
        return False, ""

    pushgateway_url = os.getenv("OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL", "")
    if not pushgateway_url:
        logger.debug("OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL not set; skipping push")
        return False, ""

    if not _prometheus_enabled():
        logger.debug("Prometheus metrics disabled via env; skipping push")
        return False, ""

    return True, pushgateway_url


def _push_registry(registry: CollectorRegistry, job_name: str) -> bool:
    can_push, pushgateway_url = _can_push()
    if not can_push:
        return False

    try:
        push_to_gateway(pushgateway_url, job=job_name, registry=registry)
        return True
    except Exception:
        logger.warning(
            "Failed to push metrics to Pushgateway for job=%s",
            job_name,
            exc_info=True,
        )
        return False


def push_quality_metrics(report: object) -> bool:
    """Push QualityReport results to Prometheus Pushgateway."""
    can_push, pushgateway_url = _can_push()
    if not can_push:
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
        freshness_gauge = Gauge(
            "pklpo_data_freshness_lag_seconds",
            "Freshness lag in seconds derived from swap_ohlcv quality checks",
            ["symbol", "timeframe"],
            registry=registry,
        )
        fill_rate_gauge = Gauge(
            "pklpo_data_fill_rate",
            "Fill rate derived from swap_ohlcv coverage quality checks",
            ["symbol", "timeframe"],
            registry=registry,
        )
        hole_rate_gauge = Gauge(
            "pklpo_data_hole_rate",
            "Hole rate derived from swap_ohlcv coverage quality checks",
            ["symbol", "timeframe"],
            registry=registry,
        )
        quality_score_gauge = Gauge(
            "pklpo_data_quality_score",
            "Quality score proxy derived from swap_ohlcv coverage quality checks",
            ["symbol", "timeframe"],
            registry=registry,
        )
        duplicates_counter = Counter(
            "pklpo_duplicate_rows_detected_total",
            "Duplicate rows detected by swap_ohlcv quality checks",
            ["symbol", "timeframe"],
            registry=registry,
        )

        results = getattr(report, "results", [])
        for result in results:
            check_name = getattr(result, "check_name", "unknown")
            symbol = getattr(result, "symbol", "") or "all"
            timeframe = getattr(result, "timeframe", "") or "na"
            severity_str = str(getattr(result, "severity", "ok")).lower()
            value = getattr(result, "value", None)
            meta = getattr(result, "meta", {}) or {}

            severity_gauge.labels(check_name, symbol, timeframe).set(
                _SEVERITY_MAP.get(severity_str, 0)
            )
            if value is not None:
                value_gauge.labels(check_name, symbol, timeframe).set(float(value))

            if check_name == "freshness" and value is not None:
                freshness_gauge.labels(symbol, timeframe).set(float(value) * 60.0)
            elif check_name == "coverage_1m" and value is not None:
                coverage_rate = max(0.0, min(float(value) / 100.0, 1.0))
                fill_rate_gauge.labels(symbol, timeframe).set(coverage_rate)
                hole_rate_gauge.labels(symbol, timeframe).set(1.0 - coverage_rate)
                quality_score_gauge.labels(symbol, timeframe).set(coverage_rate)
            elif check_name == "duplicate_rate_1m":
                duplicate_rows = int(meta.get("duplicate_rows", 0))
                if duplicate_rows > 0:
                    duplicates_counter.labels(symbol, timeframe).inc(duplicate_rows)

        job_name = os.getenv("OBSERVABILITY_JOB_NAME", "data_quality_pipeline")
        push_to_gateway(pushgateway_url, job=job_name, registry=registry)
        logger.info(
            "Quality metrics pushed to %s (%d results)", pushgateway_url, len(results)
        )
        return True
    except Exception:
        logger.warning("Failed to push quality metrics to Pushgateway", exc_info=True)
        return False


def push_swap_sync_metrics(stats: dict[str, Any]) -> bool:
    """Push swap_ohlcv sync runtime metrics to Pushgateway."""
    if not stats:
        return False

    try:
        registry = CollectorRegistry()
        mode = str(stats.get("mode", "unknown"))

        duration_gauge = Gauge(
            "pklpo_swap_sync_duration_seconds",
            "Duration of swap_ohlcv sync run",
            ["mode"],
            registry=registry,
        )
        rows_gauge = Gauge(
            "pklpo_swap_sync_rows_upserted_total",
            "Rows upserted during swap_ohlcv sync run",
            ["mode"],
            registry=registry,
        )
        symbols_gauge = Gauge(
            "pklpo_swap_sync_symbols_processed_total",
            "Symbols processed during swap_ohlcv sync run",
            ["mode"],
            registry=registry,
        )
        errors_gauge = Gauge(
            "pklpo_swap_sync_errors_total",
            "Errors observed during swap_ohlcv sync run",
            ["mode"],
            registry=registry,
        )
        speed_gauge = Gauge(
            "pklpo_swap_sync_candles_per_second",
            "Throughput of swap_ohlcv sync run",
            ["mode"],
            registry=registry,
        )
        rate_limit_gauge = Gauge(
            "pklpo_swap_sync_api_rate_limit_hits_total",
            "Rate limit hits observed during swap_ohlcv sync run",
            ["mode"],
            registry=registry,
        )
        timeout_gauge = Gauge(
            "pklpo_swap_sync_api_timeouts_total",
            "Timeouts observed during swap_ohlcv sync run",
            ["mode"],
            registry=registry,
        )
        db_latency_avg_gauge = Gauge(
            "pklpo_swap_sync_db_write_latency_avg_ms",
            "Average DB write latency for swap_ohlcv sync run",
            ["mode"],
            registry=registry,
        )
        db_latency_p95_gauge = Gauge(
            "pklpo_swap_sync_db_write_latency_p95_ms",
            "P95 DB write latency for swap_ohlcv sync run",
            ["mode"],
            registry=registry,
        )
        db_batch_avg_gauge = Gauge(
            "pklpo_swap_sync_db_batch_size_avg",
            "Average DB batch size for swap_ohlcv sync run",
            ["mode"],
            registry=registry,
        )
        db_batch_max_gauge = Gauge(
            "pklpo_swap_sync_db_batch_size_max",
            "Maximum DB batch size for swap_ohlcv sync run",
            ["mode"],
            registry=registry,
        )
        adapter_init_duration_gauge = Gauge(
            "pklpo_swap_sync_adapter_init_duration_ms",
            "Duration of swap_ohlcv market adapter initialization",
            ["mode"],
            registry=registry,
        )
        adapter_init_attempts_gauge = Gauge(
            "pklpo_swap_sync_adapter_init_attempts_total",
            "Attempts used to initialize the swap_ohlcv market adapter",
            ["mode"],
            registry=registry,
        )
        adapter_init_retries_gauge = Gauge(
            "pklpo_swap_sync_adapter_init_retries_total",
            "Retries used to initialize the swap_ohlcv market adapter",
            ["mode"],
            registry=registry,
        )

        duration_gauge.labels(mode).set(float(stats.get("duration_sec", 0.0)))
        rows_gauge.labels(mode).set(float(stats.get("rows_upserted_total", 0)))
        symbols_gauge.labels(mode).set(float(stats.get("total_symbols_processed", 0)))
        errors_gauge.labels(mode).set(float(stats.get("errors_count", 0)))
        speed_gauge.labels(mode).set(float(stats.get("candles_per_second", 0.0)))
        rate_limit_gauge.labels(mode).set(float(stats.get("api_429_count", 0)))
        timeout_gauge.labels(mode).set(float(stats.get("api_timeout_count", 0)))

        db_write = stats.get("db_write", {}) or {}
        db_latency_avg_gauge.labels(mode).set(float(db_write.get("latency_avg_ms", 0.0)))
        db_latency_p95_gauge.labels(mode).set(float(db_write.get("latency_p95_ms", 0.0)))
        db_batch_avg_gauge.labels(mode).set(float(db_write.get("batch_size_avg", 0.0)))
        db_batch_max_gauge.labels(mode).set(float(db_write.get("batch_size_max", 0.0)))

        adapter_init = stats.get("adapter_init", {}) or {}
        adapter_init_duration_gauge.labels(mode).set(
            float(adapter_init.get("load_markets_duration_ms", 0.0))
        )
        adapter_init_attempts_gauge.labels(mode).set(
            float(adapter_init.get("load_markets_attempts", 0))
        )
        adapter_init_retries_gauge.labels(mode).set(
            float(adapter_init.get("load_markets_retries", 0))
        )

        pushed = _push_registry(registry, job_name="swap_ohlcv_sync")
        if pushed:
            logger.info("Swap sync metrics pushed (mode=%s)", mode)
        return pushed
    except Exception:
        logger.warning("Failed to push swap sync metrics", exc_info=True)
        return False


def push_swap_smoke_metrics(smoke: dict[str, Any]) -> bool:
    """Push swap_ohlcv smoke validation metrics to Pushgateway."""
    if not smoke:
        return False

    try:
        registry = CollectorRegistry()

        freshness_gauge = Gauge(
            "pklpo_data_freshness_lag_seconds",
            "Freshness lag in seconds derived from swap_ohlcv smoke validation",
            ["symbol", "timeframe"],
            registry=registry,
        )
        fill_rate_gauge = Gauge(
            "pklpo_swap_sync_fill_rate",
            "Funding/open interest fill rate derived from swap_ohlcv smoke validation",
            ["field"],
            registry=registry,
        )
        rows_today_gauge = Gauge(
            "pklpo_swap_sync_rows_today",
            "Rows written today in swap_ohlcv_p",
            registry=registry,
        )

        for timeframe, lag in (smoke.get("tf_lags", {}) or {}).items():
            freshness_gauge.labels("all", str(timeframe)).set(float(lag))

        if smoke.get("fr_pct") is not None:
            fill_rate_gauge.labels("funding_rate").set(float(smoke["fr_pct"]) / 100.0)
        if smoke.get("oi_pct") is not None:
            fill_rate_gauge.labels("open_interest").set(float(smoke["oi_pct"]) / 100.0)
        rows_today_gauge.set(float(smoke.get("rows_today", 0)))

        pushed = _push_registry(registry, job_name="swap_ohlcv_smoke")
        if pushed:
            logger.info("Swap smoke metrics pushed")
        return pushed
    except Exception:
        logger.warning("Failed to push swap smoke metrics", exc_info=True)
        return False
