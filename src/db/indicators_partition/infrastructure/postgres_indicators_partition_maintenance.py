from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import text

from src.features.storage_contract import IndicatorStorageContract

from ..ports import (
    IndicatorsPartitionMaintenancePort,
    PartitionCoverageSnapshot,
    PartitionSpec,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class PostgresIndicatorsPartitionMaintenanceAdapter(IndicatorsPartitionMaintenancePort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_parent_exists(self) -> None:
        if await self._parent_exists() and not await self._parent_is_partitioned():
            row_count = await self._parent_row_count()
            if row_count:
                raise RuntimeError(
                    "Partition maintenance prerequisite failed: indicators_p exists "
                    f"as a non-partitioned table with {row_count} rows"
                )
            logger.warning(
                "dropping empty non-partitioned %s so it can be recreated as a "
                "partitioned parent",
                IndicatorStorageContract.table_name,
            )
            await self._session.execute(
                text(f"DROP TABLE {IndicatorStorageContract.table_name} CASCADE")
            )

        await self._session.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {IndicatorStorageContract.table_name} (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp BIGINT NOT NULL,
                    calculated_at TIMESTAMPTZ,
                    data_status VARCHAR(10) DEFAULT 'ok',
                    failed_groups TEXT,
                    cdl_doji SMALLINT,
                    cdl_inside SMALLINT
                ) PARTITION BY RANGE (timestamp);
                """
            )
        )

    async def ensure_parent_schema(self) -> None:
        await self.ensure_parent_exists()
        # Reconcile additive service columns outside the hot runtime path.
        for col_ddl in (
            "calculated_at TIMESTAMPTZ",
            "data_status VARCHAR(10) DEFAULT 'ok'",
            "failed_groups TEXT",
            "cdl_doji SMALLINT",
            "cdl_inside SMALLINT",
        ):
            col_name = col_ddl.split()[0]
            await self._session.execute(
                text(
                    f"ALTER TABLE {IndicatorStorageContract.table_name} ADD COLUMN IF NOT EXISTS {col_name} "
                    + col_ddl.split(None, 1)[1]
                )
            )

    async def assert_parent_upsert_constraint(self) -> None:
        if not await self._parent_exists():
            raise RuntimeError(
                "Partition maintenance prerequisite failed: "
                "indicators_p does not exist; run DB migrations/bootstrap first"
            )
        if not await self._parent_is_partitioned():
            raise RuntimeError(
                "Partition maintenance prerequisite failed: "
                "indicators_p exists but is not a partitioned parent table"
            )
        result = await self._session.execute(
            text(
                """
                SELECT pg_get_constraintdef(c.oid)
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = 'public'
                  AND t.relname = :table_name
                  AND c.contype IN ('p', 'u')
                """
            ),
            {"table_name": IndicatorStorageContract.table_name},
        )
        definitions = [row[0] for row in result.fetchall()]
        normalized = [
            " ".join(definition.replace('"', "").upper().split())
            for definition in definitions
        ]
        if not any(
            definition
            in (
                "PRIMARY KEY (SYMBOL, TIMEFRAME, TIMESTAMP)",
                "UNIQUE (SYMBOL, TIMEFRAME, TIMESTAMP)",
            )
            for definition in normalized
        ):
            raise RuntimeError(
                "Partition maintenance prerequisite failed: "
                "indicators_p must have PRIMARY KEY or UNIQUE on "
                "(symbol, timeframe, timestamp)"
            )

    async def get_partition_coverage(
        self,
        partitions: tuple[PartitionSpec, ...],
    ) -> PartitionCoverageSnapshot:
        present = [
            partition.name
            for partition in partitions
            if await self._partition_exists(partition.name)
        ]
        return PartitionCoverageSnapshot(present_partitions=tuple(present))

    async def ensure_partition(self, partition: PartitionSpec) -> bool:
        if await self._partition_exists(partition.name):
            return False

        await self._session.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {partition.name}
                PARTITION OF {IndicatorStorageContract.table_name}
                FOR VALUES FROM ({partition.start_ts}) TO ({partition.end_ts});
                """
            )
        )
        await self._session.execute(
            text(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{partition.name}_sym_tf_ts
                ON {partition.name}(symbol, timeframe, timestamp);
                """
            )
        )
        await self._session.execute(
            text(
                f"""
                CREATE INDEX IF NOT EXISTS brin_{partition.name}_ts
                ON {partition.name} USING BRIN (timestamp);
                """
            )
        )
        logger.info("created indicators partition %s", partition.name)
        return True

    async def _parent_exists(self) -> bool:
        result = await self._session.execute(
            text("SELECT to_regclass(:table_name) IS NOT NULL"),
            {"table_name": f"public.{IndicatorStorageContract.table_name}"},
        )
        return bool(result.scalar())

    async def _parent_is_partitioned(self) -> bool:
        result = await self._session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_partitioned_table pt
                    JOIN pg_class c ON c.oid = pt.partrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname = :table_name
                )
                """
            ),
            {"table_name": IndicatorStorageContract.table_name},
        )
        return bool(result.scalar())

    async def _parent_row_count(self) -> int:
        result = await self._session.execute(
            text(f"SELECT COUNT(*) FROM {IndicatorStorageContract.table_name}")
        )
        return int(result.scalar() or 0)

    async def _partition_exists(self, partition_name: str) -> bool:
        result = await self._session.execute(
            text("SELECT to_regclass(:table_name) IS NOT NULL"),
            {"table_name": f"public.{partition_name}"},
        )
        return bool(result.scalar())
