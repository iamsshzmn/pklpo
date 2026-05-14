"""Public swap candle sync interface.

Directly wires the application layer to infrastructure adapters.
"""

from __future__ import annotations

from typing import Any

from src.candles.application.sync import (
    ExecutionMode,
    RetryPolicy,
    SyncJobRequest,
    SyncJobResult,
    refresh_instrument_catalog,
    run_candle_sync,
)
from src.candles.domain.sync_config import DEFAULT_CONFIG, SWAP_BARS, SyncConfig
from src.candles.infrastructure.adapters import build_market_data_adapter
from src.candles.instruments_service import (
    load_symbols_from_file,
    refresh_instruments_list,
    resolve_instruments_cache_file,
    resolve_repo_instruments_file,
)
from src.candles.load_instruments import load_instruments
from src.candles.observability.tracer import trace_event, trace_sync_run
from src.candles.repository import SwapCandlesRepository
from src.logging import get_logger

logger = get_logger("candles.swap_sync")


class _TracingTelemetryAdapter:
    def increment(self, metric: str, value: int | float = 1, **tags: str) -> None:
        trace_event("metric.increment", metric=metric, value=value, **tags)

    def observe(self, metric: str, value: int | float, **tags: str) -> None:
        trace_event("metric.observe", metric=metric, value=value, **tags)

    def event(self, name: str, **payload: Any) -> None:
        trace_event(name, **payload)


# ---------------------------------------------------------------------------
# Port adapters
# ---------------------------------------------------------------------------


class _MarketDataPortAdapter:
    """Adapts the concrete market adapter to the MarketDataPort protocol."""

    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter

    async def __aenter__(self) -> _MarketDataPortAdapter:
        await self._adapter.__aenter__()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._adapter.__aexit__(*exc)

    async def fetch_candles(
        self,
        *,
        instrument_id: str,
        timeframe: str = "1m",
        limit: int = 300,
        before: str | None = None,
        after: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self._adapter.get_candles(
            inst_id=instrument_id,
            bar=timeframe,
            limit=limit,
            before=before,
            after=after,
        )

    async def fetch_history_candles(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[dict[str, Any]]:
        # Dedicated historical range fetch for repair/backfill paths.
        # See CcxtOKXAdapter.get_history_candles for the root-cause note on
        # why the fast-path fetch_candles cannot be reused here.
        return await self._adapter.get_history_candles(
            inst_id=instrument_id,
            bar=timeframe,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
        )

    async def fetch_instruments(
        self, instrument_type: str = "SWAP"
    ) -> list[dict[str, Any]]:
        return await self._adapter.get_instruments(inst_type=instrument_type)

    async def fetch_funding_rates(
        self, instrument_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        return await self._adapter.get_funding_rates(instrument_ids)

    async def fetch_open_interest(
        self, instrument_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        return await self._adapter.get_open_interest(instrument_ids)


class _CandleStorePortAdapter:
    """Adapts SwapCandlesRepository → CandleStorePort protocol."""

    def __init__(self, repository: SwapCandlesRepository) -> None:
        self._repository = repository

    async def upsert_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
        additional_data: dict[str, Any],
    ) -> int:
        return await self._repository.upsert_candles(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            additional_data=additional_data,
        )

    async def get_latest_timestamp(self, *, symbol: str, timeframe: str) -> int | None:
        return await self._repository.get_latest_timestamp(
            symbol=symbol,
            timeframe=timeframe,
        )

    async def get_fill_stats(self, start_timestamp_ms: int) -> dict[str, int | float]:
        return await self._repository.get_fill_stats(start_timestamp_ms)


class _InstrumentCatalogPort:
    """Adapts SwapCandlesRepository → InstrumentCatalogPort protocol."""

    def __init__(self, repository: SwapCandlesRepository) -> None:
        self._repository = repository

    async def refresh_catalog(self) -> list[str]:
        return await refresh_instruments_list(
            repository=self._repository, logger=logger
        )

    async def load_curated_symbols(self) -> list[str]:
        repo_symbols = load_symbols_from_file(
            resolve_repo_instruments_file(), logger=logger
        )
        if repo_symbols:
            logger.info(
                "Loaded %s symbols from repo instruments list", len(repo_symbols)
            )
        return repo_symbols

    async def load_cached_symbols(self) -> list[str]:
        cache_symbols = load_symbols_from_file(
            resolve_instruments_cache_file(), logger=logger
        )
        if cache_symbols:
            logger.info("Loaded %s symbols from runtime cache", len(cache_symbols))
        return cache_symbols

    async def list_symbols(self) -> list[str]:
        return await self._repository.list_swap_symbols()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_execution_mode(value: str | None) -> ExecutionMode:
    mapping = {
        "fast": ExecutionMode.FAST,
        "slow": ExecutionMode.SLOW,
        "ext": ExecutionMode.EXTENDED,
        "bootstrap": ExecutionMode.BOOTSTRAP,
    }
    return mapping.get((value or "fast").lower(), ExecutionMode.FAST)


def _build_market_adapter(config: dict[str, Any]) -> Any:
    adapter = build_market_data_adapter(config)
    logger.info("Initialized market adapter: %s", adapter.__class__.__name__)
    return adapter


def _build_runtime_config(
    config: dict[str, Any] | SyncConfig | None
) -> tuple[SyncConfig, dict[str, Any]]:
    if isinstance(config, SyncConfig):
        validated = config
        raw_config: dict[str, Any] = {}
    else:
        raw_config = dict(config or {})
        typed_overrides = {
            field_name: raw_config[field_name]
            for field_name in SyncConfig.model_fields
            if field_name in raw_config
        }
        validated = SyncConfig.from_env(overrides=typed_overrides)

    runtime_config: dict[str, Any] = {
        **DEFAULT_CONFIG,
        **validated.model_dump(),
        **raw_config,
    }
    if runtime_config.get("timeout_seconds") is None:
        runtime_config["timeout_seconds"] = 30
    return validated, runtime_config


def _stats_from_result(result: SyncJobResult) -> dict[str, Any]:
    return {
        "total_symbols": result.total_symbols,
        "total_candles_synced": result.rows_upserted_total,
        "total_symbols_processed": result.total_symbols_processed,
        "errors_count": result.errors_count,
        "duration_seconds": result.duration_sec,
        "symbols_per_second": result.symbols_per_second,
        "candles_per_second": result.candles_per_second,
        "results_by_symbol": result.results_by_symbol,
        "endpoint_stats": result.endpoint_stats,
        "today_fill": result.today_fill,
        "db_write": result.db_write,
        "sync_run": (
            {
                "correlation_id": result.sync_run.correlation_id,
                "mode": result.sync_run.mode,
                "requested_symbols": list(result.sync_run.requested_symbols),
                "requested_timeframes": list(result.sync_run.requested_timeframes),
                "started_at": result.sync_run.started_at.isoformat(),
                "completed_at": (
                    result.sync_run.completed_at.isoformat()
                    if result.sync_run.completed_at is not None
                    else None
                ),
                "status": result.sync_run.status.value,
                "error_summary": result.sync_run.error_summary,
                "aggregate_metrics": result.sync_run.aggregate_metrics,
            }
            if result.sync_run is not None
            else None
        ),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_catalog_refresh_via_application() -> dict[str, object]:
    """Refresh instrument catalog — used by Airflow DAG."""
    repository = SwapCandlesRepository()
    await load_instruments()
    instrument_catalog = _InstrumentCatalogPort(repository)
    symbols = await refresh_instrument_catalog(instrument_catalog=instrument_catalog)
    return {
        "refreshed": True,
        "reason": "loaded",
        "symbols_count": len(symbols),
    }


async def sync_swap_candles(
    symbols: list[str] | None = None,
    timeframes: list[str] | None = None,
    config: dict[str, Any] | SyncConfig | None = None,
) -> dict[str, Any]:
    """Run candle sync using the canonical typed runtime configuration."""
    sync_config, runtime_config = _build_runtime_config(config)
    repository = SwapCandlesRepository()
    mode_str = runtime_config.get("mode")
    request = SyncJobRequest(
        mode=_resolve_execution_mode(mode_str if isinstance(mode_str, str) else None),
        symbols=tuple(symbols or ()),
        timeframes=tuple(timeframes or SWAP_BARS),
        extra_data=sync_config.extra_data,
        batch_size=sync_config.batch_size,
        max_retries=sync_config.max_retries,
        retry_delay=sync_config.retry_delay,
        max_concurrent_symbols=sync_config.max_concurrent_symbols,
        provider_id=str(runtime_config.get("adapter") or "ccxt"),
        provider_options=runtime_config,
    )

    with trace_sync_run(mode=request.mode.value, symbols_count=len(request.symbols)):
        market_adapter = _build_market_adapter(runtime_config)
        result = await run_candle_sync(
            request,
            market_data=_MarketDataPortAdapter(market_adapter),
            candle_store=_CandleStorePortAdapter(repository),
            instrument_catalog=_InstrumentCatalogPort(repository),
            retry_policy=RetryPolicy(
                max_retries=request.max_retries,
                retry_delay=request.retry_delay,
                batch_size=request.batch_size,
            ),
            telemetry=_TracingTelemetryAdapter(),
        )

    stats = _stats_from_result(result)
    if hasattr(market_adapter, "snapshot_init_metrics"):
        stats["adapter_init"] = market_adapter.snapshot_init_metrics()
    return stats


__all__ = ["run_catalog_refresh_via_application", "sync_swap_candles"]
