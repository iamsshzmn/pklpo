"""
Persistent storage for data quality metrics.

Writes quality metrics (fill_rate, hole_rate, dup_rate, freshness_lag)
to ``data_quality_metrics`` table for historical trend analysis.

Usage (inside an async context with a DB session)::

    from src.features.observability.quality_store import record_quality_metrics

    await record_quality_metrics(
        session,
        symbol="all",
        timeframe="1m",
        metrics={"fill_rate": 0.998, "hole_rate": 0.0001, "freshness_lag": 42.0},
        window_hours=24,
    )
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("features.observability.quality_store")


async def record_quality_metrics(
    session: AsyncSession,
    *,
    symbol: str,
    timeframe: str,
    metrics: dict[str, float],
    window_hours: int,
) -> int:
    """Insert quality metrics into data_quality_metrics table.

    Args:
        session: Async SQLAlchemy session (caller manages commit/rollback).
        symbol: Instrument symbol or "all" for aggregated metrics.
        timeframe: Timeframe string (e.g. "1m", "5m").
        metrics: Dict of metric_name -> metric_value.
        window_hours: Aggregation window in hours (24, 168, 720).

    Returns:
        Number of rows inserted.
    """
    if not metrics:
        return 0

    now = datetime.now(UTC)
    count = 0

    for metric_name, metric_value in metrics.items():
        try:
            await session.execute(
                text(
                    """
                    INSERT INTO data_quality_metrics
                        (symbol, timeframe, metric_name, metric_value, window_hours, measured_at)
                    VALUES
                        (:symbol, :timeframe, :metric_name, :metric_value, :window_hours, :measured_at)
                """
                ),
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "metric_name": metric_name,
                    "metric_value": metric_value,
                    "window_hours": window_hours,
                    "measured_at": now,
                },
            )
            count += 1
        except Exception:
            logger.warning(
                "Failed to record metric %s for %s/%s",
                metric_name,
                symbol,
                timeframe,
                exc_info=True,
            )

    return count


async def get_quality_trend(
    session: AsyncSession,
    *,
    symbol: str,
    timeframe: str,
    metric_name: str,
    window_hours: int,
    limit: int = 100,
) -> list[tuple[datetime, float]]:
    """Fetch recent quality metric values for trend analysis.

    Args:
        session: Async SQLAlchemy session.
        symbol: Instrument symbol or "all".
        timeframe: Timeframe string.
        metric_name: Metric to query (e.g. "fill_rate").
        window_hours: Aggregation window filter.
        limit: Max rows to return.

    Returns:
        List of (measured_at, metric_value) tuples, newest first.
    """
    result = await session.execute(
        text(
            """
            SELECT measured_at, metric_value
            FROM data_quality_metrics
            WHERE symbol = :symbol
              AND timeframe = :timeframe
              AND metric_name = :metric_name
              AND window_hours = :window_hours
            ORDER BY measured_at DESC
            LIMIT :limit
        """
        ),
        {
            "symbol": symbol,
            "timeframe": timeframe,
            "metric_name": metric_name,
            "window_hours": window_hours,
            "limit": limit,
        },
    )
    return [(row[0], row[1]) for row in result.fetchall()]
