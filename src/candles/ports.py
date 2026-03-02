from __future__ import annotations

from typing import Any, Protocol


class MarketDataAdapterPort(Protocol):
    async def __aenter__(self) -> MarketDataAdapterPort: ...

    async def __aexit__(self, *exc: Any) -> None: ...

    async def get_candles(
        self,
        *,
        inst_id: str,
        bar: str = "1m",
        limit: int = 300,
        before: str | None = None,
        after: str | None = None,
    ) -> list[dict[str, Any]]: ...

    async def get_funding_rates(self, symbols: list[str]) -> dict[str, dict[str, Any]]: ...

    async def get_open_interest(self, symbols: list[str]) -> dict[str, dict[str, Any]]: ...


class CandleRepositoryPort(Protocol):
    async def upsert_swap_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
        additional_data: dict[str, Any],
    ) -> int: ...

    async def fetch_swap_usdt_symbols(self) -> list[str]: ...

    async def fetch_instrument_counts(self) -> dict[str, int]: ...

    async def fetch_today_fill_stats(
        self, start_timestamp_ms: int
    ) -> dict[str, int | float]: ...
