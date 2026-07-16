"""Observability helpers for identity build jobs."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

ALLOWED_IDENTITY_METRIC_LABELS = {
    "series_id",
    "timeframe",
    "component",
    "status",
    "error_type",
}

IDENTITY_PROMETHEUS_METRICS = {
    "pklpo_identity_build_duration_seconds": {
        "type": "histogram",
        "labels": ("series_id", "timeframe", "component", "status", "error_type"),
    },
    "pklpo_identity_build_rows_total": {
        "type": "gauge",
        "labels": ("series_id", "timeframe", "component", "status", "error_type"),
    },
    "pklpo_identity_build_errors_total": {
        "type": "counter",
        "labels": ("series_id", "timeframe", "component", "status", "error_type"),
    },
    "pklpo_identity_build_gap_count": {
        "type": "gauge",
        "labels": ("series_id", "timeframe", "component", "status", "error_type"),
    },
}


def error_message_hash(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()


@dataclass
class IdentityBuildObserver:
    """Structured logs and bounded-label metrics for identity builds."""

    events: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)

    def metric_labels(
        self,
        *,
        status: str,
        error_type: str = "none",
        series_id: str = "*",
        timeframe: str = "*",
        **_: Any,
    ) -> dict[str, str]:
        return {
            "series_id": series_id,
            "timeframe": timeframe,
            "component": "identity_build",
            "status": status,
            "error_type": error_type,
        }

    def start(self, *, run_id: str, as_of: Any) -> float:
        started = time.perf_counter()
        event = {
            "component": "identity_build",
            "stage": "start",
            "status": "running",
            "run_id": run_id,
            "as_of": str(as_of),
        }
        self.events.append(event)
        logger.info("identity_build start", extra=event)
        return started

    def success(
        self,
        *,
        run_id: str,
        started: float,
        rows_read: int,
        rows_written: int,
        gap_count: int,
    ) -> None:
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        event = {
            "component": "identity_build",
            "stage": "finish",
            "status": "success",
            "run_id": run_id,
            "rows_read": rows_read,
            "rows_written": rows_written,
            "gap_count": gap_count,
            "duration_ms": duration_ms,
        }
        self.events.append(event)
        self.metrics.append(
            {
                "labels": self.metric_labels(status="success"),
                "duration_ms": duration_ms,
                "rows_read": rows_read,
                "rows_written": rows_written,
                "gap_count": gap_count,
                "errors": 0,
            }
        )
        logger.info("identity_build success", extra=event)

    def failure(self, *, run_id: str, started: float, exc: BaseException) -> str:
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        error_type = type(exc).__name__
        error_hash = error_message_hash(str(exc))
        event = {
            "component": "identity_build",
            "stage": "finish",
            "status": "failed",
            "run_id": run_id,
            "duration_ms": duration_ms,
            "error_type": error_type,
            "error_message_hash": error_hash,
            "exception_class": error_type,
            "retryable": False,
        }
        self.events.append(event)
        self.metrics.append(
            {
                "labels": self.metric_labels(status="failed", error_type=error_type),
                "duration_ms": duration_ms,
                "rows_read": 0,
                "rows_written": 0,
                "gap_count": 0,
                "errors": 1,
            }
        )
        logger.error("identity_build failed", extra=event)
        return error_hash


ALLOWED_CONTINUOUS_BUILD_METRIC_LABELS = {
    "series_id",
    "timeframe",
    "component",
    "status",
    "error_type",
}

CONTINUOUS_BUILD_PROMETHEUS_METRICS = {
    "pklpo_continuous_build_duration_seconds": {
        "type": "histogram",
        "labels": ("series_id", "timeframe", "component", "status", "error_type"),
    },
    "pklpo_continuous_build_rows_total": {
        "type": "gauge",
        "labels": ("series_id", "timeframe", "component", "status", "error_type"),
    },
    "pklpo_continuous_build_errors_total": {
        "type": "counter",
        "labels": ("series_id", "timeframe", "component", "status", "error_type"),
    },
    "pklpo_continuous_build_segment_count": {
        "type": "gauge",
        "labels": ("series_id", "timeframe", "component", "status", "error_type"),
    },
    "pklpo_continuous_build_gap_count": {
        "type": "gauge",
        "labels": ("series_id", "timeframe", "component", "status", "error_type"),
    },
}


@dataclass
class ContinuousBuildObserver:
    """Structured logs and bounded-label metrics for the continuous OHLCV
    build job (§17.4 'continuous build' row) — same shape/discipline as
    `IdentityBuildObserver`, kept in this module because both jobs live in
    the same identity bounded context, but a distinct `component` label
    (`continuous_build`, not `identity_build`) so the two jobs are never
    conflated in Grafana/Loki queries filtered by `run_id`+`component`."""

    events: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)

    def metric_labels(
        self,
        *,
        status: str,
        error_type: str = "none",
        series_id: str = "*",
        timeframe: str = "*",
        **_: Any,
    ) -> dict[str, str]:
        return {
            "series_id": series_id,
            "timeframe": timeframe,
            "component": "continuous_build",
            "status": status,
            "error_type": error_type,
        }

    def start(self, *, run_id: str, as_of: Any) -> float:
        started = time.perf_counter()
        event = {
            "component": "continuous_build",
            "stage": "start",
            "status": "running",
            "run_id": run_id,
            "as_of": str(as_of),
        }
        self.events.append(event)
        logger.info("continuous_build start", extra=event)
        return started

    def success(
        self,
        *,
        run_id: str,
        started: float,
        rows_written: int,
        segment_count: int,
        gap_count: int,
    ) -> None:
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        event = {
            "component": "continuous_build",
            "stage": "finish",
            "status": "success",
            "run_id": run_id,
            "rows_written": rows_written,
            "segment_count": segment_count,
            "gap_count": gap_count,
            "duration_ms": duration_ms,
        }
        self.events.append(event)
        self.metrics.append(
            {
                "labels": self.metric_labels(status="success"),
                "duration_ms": duration_ms,
                "rows_written": rows_written,
                "segment_count": segment_count,
                "gap_count": gap_count,
                "errors": 0,
            }
        )
        logger.info("continuous_build success", extra=event)

    def failure(self, *, run_id: str, started: float, exc: BaseException) -> str:
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        error_type = type(exc).__name__
        error_hash = error_message_hash(str(exc))
        event = {
            "component": "continuous_build",
            "stage": "finish",
            "status": "failed",
            "run_id": run_id,
            "duration_ms": duration_ms,
            "error_type": error_type,
            "error_message_hash": error_hash,
            "exception_class": error_type,
            "retryable": False,
        }
        self.events.append(event)
        self.metrics.append(
            {
                "labels": self.metric_labels(status="failed", error_type=error_type),
                "duration_ms": duration_ms,
                "rows_written": 0,
                "segment_count": 0,
                "gap_count": 0,
                "errors": 1,
            }
        )
        logger.error("continuous_build failed", extra=event)
        return error_hash
