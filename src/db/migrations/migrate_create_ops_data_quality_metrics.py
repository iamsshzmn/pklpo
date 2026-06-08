"""Migration 280: create ops schema and ops.data_quality_metrics table."""

from sqlalchemy import text

from src.utils.session_utils import get_db_session


async def migrate_create_ops_data_quality_metrics() -> None:
    async with get_db_session() as session:
        await session.execute(text("CREATE SCHEMA IF NOT EXISTS ops;"))
        await session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS ops.data_quality_metrics (
                id BIGSERIAL PRIMARY KEY,
                ts TIMESTAMPTZ NOT NULL DEFAULT now(),
                check_name TEXT NOT NULL,
                severity TEXT NOT NULL,
                symbol TEXT NULL,
                timeframe TEXT NULL,
                value NUMERIC NULL,
                meta JSONB NOT NULL DEFAULT '{}'::jsonb
            );
        """
            )
        )
        await session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_dq_metrics_ts "
                "ON ops.data_quality_metrics (ts DESC);"
            )
        )
        await session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_dq_metrics_check "
                "ON ops.data_quality_metrics (check_name, ts DESC);"
            )
        )
        await session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_dq_metrics_severity "
                "ON ops.data_quality_metrics (severity, ts DESC) "
                "WHERE severity IN ('warn', 'critical');"
            )
        )
        await session.commit()
