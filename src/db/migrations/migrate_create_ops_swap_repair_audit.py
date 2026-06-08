"""Migration 310: create ops.swap_repair_audit table."""

from sqlalchemy import text

from src.utils.session_utils import get_db_session


async def migrate_create_ops_swap_repair_audit() -> None:
    async with get_db_session() as session:
        await session.execute(text("CREATE SCHEMA IF NOT EXISTS ops;"))
        await session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS ops.swap_repair_audit (
                id BIGSERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                dag_id TEXT NOT NULL,
                dag_run_id TEXT NULL,
                logical_date TIMESTAMPTZ NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                mode TEXT NOT NULL,
                strategy TEXT NOT NULL,
                auto_apply_window BOOLEAN NOT NULL DEFAULT FALSE,
                auto_apply_incomplete BOOLEAN NOT NULL DEFAULT FALSE,
                verified BOOLEAN NOT NULL DEFAULT FALSE,
                gap_tasks INTEGER NOT NULL DEFAULT 0,
                requested_bars INTEGER NOT NULL DEFAULT 0,
                remaining_gap_tasks INTEGER NOT NULL DEFAULT 0,
                remaining_requested_bars INTEGER NOT NULL DEFAULT 0,
                rows_written INTEGER NOT NULL DEFAULT 0,
                fetch_calls INTEGER NOT NULL DEFAULT 0,
                window_start_ts_ms BIGINT NOT NULL,
                window_end_ts_ms BIGINT NOT NULL,
                verification_method TEXT NULL,
                preview_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                summary_payload JSONB NOT NULL,
                requested_conf JSONB NOT NULL DEFAULT '{}'::jsonb
            );
        """
            )
        )
        await session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_swap_repair_audit_created_at "
                "ON ops.swap_repair_audit (created_at DESC);"
            )
        )
        await session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_swap_repair_audit_run "
                "ON ops.swap_repair_audit (dag_id, dag_run_id, timeframe);"
            )
        )
        await session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_swap_repair_audit_symbol_tf "
                "ON ops.swap_repair_audit (symbol, timeframe, created_at DESC);"
            )
        )
        await session.commit()
