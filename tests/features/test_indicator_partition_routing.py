from __future__ import annotations

from unittest.mock import AsyncMock

import pandas as pd
import pytest

from src.features.infrastructure.persistence import inserter


@pytest.mark.asyncio
async def test_ensure_indicator_monthly_partitions_creates_range_for_dataframe() -> (
    None
):
    session = AsyncMock()
    created = []

    class _PartitionManager:
        def build_partition_spec(self, reference_dt=None, *, period_offset: int = 0):
            from src.db.indicators_partition.application.partition_policy import (
                MonthlyPartitionPolicy,
            )

            return MonthlyPartitionPolicy().build_partition_spec(
                reference_dt,
                period_offset=period_offset,
            )

        async def ensure_parent_exists(self) -> None:
            raise AssertionError(
                "runtime partition routing must not repair parent schema"
            )

        async def assert_parent_upsert_constraint(self) -> None:
            return None

        async def ensure_partition(self, spec) -> bool:
            created.append(spec.name)
            return True

    df = pd.DataFrame(
        {
            "timestamp": [
                1_706_745_600_000,  # 2024-02-01
                1_709_251_200_000,  # 2024-03-01
                1_711_929_600_000,  # 2024-04-01
            ]
        }
    )

    await inserter._ensure_indicator_monthly_partitions(
        session,
        df,
        partition_manager=_PartitionManager(),
    )

    assert created == [
        "indicators_p_2024_02",
        "indicators_p_2024_03",
        "indicators_p_2024_04",
    ]
