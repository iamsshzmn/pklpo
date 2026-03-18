"""Infrastructure exports for the unified ``src.candles`` module."""

from .adapters import build_market_data_adapter, resolve_adapter_name
from .aggregator import MarketDataAggregator
from .client import OKXClient
from .config import MarketMetaConfig, get_config
from .data_loader import MarketDataLoader
from .database import MarketDataExt, MarketDataExtRepository, MarketMetadata as MarketMetadataDB, RiskLimits as RiskLimitsDB, ValidationCache, ValidationLog, create_tables, drop_tables
from .extra_data import ExtraDataFetcher
from .logging_config import LOGGER_NAME, configure_logging, get_logger, log_validation_result
from .market import OKXMarket
from .metrics import MetricsCollector, MetricsExporter, MetricsMonitor, get_metrics_collector, measure_async_time, measure_time
from .normalizer import MarketDataNormalizer
from .ohlcv_aligner import OHLCVAligner
from .okx_integration import OKXMetadataLoader
from .orders import OKXOrders
from .quality_repository import QualityMetricsRepository
from .raw_ingest import RawIngestor, compute_payload_hash
from .reprocess import ReprocessConf, RunWindowResult, ceil_to_tf, filter_symbols, floor_to_tf, get_run_window, maybe_update_watermark, parse_dag_conf
from .retention import MarketDataExtRetention
from .sync_state import SyncStateManager

__all__ = [name for name in globals() if not name.startswith("_")]
