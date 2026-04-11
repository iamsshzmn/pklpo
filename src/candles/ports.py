from __future__ import annotations

from typing import Any, Protocol


class MarketDataPort(Protocol):
    async def __aenter__(self) -> MarketDataPort: ...

    async def __aexit__(self, *exc: Any) -> None: ...

    async def fetch_candles(
        self,
        *,
        instrument_id: str,
        timeframe: str = "1m",
        limit: int = 300,
        before: str | None = None,
        after: str | None = None,
    ) -> list[dict[str, Any]]: ...

    async def fetch_instruments(
        self, instrument_type: str = "SWAP"
    ) -> list[dict[str, Any]]: ...

    async def fetch_funding_rates(
        self, instrument_ids: list[str]
    ) -> dict[str, dict[str, Any]]: ...

    async def fetch_open_interest(
        self, instrument_ids: list[str]
    ) -> dict[str, dict[str, Any]]: ...


class InstrumentCatalogPort(Protocol):
    async def load_curated_symbols(self) -> list[str]: ...

    async def refresh_catalog(self) -> list[str]: ...

    async def load_cached_symbols(self) -> list[str]: ...

    async def list_symbols(self) -> list[str]: ...


class InstrumentCatalogQueryPort(Protocol):
    async def list_swap_symbols(self) -> list[str]: ...

    async def get_instrument_counts(self) -> dict[str, int]: ...


class CandleStorePort(Protocol):
    async def upsert_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
        additional_data: dict[str, Any],
    ) -> int: ...

    async def get_latest_timestamp(
        self, *, symbol: str, timeframe: str
    ) -> int | None: ...

    async def get_fill_stats(self, start_timestamp_ms: int) -> dict[str, int | float]: ...


class SyncStatePort(Protocol):
    async def is_data_fresh(
        self,
        *,
        timeframe: str,
        max_lag_seconds: int,
    ) -> tuple[bool, str]: ...


class TelemetryPort(Protocol):
    def increment(self, metric: str, value: int | float = 1, **tags: str) -> None: ...

    def observe(self, metric: str, value: int | float, **tags: str) -> None: ...

    def event(self, name: str, **payload: Any) -> None: ...


__all__ = [
    "CandleStorePort",
    "InstrumentCatalogPort",
    "InstrumentCatalogQueryPort",
    "MarketDataPort",
    "SyncStatePort",
    "TelemetryPort",
]
