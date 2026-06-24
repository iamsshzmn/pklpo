from __future__ import annotations

import importlib.util
import json
import logging
from io import StringIO
from pathlib import Path

from src.logging.context import ContextFilter
from src.logging.formatters import JsonFormatter

_TRACER_PATH = Path(__file__).parents[3] / "src" / "candles" / "observability" / "tracer.py"
_TRACER_SPEC = importlib.util.spec_from_file_location(
    "test_event_json_delivery_tracer",
    _TRACER_PATH,
)
assert _TRACER_SPEC is not None
assert _TRACER_SPEC.loader is not None
tracer = importlib.util.module_from_spec(_TRACER_SPEC)
_TRACER_SPEC.loader.exec_module(tracer)


def _capture_pklpo_json_logs() -> tuple[
    StringIO,
    logging.Logger,
    list[logging.Handler],
    list[logging.Filter],
    int,
    bool,
]:
    pklpo_logger = logging.getLogger("pklpo")
    original_handlers = list(pklpo_logger.handlers)
    original_filters = list(pklpo_logger.filters)
    original_level = pklpo_logger.level
    original_propagate = pklpo_logger.propagate

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(ContextFilter())
    handler.setFormatter(JsonFormatter())

    pklpo_logger.handlers = [handler]
    pklpo_logger.filters = []
    pklpo_logger.setLevel(logging.INFO)
    pklpo_logger.propagate = False
    return (
        stream,
        pklpo_logger,
        original_handlers,
        original_filters,
        original_level,
        original_propagate,
    )


def test_telemetry_event_reaches_pklpo_json_handler_with_top_level_fields() -> None:
    (
        stream,
        pklpo_logger,
        original_handlers,
        original_filters,
        original_level,
        original_propagate,
    ) = _capture_pklpo_json_logs()
    try:
        with tracer.trace_sync_run(mode="fast", symbols_count=1, run_id="run-json-456"):
            tracer.trace_event(
                "sync_started",
                component="swap_sync",
                task_id="sync_task",
                symbol="BTC-USDT-SWAP",
                timeframe="1m",
            )
    finally:
        pklpo_logger.handlers = original_handlers
        pklpo_logger.filters = original_filters
        pklpo_logger.setLevel(original_level)
        pklpo_logger.propagate = original_propagate

    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    sync_started = [record for record in records if record.get("event") == "sync_started"]

    assert sync_started == [
        {
            "timestamp": sync_started[0]["timestamp"],
            "level": "INFO",
            "component": "swap_sync",
            "message": "sync_started",
            "run_id": "run-json-456",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "trace_id": "-",
            "span_id": "-",
            "error_type": "-",
            "category": "-",
            "event": "sync_started",
            "task_id": "sync_task",
        }
    ]


def test_failure_event_json_has_error_type_and_traceback() -> None:
    (
        stream,
        pklpo_logger,
        original_handlers,
        original_filters,
        original_level,
        original_propagate,
    ) = _capture_pklpo_json_logs()
    try:
        with tracer.trace_sync_run(mode="fast", symbols_count=1, run_id="run-json-789"):
            try:
                raise RuntimeError("write failed")
            except RuntimeError:
                tracer.trace_event(
                    "upsert_failed",
                    component="swap_sync",
                    symbol="BTC-USDT-SWAP",
                    timeframe="1m",
                    error="write failed",
                    error_type="unexpected_error",
                    exc_info=True,
                )
    finally:
        pklpo_logger.handlers = original_handlers
        pklpo_logger.filters = original_filters
        pklpo_logger.setLevel(original_level)
        pklpo_logger.propagate = original_propagate

    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    upsert_failed = [record for record in records if record.get("event") == "upsert_failed"]

    assert len(upsert_failed) == 1
    assert upsert_failed[0]["level"] == "ERROR"
    assert upsert_failed[0]["run_id"] == "run-json-789"
    assert upsert_failed[0]["symbol"] == "BTC-USDT-SWAP"
    assert upsert_failed[0]["timeframe"] == "1m"
    assert upsert_failed[0]["trace_id"] == "-"
    assert upsert_failed[0]["span_id"] == "-"
    assert upsert_failed[0]["event"] == "upsert_failed"
    assert upsert_failed[0]["error_type"] == "unexpected_error"
    assert "RuntimeError: write failed" in upsert_failed[0]["exception"]
