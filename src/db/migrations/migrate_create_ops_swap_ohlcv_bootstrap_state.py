"""Migration: create ops.swap_ohlcv_bootstrap_state table."""

from sqlalchemy import text

from src.utils.session_utils import get_db_session


async def migrate_create_ops_swap_ohlcv_bootstrap_state() -> None:
    async with get_db_session() as session:
        await session.execute(text("CREATE SCHEMA IF NOT EXISTS ops;"))
        await session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS ops.swap_ohlcv_bootstrap_state (
                    symbol              TEXT        NOT NULL,
                    timeframe           TEXT        NOT NULL,
                    lookback_days       INTEGER     NOT NULL,
                    target_start_ts     BIGINT      NOT NULL,
                    target_end_ts       BIGINT      NOT NULL,
                    checkpoint_ts       BIGINT,
                    current_min_ts      BIGINT,
                    current_max_ts      BIGINT,
                    expected_bars       BIGINT      NOT NULL,
                    actual_bars         BIGINT,
                    missing_bars        BIGINT,
                    coverage_pct        NUMERIC(5,2),
                    status              TEXT        NOT NULL DEFAULT 'pending',
                    bootstrap_completed BOOLEAN     NOT NULL DEFAULT FALSE,
                    completed_at        TIMESTAMPTZ,
                    last_run_id         TEXT,
                    last_error          TEXT,
                    error_streak        INTEGER     NOT NULL DEFAULT 0,
                    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (symbol, timeframe),
                    CONSTRAINT chk_bootstrap_status CHECK (
                        status IN ('pending','running','incomplete','completed','stuck','failed')
                    ),
                    CONSTRAINT chk_expected_bars   CHECK (expected_bars >= 0),
                    CONSTRAINT chk_actual_bars     CHECK (actual_bars IS NULL OR actual_bars >= 0),
                    CONSTRAINT chk_missing_bars    CHECK (missing_bars IS NULL OR missing_bars >= 0),
                    CONSTRAINT chk_coverage_pct    CHECK (coverage_pct IS NULL OR coverage_pct BETWEEN 0 AND 100)
                );
                """
            )
        )
        await session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_bootstrap_state_status "
                "ON ops.swap_ohlcv_bootstrap_state (status, updated_at DESC);"
            )
        )
        await session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_bootstrap_state_completed "
                "ON ops.swap_ohlcv_bootstrap_state (bootstrap_completed, updated_at DESC);"
            )
        )
        await session.commit()
