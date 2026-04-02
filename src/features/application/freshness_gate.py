from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.storage_contract import IndicatorStorageContract
from src.logging import get_logger

logger = get_logger("features.application.freshness_gate")

_TIMEFRAME_TO_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1H": 3600,
    "4H": 14400,
    "12H": 43200,
    "1D": 86400,
    "1W": 604800,
    "1M": 2592000,
}


@dataclass(slots=True)
class FreshnessGateConfig:
    max_lag_fast: int = 240
    max_lag_slow: int = 1200


def _timeframe_to_seconds(timeframe: str) -> int:
    return _TIMEFRAME_TO_SECONDS.get(timeframe, 60)


def _expected_closed_bar_ts_ms(timeframe: str, now_utc: datetime) -> int:
    tf_seconds = _timeframe_to_seconds(timeframe)
    now_ts = int(now_utc.timestamp())
    current_period_start = (now_ts // tf_seconds) * tf_seconds
    expected_closed_bar_ts = current_period_start - tf_seconds
    return expected_closed_bar_ts * 1000


def _feature_lag_tolerance_seconds(timeframe: str) -> int:
    if timeframe in ("1m", "5m"):
        return 300
    return _timeframe_to_seconds(timeframe)


async def check_has_work_to_do(
    session: AsyncSession,
    timeframes: list[str],
    *,
    is_manual_run: bool = False,
    config: FreshnessGateConfig | None = None,
) -> bool:
    """Return True when the DAG should run, False when it can be skipped."""
    if is_manual_run:
        logger.info("Manual run detected: freshness gate bypassed")
        return True

    gate = config or FreshnessGateConfig()
    now_utc = datetime.now(UTC)
    all_fresh = True

    for timeframe in timeframes:
        is_fast = timeframe in ("1m", "5m")
        max_lag_seconds = gate.max_lag_fast if is_fast else gate.max_lag_slow
        expected_closed_bar_ts_ms = _expected_closed_bar_ts_ms(timeframe, now_utc)

        ohlcv_max_ts_ms = (
            await session.execute(
                text(
                    """
                    SELECT timestamp
                    FROM swap_ohlcv_p
                    WHERE timeframe = :tf
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """
                ),
                {"tf": timeframe},
            )
        ).scalar()

        if not ohlcv_max_ts_ms:
            logger.info("%s: no OHLCV rows, work required", timeframe)
            return True

        ohlcv_lag_sec = (expected_closed_bar_ts_ms - ohlcv_max_ts_ms) / 1000
        if ohlcv_lag_sec >= max_lag_seconds:
            logger.info(
                "%s: OHLCV lag %.0fs exceeds threshold %ss, work required",
                timeframe,
                ohlcv_lag_sec,
                max_lag_seconds,
            )
            all_fresh = False
            continue

        indicators_max_ts_ms = (
            await session.execute(
                text(
                    f"""
                    SELECT timestamp
                    FROM {IndicatorStorageContract.table_name}
                    WHERE timeframe = :tf
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """
                ),
                {"tf": timeframe},
            )
        ).scalar()
        if not indicators_max_ts_ms:
            logger.info("%s: no indicators rows, work required", timeframe)
            all_fresh = False
            continue

        feature_lag_sec = (ohlcv_max_ts_ms - indicators_max_ts_ms) / 1000
        tolerance = _feature_lag_tolerance_seconds(timeframe)
        if feature_lag_sec > tolerance:
            logger.info(
                "%s: feature lag %.0fs exceeds tolerance %ss, work required",
                timeframe,
                feature_lag_sec,
                tolerance,
            )
            all_fresh = False
        else:
            logger.info(
                "%s: fresh and synced (feature lag %.0fs <= %ss)",
                timeframe,
                feature_lag_sec,
                tolerance,
            )

    if all_fresh:
        logger.info("All timeframes are fresh and synced, DAG can be skipped")
        return False
    return True
