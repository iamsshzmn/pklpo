"""Lazy infrastructure exports for the unified ``src.candles`` module."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "ExtraDataFetcher": ".extra_data",
    "LOGGER_NAME": ".logging_config",
    "MarketDataAggregator": ".aggregator",
    "MarketDataExt": ".database",
    "MarketDataExtRepository": ".database",
    "MarketDataExtRetention": ".retention",
    "MarketDataLoader": ".data_loader",
    "MarketDataNormalizer": ".normalizer",
    "MarketMetaConfig": ".config",
    "MarketMetadataDB": ".database",
    "MetricsCollector": ".metrics",
    "MetricsExporter": ".metrics",
    "MetricsMonitor": ".metrics",
    "OHLCVAligner": ".ohlcv_aligner",
    "OKXClient": ".client",
    "OKXMarket": ".market",
    "OKXMetadataLoader": ".okx_integration",
    "OKXOrders": ".orders",
    "QualityMetricsRepository": ".quality_repository",
    "RawIngestor": ".raw_ingest",
    "ReprocessConf": ".reprocess",
    "RiskLimitsDB": ".database",
    "RunWindowResult": ".reprocess",
    "SyncStateManager": ".sync_state",
    "ValidationCache": ".database",
    "ValidationLog": ".database",
    "build_market_data_adapter": ".adapters",
    "ceil_to_tf": ".reprocess",
    "compute_payload_hash": ".raw_ingest",
    "configure_logging": ".logging_config",
    "create_tables": ".database",
    "drop_tables": ".database",
    "filter_symbols": ".reprocess",
    "floor_to_tf": ".reprocess",
    "get_config": ".config",
    "get_logger": ".logging_config",
    "get_metrics_collector": ".metrics",
    "get_run_window": ".reprocess",
    "log_validation_result": ".logging_config",
    "maybe_update_watermark": ".reprocess",
    "measure_async_time": ".metrics",
    "measure_time": ".metrics",
    "parse_dag_conf": ".reprocess",
    "resolve_adapter_name": ".adapters",
}

__all__ = [
    "LOGGER_NAME",
    "ExtraDataFetcher",
    "MarketDataAggregator",
    "MarketDataExt",
    "MarketDataExtRepository",
    "MarketDataExtRetention",
    "MarketDataLoader",
    "MarketDataNormalizer",
    "MarketMetaConfig",
    "MarketMetadataDB",
    "MetricsCollector",
    "MetricsExporter",
    "MetricsMonitor",
    "OHLCVAligner",
    "OKXClient",
    "OKXMarket",
    "OKXMetadataLoader",
    "OKXOrders",
    "QualityMetricsRepository",
    "RawIngestor",
    "ReprocessConf",
    "RiskLimitsDB",
    "RunWindowResult",
    "SyncStateManager",
    "ValidationCache",
    "ValidationLog",
    "build_market_data_adapter",
    "ceil_to_tf",
    "compute_payload_hash",
    "configure_logging",
    "create_tables",
    "drop_tables",
    "filter_symbols",
    "floor_to_tf",
    "get_config",
    "get_logger",
    "get_metrics_collector",
    "get_run_window",
    "log_validation_result",
    "maybe_update_watermark",
    "measure_async_time",
    "measure_time",
    "parse_dag_conf",
    "resolve_adapter_name",
]


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_EXPORTS[name], __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
