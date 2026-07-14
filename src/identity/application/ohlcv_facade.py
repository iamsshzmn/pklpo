"""Read facade for analytical OHLCV access through identity-aware series."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime


@dataclass(frozen=True)
class OhlcvFacadeRow:
    series_id: str
    timeframe: str
    timestamp: int
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    volume: Decimal | None
    segment_id: str | None
    source_venue: str | None
    source_symbol: str | None
    source_timestamp: int | None
    bar_kind: str
    data_status: str
    succession_id: str | None
    adjustment_factor: Decimal
    is_gap: bool
    gap_type: str | None


class ContinuousReadDisabledError(RuntimeError):
    """Raised when a composite series is requested while continuous reads are off."""


class OhlcvFacadeRepository(Protocol):
    async def resolve_alias(self, series_id: str, as_of: datetime | None) -> str:
        """Resolve a PIT alias to the canonical series id."""

    async def get_series_kind(self, series_id: str, as_of: datetime | None) -> str:
        """Return series_kind for the canonical series id."""

    async def read_raw(
        self, series_id: str, timeframe: str, start_ts: int, end_ts: int
    ) -> list[Mapping[str, object] | OhlcvFacadeRow]:
        """Read raw OHLCV rows for trivial passthrough series."""

    async def read_continuous(
        self, series_id: str, timeframe: str, start_ts: int, end_ts: int
    ) -> list[Mapping[str, object] | OhlcvFacadeRow]:
        """Read materialized continuous rows for composite series."""

    async def read_gap_markers(
        self,
        series_id: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        as_of: datetime | None,
    ) -> list[Mapping[str, object] | OhlcvFacadeRow]:
        """Read output-only gap markers for a composite series."""

    async def get_adjustment_factor(
        self, series_id: str, timestamp: int, as_of: datetime | None
    ) -> Decimal:
        """Read the PIT adjustment factor for a timestamp."""


class OhlcvFacade:
    def __init__(
        self,
        repository: OhlcvFacadeRepository,
        *,
        continuous_read_enabled: bool | None = None,
    ) -> None:
        self._repository = repository
        self._continuous_read_enabled = (
            _env_flag("CONTINUOUS_READ_ENABLED")
            if continuous_read_enabled is None
            else continuous_read_enabled
        )

    async def read_ohlcv(
        self,
        *,
        series_id: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        as_of: datetime | None = None,
        include_gap_markers: bool = False,
    ) -> list[OhlcvFacadeRow]:
        canonical_series_id = await self._repository.resolve_alias(series_id, as_of)
        series_kind = await self._repository.get_series_kind(canonical_series_id, as_of)

        if series_kind == "composite":
            if not self._continuous_read_enabled:
                raise ContinuousReadDisabledError(
                    "continuous OHLCV reads are disabled for composite series"
                )
            rows = await self._repository.read_continuous(
                canonical_series_id, timeframe, start_ts, end_ts
            )
        else:
            rows = await self._repository.read_raw(
                canonical_series_id, timeframe, start_ts, end_ts
            )

        output_rows = [
            await self._with_pit_adjustment(_coerce_row(row), as_of) for row in rows
        ]
        if include_gap_markers:
            gap_rows = await self._repository.read_gap_markers(
                canonical_series_id, timeframe, start_ts, end_ts, as_of
            )
            output_rows.extend(_coerce_gap_marker(row) for row in gap_rows)

        return sorted(output_rows, key=lambda row: (row.timestamp, not row.is_gap))

    async def _with_pit_adjustment(
        self, row: OhlcvFacadeRow, as_of: datetime | None
    ) -> OhlcvFacadeRow:
        if row.is_gap:
            return row

        adjustment_factor = await self._repository.get_adjustment_factor(
            row.series_id, row.timestamp, as_of
        )
        return OhlcvFacadeRow(
            series_id=row.series_id,
            timeframe=row.timeframe,
            timestamp=row.timestamp,
            open=_multiply(row.open, adjustment_factor),
            high=_multiply(row.high, adjustment_factor),
            low=_multiply(row.low, adjustment_factor),
            close=_multiply(row.close, adjustment_factor),
            volume=row.volume,
            segment_id=row.segment_id,
            source_venue=row.source_venue,
            source_symbol=row.source_symbol,
            source_timestamp=row.source_timestamp,
            bar_kind=row.bar_kind,
            data_status=row.data_status,
            succession_id=row.succession_id,
            adjustment_factor=adjustment_factor,
            is_gap=row.is_gap,
            gap_type=row.gap_type,
        )


def _coerce_row(row: Mapping[str, object] | OhlcvFacadeRow) -> OhlcvFacadeRow:
    if isinstance(row, OhlcvFacadeRow):
        return row

    timestamp = int(row["timestamp"])
    series_id = str(row["series_id"])
    timeframe = str(row["timeframe"])
    return OhlcvFacadeRow(
        series_id=series_id,
        timeframe=timeframe,
        timestamp=timestamp,
        open=_decimal_or_none(row.get("open")),
        high=_decimal_or_none(row.get("high")),
        low=_decimal_or_none(row.get("low")),
        close=_decimal_or_none(row.get("close")),
        volume=_decimal_or_none(row.get("volume")),
        segment_id=_str_or_none(row.get("segment_id")),
        source_venue=_str_or_none(row.get("source_venue")),
        source_symbol=_str_or_none(row.get("source_symbol")),
        source_timestamp=_int_or_none(row.get("source_timestamp", timestamp)),
        bar_kind=str(row.get("bar_kind", "native")),
        data_status=str(row.get("data_status", "complete")),
        succession_id=_str_or_none(row.get("succession_id")),
        adjustment_factor=_decimal_or_none(row.get("adjustment_factor"))
        or Decimal("1"),
        is_gap=bool(row.get("is_gap", False)),
        gap_type=_str_or_none(row.get("gap_type")),
    )


def _coerce_gap_marker(row: Mapping[str, object] | OhlcvFacadeRow) -> OhlcvFacadeRow:
    if isinstance(row, OhlcvFacadeRow):
        return row

    return OhlcvFacadeRow(
        series_id=str(row["series_id"]),
        timeframe=str(row["timeframe"]),
        timestamp=int(row["timestamp"]),
        open=None,
        high=None,
        low=None,
        close=None,
        volume=None,
        segment_id=_str_or_none(row.get("segment_id")),
        source_venue=None,
        source_symbol=None,
        source_timestamp=None,
        bar_kind=str(row.get("bar_kind", "gap_marker")),
        data_status=str(row.get("data_status", "missing")),
        succession_id=None,
        adjustment_factor=Decimal("1"),
        is_gap=True,
        gap_type=_str_or_none(row.get("gap_type")),
    )


def _multiply(value: Decimal | None, factor: Decimal) -> Decimal | None:
    return None if value is None else value * factor


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _int_or_none(value: object) -> int | None:
    return None if value is None else int(value)


def _str_or_none(value: object) -> str | None:
    return None if value is None else str(value)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}
