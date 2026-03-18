from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from src.candles.infrastructure.adapters import build_market_data_adapter
from src.candles.instruments_service import (
    refresh_instruments_list,
    resolve_instruments_cache_file,
)
from src.logging import get_logger

if TYPE_CHECKING:
    from src.candles.application.sync import SyncJobResult
    from src.candles.ports import (
        CandleStorePort,
        InstrumentCatalogQueryPort,
        MarketDataAdapterPort,
    )

logger = get_logger("candles.runtime_adapters")


class UnavailableMarketDataAdapter:
    """Adapter placeholder used when no runtime adapter can be initialized."""

    def __init__(self, reason: str) -> None:
        self._reason = reason

    async def __aenter__(self) -> UnavailableMarketDataAdapter:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def get_candles(self, **kwargs: Any) -> list[dict[str, Any]]:
        raise RuntimeError(self._reason)

    async def get_funding_rates(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        raise RuntimeError(self._reason)

    async def get_instruments(self, inst_type: str = "SWAP") -> list[dict[str, Any]]:
        raise RuntimeError(self._reason)

    async def get_open_interest(
        self, symbols: list[str]
    ) -> dict[str, dict[str, Any]]:
        raise RuntimeError(self._reason)


class LegacyMarketDataPortAdapter:
    def __init__(self, adapter: MarketDataAdapterPort) -> None:
        self._adapter = adapter

    async def __aenter__(self) -> LegacyMarketDataPortAdapter:
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


class LegacyCandleStorePortAdapter:
    def __init__(self, repository: CandleStorePort) -> None:
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

    async def get_latest_timestamp(
        self, *, symbol: str, timeframe: str
    ) -> int | None:
        return await self._repository.get_latest_timestamp(
            symbol=symbol,
            timeframe=timeframe,
        )

    async def get_fill_stats(self, start_timestamp_ms: int) -> dict[str, int | float]:
        return await self._repository.get_fill_stats(start_timestamp_ms)


class LegacyInstrumentCatalogPort:
    def __init__(self, repository: InstrumentCatalogQueryPort) -> None:
        self._repository = repository

    async def refresh_catalog(self) -> list[str]:
        return await refresh_instruments_list(repository=self._repository, logger=logger)

    async def load_cached_symbols(self) -> list[str]:
        instruments_file = resolve_instruments_cache_file()
        if not instruments_file.exists():
            return []

        try:
            with open(instruments_file, encoding="utf-8") as handle:
                symbols: list[str] = json.load(handle)
        except Exception as exc:
            logger.warning("Failed to read symbols from cache file (%s)", exc)
            return []

        return symbols

    async def list_symbols(self) -> list[str]:
        return await self._repository.list_swap_symbols()


def build_runtime_market_adapter(config: dict[str, Any]) -> MarketDataAdapterPort:
    try:
        adapter = build_market_data_adapter(config)
        logger.info("Initialized market adapter: %s", adapter.__class__.__name__)
        return adapter
    except Exception as exc:
        logger.warning("Adapter init failed (%s), fallback to legacy", exc)
        try:
            return build_market_data_adapter(
                {
                    "adapter": "legacy",
                    "legacy_adapter_factory": config.get("legacy_adapter_factory"),
                }
            )
        except Exception as fallback_exc:
            reason = (
                "No market adapter available. Primary init failed: "
                f"{exc}. Legacy fallback failed: {fallback_exc}"
            )
            logger.error(reason)
            return UnavailableMarketDataAdapter(reason)


def legacy_stats_from_result(result: SyncJobResult) -> dict[str, Any]:
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
    }
