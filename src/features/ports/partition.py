"""Partition management port for features persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    from src.db.indicators_partition.ports.indicators_partition_maintenance import (
        PartitionSpec,
    )


@runtime_checkable
class PartitionManager(Protocol):
    """Abstraction over partition policy and maintenance operations."""

    def build_partition_spec(
        self,
        reference_dt: datetime | None = None,
        *,
        period_offset: int = 0,
    ) -> PartitionSpec: ...

    async def ensure_parent_exists(self) -> None: ...

    async def assert_parent_upsert_constraint(self) -> None: ...

    async def ensure_partition(self, partition: PartitionSpec) -> bool: ...


__all__ = ["PartitionManager"]
