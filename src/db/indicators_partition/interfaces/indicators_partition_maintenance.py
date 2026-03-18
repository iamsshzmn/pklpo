from __future__ import annotations

from typing import TYPE_CHECKING

from src.utils.session_utils import get_db_session

from ..application import (
    DEFAULT_MONTHS_AHEAD,
    DEFAULT_MONTHS_BACK,
    EnsureIndicatorsPartitionWindow,
    PreviewIndicatorsPartitionWindow,
    ValidateIndicatorsPartitionHorizon,
)
from ..infrastructure import PostgresIndicatorsPartitionMaintenanceAdapter

if TYPE_CHECKING:
    from datetime import datetime


async def run_indicators_partition_maintenance(
    *,
    months_back: int = DEFAULT_MONTHS_BACK,
    months_ahead: int = DEFAULT_MONTHS_AHEAD,
    reference_dt: datetime | None = None,
    require_parent_pk: bool = True,
) -> dict[str, object]:
    async with get_db_session() as session:
        adapter = PostgresIndicatorsPartitionMaintenanceAdapter(session)
        use_case = EnsureIndicatorsPartitionWindow(adapter)
        result = await use_case.execute(
            months_back=months_back,
            months_ahead=months_ahead,
            reference_dt=reference_dt,
            require_parent_pk=require_parent_pk,
        )
    return result.to_dict()


async def preview_indicators_partition_maintenance(
    *,
    months_back: int = DEFAULT_MONTHS_BACK,
    months_ahead: int = DEFAULT_MONTHS_AHEAD,
    reference_dt: datetime | None = None,
) -> dict[str, object]:
    async with get_db_session() as session:
        adapter = PostgresIndicatorsPartitionMaintenanceAdapter(session)
        use_case = PreviewIndicatorsPartitionWindow(adapter)
        result = await use_case.execute(
            months_back=months_back,
            months_ahead=months_ahead,
            reference_dt=reference_dt,
        )
    return result.to_dict()


async def run_indicators_partition_validation(
    *,
    months_ahead: int = DEFAULT_MONTHS_AHEAD,
    reference_dt: datetime | None = None,
) -> dict[str, object]:
    async with get_db_session() as session:
        adapter = PostgresIndicatorsPartitionMaintenanceAdapter(session)
        use_case = ValidateIndicatorsPartitionHorizon(adapter)
        result = await use_case.execute(
            months_ahead=months_ahead,
            reference_dt=reference_dt,
        )

    if result.missing_partitions:
        raise RuntimeError(
            "Indicators partition horizon validation failed: missing partitions "
            f"{result.missing_partitions}"
        )

    return result.to_dict()
