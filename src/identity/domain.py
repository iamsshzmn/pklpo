"""Domain objects for identity build derivation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal


@dataclass(frozen=True)
class RawInstrument:
    symbol: str
    venue: str
    inst_type: str
    list_time: int | None = None


@dataclass(frozen=True)
class ApprovedSuccession:
    old_symbol: str
    new_symbol: str
    venue: str
    inst_type: str
    ratio: Decimal | int | float
    old_stop_ts: int | None
    new_start_ts: int | None
    effective_from: datetime
    known_from: datetime
    approved_at: datetime


@dataclass(frozen=True)
class ApprovedGapClassification:
    series_id: str
    timeframe: str
    range_start_ts: int
    range_end_ts: int
    gap_type: str
    recoverability: str
    reason: str
    known_from: datetime
    approved_at: datetime


@dataclass(frozen=True)
class IdentityBuildInputs:
    instruments: list[RawInstrument]
    successions: list[ApprovedSuccession]
    gap_classifications: list[ApprovedGapClassification]


@dataclass(frozen=True)
class SeriesRegistryRow:
    series_id: str
    series_label: str
    asset_id: str | None
    series_kind: str
    status: str
    known_from: datetime


@dataclass(frozen=True)
class SeriesMemberRow:
    series_id: str
    source_venue: str
    source_symbol: str
    valid_from: int
    valid_to: int | None
    known_from: datetime
    adjustment_factor: Decimal
    succession_id: str | None = None


@dataclass(frozen=True)
class SeriesAliasRow:
    old_series_id: str
    canonical_series_id: str
    known_from: datetime
    reason: str


@dataclass(frozen=True)
class SeriesGapRangeRow:
    series_id: str
    timeframe: str
    gap_start_ts: int
    gap_end_ts: int
    gap_type: str
    recoverability: str
    reason: str
    known_from: datetime


@dataclass(frozen=True)
class IdentitySnapshot:
    registry: list[SeriesRegistryRow]
    members: list[SeriesMemberRow]
    aliases: list[SeriesAliasRow]
    gap_ranges: list[SeriesGapRangeRow]

    @property
    def series_ids(self) -> list[str]:
        return [row.series_id for row in self.registry]


@dataclass(frozen=True)
class IdentityBuildContext:
    run_id: str
    algo_version: str
    params_hash: str
    as_of: datetime


@dataclass(frozen=True)
class IdentityBuildResult:
    run_id: str
    series_count: int
    member_count: int
    alias_count: int
    gap_count: int
