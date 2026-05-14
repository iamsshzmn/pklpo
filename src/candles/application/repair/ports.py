from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.candles.ports import TelemetryPort


@dataclass(frozen=True)
class ListingAnchorMetadata:
    list_time_ts_ms: int | None
    metadata_refreshed_at_ms: int | None


class CandleCoverageQueryPort(Protocol):
    async def list_existing_valid_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[int]: ...

    async def get_coverage_bounds(
        self,
        *,
        symbol: str,
        timeframe: str,
        end_ts_ms: int,
    ) -> tuple[int | None, int | None]: ...

    async def find_first_gap_start_ts_ms(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> int | None: ...

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

    async def list_missing_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
        interval_ms: int,
    ) -> list[int]: ...

    async def count_missing_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> int: ...

    async def list_corrupted_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[int]: ...


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


class RepairAnchorMetadataPort(Protocol):
    async def get_listing_anchor_metadata(
        self,
        *,
        symbol: str,
    ) -> ListingAnchorMetadata | None: ...

    async def get_listing_time_ts_ms(self, *, symbol: str) -> int | None: ...


__all__ = [
    "CandleCoverageQueryPort",
    "HistoricalCandleSourcePort",
    "ListingAnchorMetadata",
    "RepairAnchorMetadataPort",
    "RepairCandleStorePort",
    "TelemetryPort",
]
