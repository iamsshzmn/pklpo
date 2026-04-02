from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime

from src.features.storage_contract import IndicatorStorageContract

from ..ports import (
    IndicatorsPartitionMaintenancePort,
    PartitionCoverageSnapshot,
    PartitionSpec,
)
from .partition_policy import (
    DEFAULT_PARTITION_POLICY,
    PartitionPolicy,
    normalize_reference_dt,
)

logger = logging.getLogger(__name__)

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


def build_month_partition_spec(
    reference_dt: datetime | None = None,
    *,
    month_offset: int = 0,
) -> PartitionSpec:
    return DEFAULT_PARTITION_POLICY.build_partition_spec(
        reference_dt,
        period_offset=month_offset,
    )


def build_partition_name(start: datetime) -> str:
    return DEFAULT_PARTITION_POLICY.build_partition_name(start)


def iter_month_partition_specs(
    reference_dt: datetime | None = None,
    *,
    months_back: int = DEFAULT_MONTHS_BACK,
    months_ahead: int = DEFAULT_MONTHS_AHEAD,
) -> tuple[PartitionSpec, ...]:
    return DEFAULT_PARTITION_POLICY.build_window(
        reference_dt,
        periods_back=months_back,
        periods_ahead=months_ahead,
    )


class EnsureIndicatorsPartitionWindow:
    def __init__(
        self,
        maintenance: IndicatorsPartitionMaintenancePort,
        policy: PartitionPolicy = DEFAULT_PARTITION_POLICY,
    ) -> None:
        self._maintenance = maintenance
        self._policy = policy

    async def execute(
        self,
        *,
        months_back: int = DEFAULT_MONTHS_BACK,
        months_ahead: int = DEFAULT_MONTHS_AHEAD,
        reference_dt: datetime | None = None,
        require_parent_pk: bool = True,
    ) -> PartitionMaintenanceResult:
        reference = normalize_reference_dt(reference_dt)
        specs = self._policy.build_window(
            reference,
            periods_back=months_back,
            periods_ahead=months_ahead,
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
            IndicatorStorageContract.table_name,
            result.reference_date,
            months_back,
            months_ahead,
            result.created_count,
            result.existing_count,
            len(result.missing_before_run),
        )
        return result


class PreviewIndicatorsPartitionWindow:
    def __init__(
        self,
        maintenance: IndicatorsPartitionMaintenancePort,
        policy: PartitionPolicy = DEFAULT_PARTITION_POLICY,
    ) -> None:
        self._maintenance = maintenance
        self._policy = policy

    async def execute(
        self,
        *,
        months_back: int = DEFAULT_MONTHS_BACK,
        months_ahead: int = DEFAULT_MONTHS_AHEAD,
        reference_dt: datetime | None = None,
    ) -> PartitionMaintenanceResult:
        reference = normalize_reference_dt(reference_dt)
        specs = self._policy.build_window(
            reference,
            periods_back=months_back,
            periods_ahead=months_ahead,
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
            IndicatorStorageContract.table_name,
            result.reference_date,
            months_back,
            months_ahead,
            result.existing_count,
            len(result.missing_before_run),
        )
        return result


class ValidateIndicatorsPartitionHorizon:
    def __init__(
        self,
        maintenance: IndicatorsPartitionMaintenancePort,
        policy: PartitionPolicy = DEFAULT_PARTITION_POLICY,
    ) -> None:
        self._maintenance = maintenance
        self._policy = policy

    async def execute(
        self,
        *,
        months_ahead: int = DEFAULT_MONTHS_AHEAD,
        reference_dt: datetime | None = None,
    ) -> PartitionCoverageResult:
        reference = normalize_reference_dt(reference_dt)
        specs = self._policy.build_window(
            reference,
            periods_back=0,
            periods_ahead=months_ahead,
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
        specs: tuple[PartitionSpec, ...],
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
            IndicatorStorageContract.table_name,
            result.reference_date,
            months_ahead,
            result.actual_months_ahead,
            len(result.missing_partitions),
        )
        return result
