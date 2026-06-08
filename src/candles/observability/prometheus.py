"""
Prometheus metrics push helpers for candles pipelines.

Supports:
- quality pipeline metrics
- swap_ohlcv sync runtime metrics
- swap_ohlcv smoke validation metrics
- swap repair validated result metrics
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
        db_latency_avg_gauge.labels(mode).set(
            float(db_write.get("latency_avg_ms", 0.0))
        )
        db_latency_p95_gauge.labels(mode).set(
            float(db_write.get("latency_p95_ms", 0.0))
        )
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


def push_feature_eligibility_metrics(snapshot: dict[str, Any]) -> bool:
    """Push feature eligibility materialized-state metrics."""
    if not snapshot:
        return False

    try:
        registry = CollectorRegistry()
        state_counts_gauge = Gauge(
            "pklpo_feature_eligibility_symbols",
            "Feature eligibility symbols by timeframe and state",
            ["timeframe", "state"],
            registry=registry,
        )
        eligible_total_gauge = Gauge(
            "pklpo_feature_eligible_total",
            "Feature-eligible symbols by timeframe",
            ["timeframe"],
            registry=registry,
        )
        transitions_total = Counter(
            "pklpo_feature_eligibility_transitions_total",
            "Feature eligibility state transitions",
            ["from_state", "to_state"],
            registry=registry,
        )
        lost_gauge = Gauge(
            "pklpo_feature_eligibility_lost",
            "Symbols that lost eligibility by timeframe",
            ["timeframe"],
            registry=registry,
        )
        invalid_total_gauge = Gauge(
            "pklpo_feature_eligibility_invalid_total",
            "Feature eligibility invalid_history count",
            registry=registry,
        )
        stale_seconds_gauge = Gauge(
            "pklpo_feature_eligibility_stale_seconds",
            "Seconds since the latest feature eligibility evaluation",
            registry=registry,
        )

        for (timeframe, state), count in (snapshot.get("state_counts") or {}).items():
            state_counts_gauge.labels(str(timeframe), str(state)).set(float(count))
        for timeframe, count in (snapshot.get("eligible_counts") or {}).items():
            eligible_total_gauge.labels(str(timeframe)).set(float(count))

        lost_counts: dict[str, int] = {}
        for transition in snapshot.get("transitions") or []:
            from_state = str(transition.get("from_state") or "none")
            to_state = str(transition.get("to_state") or "none")
            timeframe = str(transition.get("timeframe") or "")
            transitions_total.labels(from_state, to_state).inc()
            if from_state == "eligible" and to_state in {
                "incomplete_history",
                "invalid_history",
            }:
                lost_counts[timeframe] = lost_counts.get(timeframe, 0) + 1
        for timeframe, count in lost_counts.items():
            lost_gauge.labels(timeframe).set(float(count))

        invalid_total_gauge.set(float(snapshot.get("invalid_total", 0)))
        stale_seconds_gauge.set(float(snapshot.get("stale_seconds", 0.0)))
        pushed = _push_registry(registry, job_name="feature_eligibility")
        if pushed:
            logger.info("Feature eligibility metrics pushed")
        return pushed
    except Exception:
        logger.warning("Failed to push feature eligibility metrics", exc_info=True)
        return False


def push_pipeline_monitoring_metrics(snapshot: dict[str, Any]) -> bool:
    """Push read-only pipeline monitoring snapshot metrics."""
    if not snapshot:
        return False

    try:
        registry = CollectorRegistry()
        candle_lag_gauge = Gauge(
            "pklpo_pipeline_candle_lag_seconds",
            "Lag in seconds between now and latest candle by timeframe",
            ["timeframe"],
            registry=registry,
        )
        recalc_queue_gauge = Gauge(
            "pklpo_pipeline_recalc_queue_rows",
            "Indicator recalculation queue rows by status",
            ["status"],
            registry=registry,
        )
        bootstrap_state_gauge = Gauge(
            "pklpo_pipeline_bootstrap_state_rows",
            "Bootstrap state rows by status",
            ["status"],
            registry=registry,
        )
        eligibility_state_gauge = Gauge(
            "pklpo_pipeline_eligibility_state_rows",
            "Feature eligibility rows by timeframe and state",
            ["timeframe", "state"],
            registry=registry,
        )
        alerts_gauge = Gauge(
            "pklpo_pipeline_alerts",
            "Read-only monitoring alerts by severity",
            ["severity"],
            registry=registry,
        )

        for timeframe, lag in (snapshot.get("candle_lag_seconds") or {}).items():
            candle_lag_gauge.labels(str(timeframe)).set(float(lag))
        for status, count in (snapshot.get("recalc_queue") or {}).items():
            recalc_queue_gauge.labels(str(status)).set(float(count))
        for status, count in (snapshot.get("bootstrap_state") or {}).items():
            bootstrap_state_gauge.labels(str(status)).set(float(count))
        eligibility_state = snapshot.get("eligibility_state") or []
        if isinstance(eligibility_state, dict):
            eligibility_state_rows: list[dict[str, Any]] = [
                {"timeframe": timeframe, "state": state, "count": count}
                for (timeframe, state), count in eligibility_state.items()
            ]
        else:
            eligibility_state_rows = list(eligibility_state)
        for row in eligibility_state_rows:
            eligibility_state_gauge.labels(
                str(row["timeframe"]),
                str(row["state"]),
            ).set(float(row["count"]))
        for severity, count in (snapshot.get("alerts") or {}).items():
            alerts_gauge.labels(str(severity)).set(float(count))

        pushed = _push_registry(registry, job_name="pipeline_monitoring")
        if pushed:
            logger.info("Pipeline monitoring metrics pushed")
        return pushed
    except Exception:
        logger.warning("Failed to push pipeline monitoring metrics", exc_info=True)
        return False


def push_swap_repair_metrics(payloads: list[dict[str, Any]] | dict[str, Any]) -> bool:
    """Push validated swap repair results to Prometheus Pushgateway."""
    if not payloads:
        return False

    normalized = payloads if isinstance(payloads, list) else [payloads]
    try:
        registry = CollectorRegistry()
        label_names = ["symbol", "timeframe", "mode", "strategy"]

        rows_written_gauge = Gauge(
            "pklpo_swap_repair_rows_written",
            "Rows written during a validated swap repair run",
            label_names,
            registry=registry,
        )
        gap_tasks_gauge = Gauge(
            "pklpo_swap_repair_gap_tasks",
            "Planned gap tasks for a validated swap repair run",
            label_names,
            registry=registry,
        )
        requested_bars_gauge = Gauge(
            "pklpo_swap_repair_requested_bars",
            "Requested bars for a validated swap repair run",
            label_names,
            registry=registry,
        )
        remaining_gap_tasks_gauge = Gauge(
            "pklpo_swap_repair_remaining_gap_tasks",
            "Remaining gap tasks after a validated swap repair run",
            label_names,
            registry=registry,
        )
        remaining_requested_bars_gauge = Gauge(
            "pklpo_swap_repair_remaining_requested_bars",
            "Remaining requested bars after a validated swap repair run",
            label_names,
            registry=registry,
        )
        verified_gauge = Gauge(
            "pklpo_swap_repair_verified",
            "Whether a validated swap repair result is fully verified (1/0)",
            label_names,
            registry=registry,
        )
        auto_apply_incomplete_gauge = Gauge(
            "pklpo_swap_repair_auto_apply_incomplete",
            "Whether a validated swap repair result is an incomplete auto-apply (1/0)",
            label_names,
            registry=registry,
        )
        received_bars_gauge = Gauge(
            "pklpo_swap_repair_received_bars",
            "Bars received from OKX across all iterations of a repair run",
            label_names,
            registry=registry,
        )
        progress_gauge = Gauge(
            "pklpo_swap_repair_progress",
            "Net reduction in missing timestamps for a repair run",
            label_names,
            registry=registry,
        )
        api_fill_ratio_gauge = Gauge(
            "pklpo_swap_repair_api_fill_ratio",
            "Fraction of requested bars the exchange actually returned (received/requested)",
            label_names,
            registry=registry,
        )
        write_success_ratio_gauge = Gauge(
            "pklpo_swap_repair_write_success_ratio",
            "Fraction of received bars that were written to the store (written/received)",
            label_names,
            registry=registry,
        )
        remaining_missing_before_gauge = Gauge(
            "pklpo_swap_repair_remaining_missing_before",
            "Missing timestamps in window before the repair run",
            label_names,
            registry=registry,
        )
        remaining_missing_after_gauge = Gauge(
            "pklpo_swap_repair_remaining_missing_after",
            "Missing timestamps in window after the repair run",
            label_names,
            registry=registry,
        )
        outcome_total_gauge = Gauge(
            "pklpo_swap_repair_outcome_total",
            "Count of repair run outcomes by classification",
            [*label_names, "outcome"],
            registry=registry,
        )
        blocked_gauge = Gauge(
            "pklpo_swap_repair_blocked",
            "Whether a validated swap repair result ended in a blocked empty-chunk state (1/0)",
            label_names,
            registry=registry,
        )
        blocked_reason_total_gauge = Gauge(
            "pklpo_swap_repair_blocked_reason_total",
            "Count of blocked repair results by blocked reason",
            [*label_names, "blocked_reason"],
            registry=registry,
        )
        blocked_cause_total_gauge = Gauge(
            "pklpo_swap_repair_blocked_cause_total",
            "Count of blocked repair results by blocked cause",
            [*label_names, "blocked_cause"],
            registry=registry,
        )
        last200_pairs_checked_total = Counter(
            "pklpo_last200_pairs_checked_total",
            "Pairs checked by the last-200 closed-bars guard",
            ["timeframe"],
            registry=registry,
        )
        last200_pairs_ok_total = Counter(
            "pklpo_last200_pairs_ok_total",
            "Pairs that ended ok in the last-200 closed-bars guard",
            ["timeframe"],
            registry=registry,
        )
        last200_missing_bars_total = Counter(
            "pklpo_last200_missing_bars_total",
            "Bars requiring repair attention in the last-200 guard before final verification",
            ["timeframe"],
            registry=registry,
        )
        last200_corrupted_bars_total = Counter(
            "pklpo_last200_corrupted_bars_total",
            "Corrupted bars detected by the last-200 guard",
            ["timeframe"],
            registry=registry,
        )
        last200_remaining_after_total = Counter(
            "pklpo_last200_remaining_after_total",
            "Bars still unresolved after the last-200 guard run",
            ["timeframe", "status"],
            registry=registry,
        )
        last200_indicator_recalc_enqueued_total = Counter(
            "pklpo_last200_indicator_recalc_enqueued_total",
            "Feature recalculation ranges enqueued by the last-200 guard",
            ["timeframe"],
            registry=registry,
        )

        for payload in normalized:
            labels = (
                str(payload.get("symbol", "")),
                str(payload.get("timeframe", "")),
                str(payload.get("mode", "")),
                str(payload.get("strategy", "")),
            )
            rows_written_gauge.labels(*labels).set(
                float(payload.get("rows_written", 0))
            )
            gap_tasks_gauge.labels(*labels).set(float(payload.get("gap_tasks", 0)))
            requested_bars_gauge.labels(*labels).set(
                float(payload.get("requested_bars", 0))
            )
            remaining_gap_tasks_gauge.labels(*labels).set(
                float(payload.get("remaining_gap_tasks", 0))
            )
            remaining_requested_bars_gauge.labels(*labels).set(
                float(payload.get("remaining_requested_bars", 0))
            )
            verified_gauge.labels(*labels).set(1.0 if payload.get("verified") else 0.0)
            auto_apply_incomplete_gauge.labels(*labels).set(
                1.0 if payload.get("auto_apply_incomplete") else 0.0
            )
            received_bars_gauge.labels(*labels).set(
                float(payload.get("received_bars", 0))
            )
            progress_gauge.labels(*labels).set(float(payload.get("progress", 0)))
            api_fill_ratio_gauge.labels(*labels).set(
                float(payload.get("api_fill_ratio", 0.0))
            )
            write_success_ratio_gauge.labels(*labels).set(
                float(payload.get("write_success_ratio", 0.0))
            )
            remaining_missing_before_gauge.labels(*labels).set(
                float(payload.get("remaining_missing_before", 0))
            )
            remaining_missing_after_gauge.labels(*labels).set(
                float(payload.get("remaining_missing_after", 0))
            )
            blocked = bool(payload.get("blocked", False))
            blocked_gauge.labels(*labels).set(1.0 if blocked else 0.0)
            blocked_reason = payload.get("blocked_reason")
            if blocked_reason is not None:
                blocked_reason_total_gauge.labels(*labels, str(blocked_reason)).inc()
            blocked_cause = payload.get("blocked_cause")
            if blocked_cause is not None:
                blocked_cause_total_gauge.labels(*labels, str(blocked_cause)).inc()
            outcome_value = payload.get("outcome")
            if outcome_value is not None:
                outcome_total_gauge.labels(*labels, str(outcome_value)).inc()
            if str(payload.get("strategy", "")) == "last_n_closed_bars":
                timeframe = str(payload.get("timeframe", ""))
                status = str(payload.get("status", "unknown"))
                unresolved = list(payload.get("unresolved_timestamps", []))
                missing_before = int(payload.get("repaired_count", 0)) + len(unresolved)
                last200_pairs_checked_total.labels(timeframe).inc()
                if status == "ok":
                    last200_pairs_ok_total.labels(timeframe).inc()
                if missing_before > 0:
                    last200_missing_bars_total.labels(timeframe).inc(missing_before)
                corrupted = int(payload.get("corrupted_count", 0))
                if corrupted > 0:
                    last200_corrupted_bars_total.labels(timeframe).inc(corrupted)
                if unresolved:
                    last200_remaining_after_total.labels(timeframe, status).inc(
                        len(unresolved)
                    )
                if status == "ok" and payload.get("affected_recalc_range") is not None:
                    last200_indicator_recalc_enqueued_total.labels(timeframe).inc()

        pushed = _push_registry(registry, job_name="swap_repair_v1")
        if pushed:
            logger.info("Swap repair metrics pushed (%d payloads)", len(normalized))
        return pushed
    except Exception:
        logger.warning("Failed to push swap repair metrics", exc_info=True)
        return False
