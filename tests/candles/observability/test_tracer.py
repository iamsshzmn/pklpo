from __future__ import annotations

import importlib.util
import json
import logging
from io import StringIO
from pathlib import Path

from src.logging.context import ContextFilter, get_current_run_id
from src.logging.formatters import JsonFormatter

_TRACER_PATH = (
    Path(__file__).parents[3] / "src" / "candles" / "observability" / "tracer.py"
)
_TRACER_SPEC = importlib.util.spec_from_file_location(
    "test_candles_tracer", _TRACER_PATH
)
assert _TRACER_SPEC is not None
assert _TRACER_SPEC.loader is not None
tracer = importlib.util.module_from_spec(_TRACER_SPEC)
_TRACER_SPEC.loader.exec_module(tracer)


def test_trace_sync_run_sets_structured_run_id() -> None:
    with tracer.trace_sync_run(
        mode="fast",
        symbols_count=2,
        run_id="manual__2026-06-09T00:00:00+00:00",
    ) as run_id:
        assert run_id == "manual__2026-06-09T00:00:00+00:00"
        assert get_current_run_id() == "manual__2026-06-09T00:00:00+00:00"
        assert tracer.get_correlation_id() == "manual__2026-06-09T00:00:00+00:00"
        assert tracer.get_trace_context() == {
            "run_id": "manual__2026-06-09T00:00:00+00:00",
            "mode": "fast",
            "symbols_count": "2",
            "trace_id": "-",
            "span_id": "-",
        }

    assert get_current_run_id() is None


def test_correlation_log_filter_uses_run_id_field() -> None:
    record = logging.LogRecord(
        name="src.candles",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="test",
        args=(),
        exc_info=None,
    )

    with tracer.trace_sync_run(mode="fast", symbols_count=1, run_id="run-123"):
        assert tracer.CorrelationLogFilter().filter(record)

    assert record.run_id == "run-123"
    assert record.correlation_id == "run-123"


def test_trace_event_reaches_pklpo_json_with_structured_fields() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(ContextFilter())
    handler.setFormatter(JsonFormatter())

    pklpo_logger = logging.getLogger("pklpo")
    original_handlers = list(pklpo_logger.handlers)
    original_filters = list(pklpo_logger.filters)
    original_level = pklpo_logger.level
    original_propagate = pklpo_logger.propagate
    pklpo_logger.handlers = [handler]
    pklpo_logger.filters = []
    pklpo_logger.setLevel(logging.INFO)
    pklpo_logger.propagate = False
    try:
        with tracer.trace_sync_run(
            mode="fast",
            symbols_count=1,
            run_id="run-json-123",
        ):
            tracer.trace_event(
                "sync_started",
                component="swap_sync",
                task_id="load_symbols",
                symbol="BTC-USDT-SWAP",
                timeframe="1m",
                duration_ms=12,
            )
    finally:
        pklpo_logger.handlers = original_handlers
        pklpo_logger.filters = original_filters
        pklpo_logger.setLevel(original_level)
        pklpo_logger.propagate = original_propagate

    records = [
        json.loads(line)
        for line in stream.getvalue().splitlines()
        if '"event": "sync_started"' in line
    ]

    assert records == [
        {
            "timestamp": records[0]["timestamp"],
            "level": "INFO",
            "component": "swap_sync",
            "message": "sync_started",
            "run_id": "run-json-123",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "trace_id": "-",
            "span_id": "-",
            "error_type": "-",
            "category": "-",
            "event": "sync_started",
            "task_id": "load_symbols",
            "duration_ms": 12,
        }
    ]
