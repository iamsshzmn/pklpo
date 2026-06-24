from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_candles_prometheus() -> ModuleType:
    module_path = _PROJECT_ROOT / "src" / "candles" / "observability" / "prometheus.py"
    spec = importlib.util.spec_from_file_location(
        "tests.pklpo_platform._candles_prometheus",
        module_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_observability_facade_reexports_existing_implementations() -> None:
    facade = importlib.import_module("src.pklpo_platform.observability")

    from src.logging import get_logger, set_log_context
    from src.logging.tracing import (
        configure_tracing,
        get_trace_ids,
        set_span_attributes,
        start_span,
    )

    prometheus = _load_candles_prometheus()

    assert facade.get_logger is get_logger
    assert facade.set_log_context is set_log_context
    assert facade.configure_tracing is configure_tracing
    assert facade.get_trace_ids is get_trace_ids
    assert facade.set_span_attributes is set_span_attributes
    assert facade.start_span is start_span
    assert facade.push_swap_sync_metrics.__code__.co_filename == str(
        Path(prometheus.push_swap_sync_metrics.__code__.co_filename)
    )
    assert facade.push_swap_repair_metrics.__code__.co_filename == str(
        Path(prometheus.push_swap_repair_metrics.__code__.co_filename)
    )
    assert callable(facade.airflow_log_context)


def test_observability_facade_import_avoids_heavy_side_effect_modules() -> None:
    for module_name in (
        "src.candles.infrastructure.database",
        "src.candles.infrastructure.logging_config",
        "src.database",
        "opentelemetry.sdk.trace",
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
    ):
        sys.modules.pop(module_name, None)

    importlib.import_module("src.pklpo_platform.observability")

    assert "src.candles.infrastructure.database" not in sys.modules
    assert "src.candles.infrastructure.logging_config" not in sys.modules
    assert "src.database" not in sys.modules
    assert "opentelemetry.sdk.trace" not in sys.modules
    assert "opentelemetry.exporter.otlp.proto.grpc.trace_exporter" not in sys.modules
