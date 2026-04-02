from __future__ import annotations

from typing import TYPE_CHECKING

from src.db.indicators_partition.application.partition_policy import (
    MonthlyPartitionPolicy,
)
from src.db.indicators_partition.infrastructure import (
    PostgresIndicatorsPartitionMaintenanceAdapter,
)

from ..ports import PartitionManager

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from src.db.indicators_partition.ports.indicators_partition_maintenance import (
        PartitionSpec,
    )


class PostgresPartitionManagerAdapter(PartitionManager):
    """PartitionManager adapter backed by the Postgres partition maintenance stack."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        policy: MonthlyPartitionPolicy | None = None,
    ) -> None:
        self._policy = policy or MonthlyPartitionPolicy()
        self._maintenance = PostgresIndicatorsPartitionMaintenanceAdapter(session)

    def build_partition_spec(
        self,
        reference_dt: datetime | None = None,
        *,
        period_offset: int = 0,
    ) -> PartitionSpec:
        return self._policy.build_partition_spec(
            reference_dt,
            period_offset=period_offset,
        )

    async def ensure_parent_exists(self) -> None:
        await self._maintenance.ensure_parent_exists()

    async def assert_parent_upsert_constraint(self) -> None:
        await self._maintenance.assert_parent_upsert_constraint()

    async def ensure_partition(self, partition: PartitionSpec) -> bool:
        return await self._maintenance.ensure_partition(partition)


def create_partition_manager(
    session: AsyncSession,
    *,
    policy: MonthlyPartitionPolicy | None = None,
) -> PartitionManager:
    return PostgresPartitionManagerAdapter(session, policy=policy)


__all__ = ["PostgresPartitionManagerAdapter", "create_partition_manager"]
