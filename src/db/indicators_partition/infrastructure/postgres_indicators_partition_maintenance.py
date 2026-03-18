from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import text

from ..application.indicators_partition_maintenance import PARENT_TABLE
from ..ports import (
    IndicatorsPartitionMaintenancePort,
    MonthPartitionSpec,
    PartitionCoverageSnapshot,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class PostgresIndicatorsPartitionMaintenanceAdapter(
    IndicatorsPartitionMaintenancePort
):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_parent_exists(self) -> None:
        await self._session.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {PARENT_TABLE} (
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
        # Add non-NUMERIC columns to existing table if they were created without them
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
                    f"ALTER TABLE {PARENT_TABLE} ADD COLUMN IF NOT EXISTS {col_name} "
                    + col_ddl.split(None, 1)[1]
                )
            )

    async def assert_parent_upsert_constraint(self) -> None:
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
            {"table_name": PARENT_TABLE},
        )
        definitions = [row[0] for row in result.fetchall()]
        normalized = [
            " ".join(definition.replace('"', "").upper().split())
            for definition in definitions
        ]
        if not any(
            definition in (
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
        partitions: tuple[MonthPartitionSpec, ...],
    ) -> PartitionCoverageSnapshot:
        present = [
            partition.name
            for partition in partitions
            if await self._partition_exists(partition.name)
        ]
        return PartitionCoverageSnapshot(present_partitions=tuple(present))

    async def ensure_partition(self, partition: MonthPartitionSpec) -> bool:
        if await self._partition_exists(partition.name):
            return False

        await self._session.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {partition.name}
                PARTITION OF {PARENT_TABLE}
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

    async def _partition_exists(self, partition_name: str) -> bool:
        result = await self._session.execute(
            text("SELECT to_regclass(:table_name) IS NOT NULL"),
            {"table_name": f"public.{partition_name}"},
        )
        return bool(result.scalar())
