from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from ..ports import (
    IndicatorsPartitionMaintenancePort,
    MonthPartitionSpec,
    PartitionCoverageSnapshot,
)

logger = logging.getLogger(__name__)

PARENT_TABLE = "indicators_p"
DEFAULT_MONTHS_BACK = 1
DEFAULT_MONTHS_AHEAD = 3
BOOTSTRAP_MONTHS_BACK = 12
BOOTSTRAP_MONTHS_AHEAD = 1


@dataclass(frozen=True, slots=True)
class PartitionMaintenanceResult:
    reference_date: str
    months_back: int
    months_ahead: int
    window_start: str
    window_end: str
    created_partitions: list[str]
    existing_partitions: list[str]
    missing_before_run: list[str]
    created_count: int
    existing_count: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PartitionCoverageResult:
    reference_date: str
    months_ahead: int
    expected_partitions: list[str]
    present_partitions: list[str]
    missing_partitions: list[str]
    current_month_ready: bool
    actual_months_ahead: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _normalize_reference_dt(reference_dt: datetime | None) -> datetime:
    if reference_dt is None:
        return datetime.now(UTC)
    if reference_dt.tzinfo is None:
        return reference_dt.replace(tzinfo=UTC)
    return reference_dt.astimezone(UTC)


def _month_start(reference_dt: datetime) -> datetime:
    normalized = _normalize_reference_dt(reference_dt)
    return datetime(normalized.year, normalized.month, 1, tzinfo=UTC)


def _shift_month(month_start: datetime, offset: int) -> datetime:
    month_index = month_start.month - 1 + offset
    year = month_start.year + month_index // 12
    month = month_index % 12 + 1
    return datetime(year, month, 1, tzinfo=UTC)


def _unix_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def build_partition_name(start_ts: int, end_ts: int) -> str:
    return f"{PARENT_TABLE}_{start_ts}_{end_ts}"


def build_month_partition_spec(
    reference_dt: datetime | None = None,
    *,
    month_offset: int = 0,
) -> MonthPartitionSpec:
    base_month = _month_start(_normalize_reference_dt(reference_dt))
    start = _shift_month(base_month, month_offset)
    end = _shift_month(start, 1)
    start_ts = _unix_ms(start)
    end_ts = _unix_ms(end)
    return MonthPartitionSpec(
        start=start,
        end=end,
        start_ts=start_ts,
        end_ts=end_ts,
        name=build_partition_name(start_ts, end_ts),
    )


def iter_month_partition_specs(
    reference_dt: datetime | None = None,
    *,
    months_back: int = DEFAULT_MONTHS_BACK,
    months_ahead: int = DEFAULT_MONTHS_AHEAD,
) -> tuple[MonthPartitionSpec, ...]:
    if months_back < 0:
        raise ValueError("months_back must be >= 0")
    if months_ahead < 0:
        raise ValueError("months_ahead must be >= 0")

    return tuple(
        build_month_partition_spec(reference_dt, month_offset=offset)
        for offset in range(-months_back, months_ahead + 1)
    )


class EnsureIndicatorsPartitionWindow:
    def __init__(self, maintenance: IndicatorsPartitionMaintenancePort) -> None:
        self._maintenance = maintenance

    async def execute(
        self,
        *,
        months_back: int = DEFAULT_MONTHS_BACK,
        months_ahead: int = DEFAULT_MONTHS_AHEAD,
        reference_dt: datetime | None = None,
        require_parent_pk: bool = True,
    ) -> PartitionMaintenanceResult:
        reference = _normalize_reference_dt(reference_dt)
        specs = iter_month_partition_specs(
            reference,
            months_back=months_back,
            months_ahead=months_ahead,
        )

        await self._maintenance.ensure_parent_exists()
        if require_parent_pk:
            await self._maintenance.assert_parent_upsert_constraint()

        coverage = await self._maintenance.get_partition_coverage(specs)
        existing = set(coverage.present_partitions)

        created_partitions: list[str] = []
        existing_partitions: list[str] = []
        missing_before_run: list[str] = []

        for spec in specs:
            if spec.name in existing:
                existing_partitions.append(spec.name)
                continue

            missing_before_run.append(spec.name)
            created = await self._maintenance.ensure_partition(spec)
            if created:
                created_partitions.append(spec.name)
                existing.add(spec.name)
            else:
                existing_partitions.append(spec.name)
                existing.add(spec.name)

        result = PartitionMaintenanceResult(
            reference_date=reference.date().isoformat(),
            months_back=months_back,
            months_ahead=months_ahead,
            window_start=specs[0].start.date().isoformat(),
            window_end=specs[-1].end.date().isoformat(),
            created_partitions=created_partitions,
            existing_partitions=existing_partitions,
            missing_before_run=missing_before_run,
            created_count=len(created_partitions),
            existing_count=len(existing_partitions),
        )
        logger.info(
            "indicators_partition_maintenance table=%s reference_date=%s months_back=%s "
            "months_ahead=%s created_count=%s existing_count=%s missing_before_run=%s",
            PARENT_TABLE,
            result.reference_date,
            months_back,
            months_ahead,
            result.created_count,
            result.existing_count,
            len(result.missing_before_run),
        )
        return result


class PreviewIndicatorsPartitionWindow:
    def __init__(self, maintenance: IndicatorsPartitionMaintenancePort) -> None:
        self._maintenance = maintenance

    async def execute(
        self,
        *,
        months_back: int = DEFAULT_MONTHS_BACK,
        months_ahead: int = DEFAULT_MONTHS_AHEAD,
        reference_dt: datetime | None = None,
    ) -> PartitionMaintenanceResult:
        reference = _normalize_reference_dt(reference_dt)
        specs = iter_month_partition_specs(
            reference,
            months_back=months_back,
            months_ahead=months_ahead,
        )
        coverage = await self._maintenance.get_partition_coverage(specs)
        present = set(coverage.present_partitions)

        existing_partitions = [spec.name for spec in specs if spec.name in present]
        missing_before_run = [spec.name for spec in specs if spec.name not in present]

        result = PartitionMaintenanceResult(
            reference_date=reference.date().isoformat(),
            months_back=months_back,
            months_ahead=months_ahead,
            window_start=specs[0].start.date().isoformat(),
            window_end=specs[-1].end.date().isoformat(),
            created_partitions=[],
            existing_partitions=existing_partitions,
            missing_before_run=missing_before_run,
            created_count=0,
            existing_count=len(existing_partitions),
        )
        logger.info(
            "indicators_partition_preview table=%s reference_date=%s months_back=%s "
            "months_ahead=%s existing_count=%s missing_before_run=%s",
            PARENT_TABLE,
            result.reference_date,
            months_back,
            months_ahead,
            result.existing_count,
            len(result.missing_before_run),
        )
        return result


class ValidateIndicatorsPartitionHorizon:
    def __init__(self, maintenance: IndicatorsPartitionMaintenancePort) -> None:
        self._maintenance = maintenance

    async def execute(
        self,
        *,
        months_ahead: int = DEFAULT_MONTHS_AHEAD,
        reference_dt: datetime | None = None,
    ) -> PartitionCoverageResult:
        reference = _normalize_reference_dt(reference_dt)
        specs = iter_month_partition_specs(
            reference,
            months_back=0,
            months_ahead=months_ahead,
        )
        coverage = await self._maintenance.get_partition_coverage(specs)
        return self._build_result(
            specs=specs,
            coverage=coverage,
            months_ahead=months_ahead,
            reference=reference,
        )

    def _build_result(
        self,
        *,
        specs: tuple[MonthPartitionSpec, ...],
        coverage: PartitionCoverageSnapshot,
        months_ahead: int,
        reference: datetime,
    ) -> PartitionCoverageResult:
        present = set(coverage.present_partitions)
        expected = [spec.name for spec in specs]
        present_partitions = [spec.name for spec in specs if spec.name in present]
        missing_partitions = [spec.name for spec in specs if spec.name not in present]

        actual_months_ahead = 0
        for index, spec in enumerate(specs[1:], start=1):
            if spec.name not in present or actual_months_ahead != index - 1:
                break
            actual_months_ahead += 1

        result = PartitionCoverageResult(
            reference_date=reference.date().isoformat(),
            months_ahead=months_ahead,
            expected_partitions=expected,
            present_partitions=present_partitions,
            missing_partitions=missing_partitions,
            current_month_ready=specs[0].name in present,
            actual_months_ahead=actual_months_ahead,
        )
        logger.info(
            "indicators_partition_validation table=%s reference_date=%s months_ahead=%s "
            "actual_months_ahead=%s missing_count=%s",
            PARENT_TABLE,
            result.reference_date,
            months_ahead,
            result.actual_months_ahead,
            len(result.missing_partitions),
        )
        return result
