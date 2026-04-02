from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class PartitionSpec:
    start: datetime
    end: datetime
    start_ts: int
    end_ts: int
    name: str


MonthPartitionSpec = PartitionSpec


@dataclass(frozen=True, slots=True)
class PartitionCoverageSnapshot:
    present_partitions: tuple[str, ...]


@runtime_checkable
class IndicatorsPartitionMaintenancePort(Protocol):
    async def ensure_parent_exists(self) -> None: ...

    async def assert_parent_upsert_constraint(self) -> None: ...

    async def get_partition_coverage(
        self,
        partitions: tuple[PartitionSpec, ...],
    ) -> PartitionCoverageSnapshot: ...

    async def ensure_partition(self, partition: PartitionSpec) -> bool: ...
