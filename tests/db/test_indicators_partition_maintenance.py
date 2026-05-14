from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from src.db.indicators_partition.application import (
    WeeklyPartitionPolicy,
    indicators_partition_maintenance as maintenance,
)
from src.db.indicators_partition.ports import (
    MonthPartitionSpec,
    PartitionCoverageSnapshot,
)


@dataclass
class FakeMaintenancePort:
    present: set[str]
    created: list[str]
    calls: list[str]

    async def ensure_parent_exists(self) -> None:
        self.calls.append("ensure_parent_exists")

    async def ensure_parent_schema(self) -> None:
        self.calls.append("ensure_parent_schema")

    async def assert_parent_upsert_constraint(self) -> None:
        self.calls.append("assert_parent_upsert_constraint")

    async def get_partition_coverage(
        self,
        partitions: tuple[MonthPartitionSpec, ...],
    ) -> PartitionCoverageSnapshot:
        return PartitionCoverageSnapshot(
            present_partitions=tuple(
                partition.name
                for partition in partitions
                if partition.name in self.present
            )
        )

    async def ensure_partition(self, partition: MonthPartitionSpec) -> bool:
        if partition.name in self.present:
            return False
        self.present.add(partition.name)
        self.created.append(partition.name)
        return True


def test_iter_month_partition_specs_uses_exact_calendar_months() -> None:
    specs = maintenance.iter_month_partition_specs(
        datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        months_back=1,
        months_ahead=2,
    )

    assert [spec.start.date().isoformat() for spec in specs] == [
        "2025-12-01",
        "2026-01-01",
        "2026-02-01",
        "2026-03-01",
    ]
    assert [spec.end.date().isoformat() for spec in specs] == [
        "2026-01-01",
        "2026-02-01",
        "2026-03-01",
        "2026-04-01",
    ]


@pytest.mark.asyncio
async def test_ensure_partition_window_creates_only_missing_partitions() -> None:
    specs = maintenance.iter_month_partition_specs(
        datetime(2026, 3, 7, tzinfo=UTC),
        months_back=0,
        months_ahead=2,
    )
    port = FakeMaintenancePort(
        present={specs[0].name},
        created=[],
        calls=[],
    )
    use_case = maintenance.EnsureIndicatorsPartitionWindow(port)

    result = await use_case.execute(
        months_back=0,
        months_ahead=2,
        reference_dt=datetime(2026, 3, 7, tzinfo=UTC),
        require_parent_pk=True,
    )

    assert port.calls == [
        "ensure_parent_exists",
        "ensure_parent_schema",
        "assert_parent_upsert_constraint",
    ]
    assert result.existing_partitions == [specs[0].name]
    assert result.created_partitions == [specs[1].name, specs[2].name]
    assert result.missing_before_run == [specs[1].name, specs[2].name]
    assert port.created == [specs[1].name, specs[2].name]


@pytest.mark.asyncio
async def test_get_partition_coverage_counts_consecutive_future_months() -> None:
    specs = maintenance.iter_month_partition_specs(
        datetime(2026, 3, 7, tzinfo=UTC),
        months_back=0,
        months_ahead=3,
    )
    port = FakeMaintenancePort(
        present={specs[0].name, specs[1].name, specs[2].name},
        created=[],
        calls=[],
    )
    use_case = maintenance.ValidateIndicatorsPartitionHorizon(port)

    result = await use_case.execute(
        months_ahead=3,
        reference_dt=datetime(2026, 3, 7, tzinfo=UTC),
    )

    assert result.current_month_ready is True
    assert result.actual_months_ahead == 2
    assert result.missing_partitions == [specs[3].name]


@pytest.mark.asyncio
async def test_preview_partition_window_reports_missing_without_creating() -> None:
    specs = maintenance.iter_month_partition_specs(
        datetime(2026, 3, 7, tzinfo=UTC),
        months_back=1,
        months_ahead=1,
    )
    port = FakeMaintenancePort(
        present={specs[1].name},
        created=[],
        calls=[],
    )
    use_case = maintenance.PreviewIndicatorsPartitionWindow(port)

    result = await use_case.execute(
        months_back=1,
        months_ahead=1,
        reference_dt=datetime(2026, 3, 7, tzinfo=UTC),
    )

    assert result.created_count == 0
    assert result.created_partitions == []
    assert result.existing_partitions == [specs[1].name]
    assert result.missing_before_run == [specs[0].name, specs[2].name]
    assert port.created == []


def test_weekly_partition_policy_uses_exact_calendar_weeks() -> None:
    policy = WeeklyPartitionPolicy()

    specs = policy.build_window(
        datetime(2026, 3, 18, 12, 0, tzinfo=UTC),
        periods_back=1,
        periods_ahead=1,
    )

    assert [spec.start.date().isoformat() for spec in specs] == [
        "2026-03-09",
        "2026-03-16",
        "2026-03-23",
    ]
    assert [spec.end.date().isoformat() for spec in specs] == [
        "2026-03-16",
        "2026-03-23",
        "2026-03-30",
    ]
    assert [spec.name for spec in specs] == [
        "indicators_p_2026_w11",
        "indicators_p_2026_w12",
        "indicators_p_2026_w13",
    ]


@pytest.mark.asyncio
async def test_use_case_accepts_alternative_partition_policy() -> None:
    policy = WeeklyPartitionPolicy()
    specs = policy.build_window(
        datetime(2026, 3, 18, tzinfo=UTC),
        periods_back=0,
        periods_ahead=1,
    )
    port = FakeMaintenancePort(
        present={specs[0].name},
        created=[],
        calls=[],
    )
    use_case = maintenance.EnsureIndicatorsPartitionWindow(port, policy=policy)

    result = await use_case.execute(
        months_back=0,
        months_ahead=1,
        reference_dt=datetime(2026, 3, 18, tzinfo=UTC),
    )

    assert port.calls[:2] == ["ensure_parent_exists", "ensure_parent_schema"]
    assert result.existing_partitions == [specs[0].name]
    assert result.created_partitions == [specs[1].name]
