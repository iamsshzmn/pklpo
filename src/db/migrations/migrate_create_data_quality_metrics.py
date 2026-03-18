"""
Migration: create data_quality_metrics table.

Stores historical quality metrics (fill_rate, hole_rate, dup_rate, freshness_lag)
per symbol/timeframe with configurable aggregation windows (24h / 7d / 30d).
Used by Phase 1 quality dashboard and trend analysis.
"""

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_create_data_quality_metrics() -> None:
    """Create data_quality_metrics table (idempotent)."""
    logger.info("Creating data_quality_metrics table...")

    async with get_db_session() as session:
        try:
            await session.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS data_quality_metrics (
                        id SERIAL PRIMARY KEY,
                        symbol VARCHAR(50) NOT NULL,
                        timeframe VARCHAR(10) NOT NULL,
                        metric_name VARCHAR(50) NOT NULL,
                        metric_value DOUBLE PRECISION NOT NULL,
                        window_hours INT NOT NULL,
                        measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );

                    CREATE INDEX IF NOT EXISTS idx_dqm_lookup
                        ON data_quality_metrics (symbol, timeframe, metric_name, measured_at);

                    CREATE INDEX IF NOT EXISTS idx_dqm_measured_at
                        ON data_quality_metrics (measured_at);
                """)
            )
            await session.commit()
            logger.info("data_quality_metrics table ready")
        except Exception as e:
            await session.rollback()
            logger.error("Failed to create data_quality_metrics: %s", e)
            raise
