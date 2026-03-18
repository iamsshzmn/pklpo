import logging

from src.db.indicators_partition.application import (
    BOOTSTRAP_MONTHS_AHEAD,
    BOOTSTRAP_MONTHS_BACK,
)
from src.db.indicators_partition.interfaces import run_indicators_partition_maintenance

logger = logging.getLogger(__name__)


async def migrate_create_indicators_partitioned() -> None:
    """
    Create partitioned indicators table and bootstrap a starting partition window.
    """
    result = await run_indicators_partition_maintenance(
        months_back=BOOTSTRAP_MONTHS_BACK,
        months_ahead=BOOTSTRAP_MONTHS_AHEAD,
        require_parent_pk=False,
    )

    logger.info(
        "indicators_p prepared: window=%s..%s created=%s existing=%s",
        result.get("window_start"),
        result.get("window_end"),
        result.get("created_count"),
        result.get("existing_count"),
    )
