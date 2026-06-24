from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir
from typing import TYPE_CHECKING, Any, cast

from src.candles.application.sync_use_cases import (
    build_sync_config,
    check_data_freshness,
    format_stats_for_xcom,
    run_smoke_validation as run_smoke_validation_use_case,
    should_refresh_instruments,
)
from src.candles.interfaces.swap_sync import (
    run_catalog_refresh_via_application,
    sync_swap_candles,
)
from src.candles.observability.prometheus import (
    push_swap_smoke_metrics,
    push_swap_sync_metrics,
)
from src.utils.session_utils import get_db_session

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime


@dataclass(frozen=True)
class AirflowSyncRequest:
    conf: Mapping[str, Any]
    logical_date: datetime | None
    run_type: str | None = None
    run_id: str | None = None

    @property
    def is_manual(self) -> bool:
        return self.run_type == "manual"


async def run_catalog_refresh_job(request: AirflowSyncRequest) -> dict[str, Any]:
    cache_dir = Path(
        os.environ.get("INSTRUMENTS_CACHE_DIR", str(Path(gettempdir()) / "pklpo"))
    )
    if not should_refresh_instruments(dict(request.conf), cache_dir):
        return {"refreshed": False, "reason": "cache_fresh"}

    return cast("dict[str, Any]", await run_catalog_refresh_via_application())


async def run_refresh_okx_meta(request: AirflowSyncRequest) -> dict[str, Any]:
    return await run_catalog_refresh_job(request)


async def run_swap_sync(request: AirflowSyncRequest) -> dict[str, Any]:
    config = build_sync_config(dict(request.conf), request.logical_date)
    mode = config["mode"]
    timeout_seconds = config.get("timeout_seconds")
    if timeout_seconds is None:
        timeout_seconds = 30

    if request.is_manual:
        should_skip = False
        skip_reason = ""
    else:
        async with get_db_session() as session:
            should_skip, skip_reason = await check_data_freshness(session, mode)

    if should_skip:
        return {"mode": mode, "skipped": True, "reason": skip_reason}

    stats = await sync_swap_candles(
        symbols=config.get("symbols"),
        timeframes=config.get("timeframes"),
        config={
            "mode": mode,
            "extra_data": config.get("extra_data", False),
            "max_requests_per_second": config.get("max_requests_per_second", 15),
            "batch_size": config.get("batch_size", 300),
            "max_concurrent_symbols": config.get("max_concurrent_symbols", 1),
            "max_retries": config.get("max_retries", 5),
            "retry_delay": config.get("retry_delay", 1.5),
            "timeout_seconds": timeout_seconds,
            "run_id": request.run_id,
        },
    )
    payload = format_stats_for_xcom(stats, config)
    push_swap_sync_metrics(payload)
    return payload


async def run_smoke_validate(request: AirflowSyncRequest) -> dict[str, Any]:
    config = build_sync_config(dict(request.conf), request.logical_date)
    mode = config["mode"]
    extra_data_enabled = config.get("extra_data", False)

    async with get_db_session() as session:
        result = await run_smoke_validation_use_case(
            session,
            mode,
            extra_data_enabled,
        )
    push_swap_smoke_metrics(result)
    return result
