from __future__ import annotations

from typing import Any, Protocol

from src.candles.ports import TelemetryPort


class CandleCoverageQueryPort(Protocol):
    async def list_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[int]: ...

    async def count_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> int: ...


class HistoricalCandleSourcePort(Protocol):
    async def fetch_range(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[dict[str, Any]]: ...


class RepairCandleStorePort(Protocol):
    async def selective_upsert_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
    ) -> int: ...


__all__ = [
    "CandleCoverageQueryPort",
    "HistoricalCandleSourcePort",
    "RepairCandleStorePort",
    "TelemetryPort",
]
