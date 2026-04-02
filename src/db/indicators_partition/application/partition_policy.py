from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from src.features.storage_contract import IndicatorStorageContract

from ..ports import PartitionSpec


def normalize_reference_dt(reference_dt: datetime | None) -> datetime:
    if reference_dt is None:
        return datetime.now(UTC)
    if reference_dt.tzinfo is None:
        return reference_dt.replace(tzinfo=UTC)
    return reference_dt.astimezone(UTC)


def unix_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


class PartitionPolicy(Protocol):
    def build_window(
        self,
        reference_dt: datetime | None = None,
        *,
        periods_back: int,
        periods_ahead: int,
    ) -> tuple[PartitionSpec, ...]: ...


def _month_start(reference_dt: datetime) -> datetime:
    normalized = normalize_reference_dt(reference_dt)
    return datetime(normalized.year, normalized.month, 1, tzinfo=UTC)


def _shift_month(month_start: datetime, offset: int) -> datetime:
    month_index = month_start.month - 1 + offset
    year = month_start.year + month_index // 12
    month = month_index % 12 + 1
    return datetime(year, month, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class MonthlyPartitionPolicy:
    table_name: str = IndicatorStorageContract.table_name

    def build_partition_name(self, start: datetime) -> str:
        return f"{self.table_name}_{start.year}_{start.month:02d}"

    def build_partition_spec(
        self,
        reference_dt: datetime | None = None,
        *,
        period_offset: int = 0,
    ) -> PartitionSpec:
        base_month = _month_start(normalize_reference_dt(reference_dt))
        start = _shift_month(base_month, period_offset)
        end = _shift_month(start, 1)
        return PartitionSpec(
            start=start,
            end=end,
            start_ts=unix_ms(start),
            end_ts=unix_ms(end),
            name=self.build_partition_name(start),
        )

    def build_window(
        self,
        reference_dt: datetime | None = None,
        *,
        periods_back: int,
        periods_ahead: int,
    ) -> tuple[PartitionSpec, ...]:
        if periods_back < 0:
            raise ValueError("periods_back must be >= 0")
        if periods_ahead < 0:
            raise ValueError("periods_ahead must be >= 0")
        return tuple(
            self.build_partition_spec(reference_dt, period_offset=offset)
            for offset in range(-periods_back, periods_ahead + 1)
        )


def _week_start(reference_dt: datetime) -> datetime:
    normalized = normalize_reference_dt(reference_dt)
    start = normalized - timedelta(days=normalized.weekday())
    return datetime(start.year, start.month, start.day, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class WeeklyPartitionPolicy:
    table_name: str = IndicatorStorageContract.table_name

    def build_partition_name(self, start: datetime) -> str:
        iso_year, iso_week, _ = start.isocalendar()
        return f"{self.table_name}_{iso_year}_w{iso_week:02d}"

    def build_partition_spec(
        self,
        reference_dt: datetime | None = None,
        *,
        period_offset: int = 0,
    ) -> PartitionSpec:
        base_week = _week_start(normalize_reference_dt(reference_dt))
        start = base_week + timedelta(weeks=period_offset)
        end = start + timedelta(weeks=1)
        return PartitionSpec(
            start=start,
            end=end,
            start_ts=unix_ms(start),
            end_ts=unix_ms(end),
            name=self.build_partition_name(start),
        )

    def build_window(
        self,
        reference_dt: datetime | None = None,
        *,
        periods_back: int,
        periods_ahead: int,
    ) -> tuple[PartitionSpec, ...]:
        if periods_back < 0:
            raise ValueError("periods_back must be >= 0")
        if periods_ahead < 0:
            raise ValueError("periods_ahead must be >= 0")
        return tuple(
            self.build_partition_spec(reference_dt, period_offset=offset)
            for offset in range(-periods_back, periods_ahead + 1)
        )


DEFAULT_PARTITION_POLICY = MonthlyPartitionPolicy()
