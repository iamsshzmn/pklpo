from __future__ import annotations

from src.candles.application.sync import (
    ExecutionMode,
    RetryPolicy,
    SyncJobRequest,
    refresh_instrument_catalog,
    run_candle_sync,
)
from src.candles.infrastructure.runtime_adapters import (
    LegacyCandleStorePortAdapter,
    LegacyInstrumentCatalogPort,
    LegacyMarketDataPortAdapter,
    build_runtime_market_adapter,
    legacy_stats_from_result,
)
from src.candles.repository import SwapCandlesRepository


def resolve_execution_mode(value: str | None) -> ExecutionMode:
    mapping = {
        "fast": ExecutionMode.FAST,
        "slow": ExecutionMode.SLOW,
        "ext": ExecutionMode.EXTENDED,
        "bootstrap": ExecutionMode.BOOTSTRAP,
    }
    return mapping.get((value or "fast").lower(), ExecutionMode.FAST)


async def run_catalog_refresh_via_application() -> dict[str, object]:
    repository = SwapCandlesRepository()
    instrument_catalog = LegacyInstrumentCatalogPort(repository)
    symbols = await refresh_instrument_catalog(instrument_catalog=instrument_catalog)
    return {
        "refreshed": True,
        "reason": "loaded",
        "symbols_count": len(symbols),
    }


async def run_sync_via_application(
    *,
    symbols: list[str] | None,
    timeframes: list[str] | None,
    config: dict[str, object],
    default_timeframes: list[str],
) -> dict[str, object]:
    repository = SwapCandlesRepository()
    market_adapter = build_runtime_market_adapter(dict(config))
    request = SyncJobRequest(
        mode=resolve_execution_mode(config.get("mode") if isinstance(config.get("mode"), str) else None),
        symbols=tuple(symbols or ()),
        timeframes=tuple(timeframes or default_timeframes),
        extra_data=bool(config.get("extra_data", False)),
        batch_size=int(config.get("batch_size", 300)),
        max_retries=int(config.get("max_retries", 3)),
        retry_delay=float(config.get("retry_delay", 1.0)),
        max_concurrent_symbols=int(config.get("max_concurrent_symbols", 1)),
        provider_id=str(config.get("adapter") or "default"),
        provider_options=dict(config),
    )
    result = await run_candle_sync(
        request,
        market_data=LegacyMarketDataPortAdapter(market_adapter),
        candle_store=LegacyCandleStorePortAdapter(repository),
        instrument_catalog=LegacyInstrumentCatalogPort(repository),
        retry_policy=RetryPolicy(
            max_retries=request.max_retries,
            retry_delay=request.retry_delay,
            batch_size=request.batch_size,
        ),
    )
    return legacy_stats_from_result(result)
