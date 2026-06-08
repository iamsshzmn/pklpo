"""
Migration: Create Market Selection tables

Tables:
- market_scores_tf: per-symbol per-TF scoring history
- market_universe: selected trading pairs per version
- market_universe_versions: version metadata and status
- market_regime_history: global regime history
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_engine

logger = logging.getLogger(__name__)


async def migrate_create_market_selection() -> None:
    """Create all market_selection tables."""
    engine = get_async_engine()

    async with AsyncSession(engine) as session:
        # 1. market_scores_tf
        await session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS market_scores_tf (
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                ts_eval BIGINT NOT NULL,

                vol_raw REAL,
                trend_q_raw REAL,
                noise_raw REAL,
                stability_raw REAL,
                liq_raw REAL,

                vol_score REAL,
                trend_q_score REAL,
                noise_score REAL,
                stability_score REAL,
                liq_score REAL,

                score_tf_base REAL,
                score_tf REAL,

                quality_score REAL,
                fill_rate REAL,
                gap_rate REAL,
                data_lag_seconds INTEGER,
                valid_bars INTEGER,
                expected_bars INTEGER,
                eligible BOOLEAN NOT NULL DEFAULT false,

                global_regime TEXT,
                global_strength REAL,
                regime_confidence REAL,

                reason_flags TEXT[] DEFAULT '{}',
                window_days INTEGER,
                config_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),

                PRIMARY KEY (symbol, timeframe, ts_eval)
            )
        """
            )
        )

        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_mstf_tf_ts
                ON market_scores_tf (timeframe, ts_eval)
        """
            )
        )

        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_mstf_symbol_tf
                ON market_scores_tf (symbol, timeframe)
        """
            )
        )

        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_mstf_eligible_ts
                ON market_scores_tf (eligible, ts_eval)
                WHERE eligible = true
        """
            )
        )

        logger.info("Created table: market_scores_tf")

        # 2. market_universe
        await session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS market_universe (
                ts_version BIGINT NOT NULL,
                symbol TEXT NOT NULL,

                final_score REAL NOT NULL,
                rank INTEGER NOT NULL,

                score_4h REAL,
                score_1h REAL,
                score_15m REAL,
                score_5m REAL,
                best_tf TEXT,
                worst_tf TEXT,

                score_std_7d REAL,
                score_std_30d REAL,
                days_in_universe INTEGER,

                global_regime_at_time TEXT,
                global_strength_at_time REAL,

                reason_flags TEXT[] DEFAULT '{}',
                penalty_applied REAL DEFAULT 0,

                config_hash TEXT NOT NULL,
                source_version BIGINT,

                created_at TIMESTAMPTZ DEFAULT NOW(),

                PRIMARY KEY (ts_version, symbol)
            )
        """
            )
        )

        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_mu_ts_version
                ON market_universe (ts_version)
        """
            )
        )

        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_mu_symbol
                ON market_universe (symbol)
        """
            )
        )

        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_mu_rank
                ON market_universe (ts_version, rank)
        """
            )
        )

        logger.info("Created table: market_universe")

        # 3. market_universe_versions
        await session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS market_universe_versions (
                ts_version BIGINT PRIMARY KEY,
                ts_eval BIGINT NOT NULL,

                status TEXT NOT NULL DEFAULT 'building',

                universe_size INTEGER,
                eligible_count INTEGER,

                eligible_5m INTEGER,
                eligible_15m INTEGER,
                eligible_1h INTEGER,
                eligible_4h INTEGER,

                global_regime TEXT,
                global_strength REAL,

                avg_quality_score REAL,
                min_final_score REAL,
                max_final_score REAL,

                source_version BIGINT,
                fallback_reason TEXT,

                config_hash TEXT NOT NULL,
                execution_time_seconds REAL,
                notes TEXT,

                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """
            )
        )

        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_muv_status
                ON market_universe_versions (status)
        """
            )
        )

        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_muv_published
                ON market_universe_versions (ts_version)
                WHERE status = 'published'
        """
            )
        )

        logger.info("Created table: market_universe_versions")

        # 4. market_regime_history
        await session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS market_regime_history (
                ts_eval BIGINT PRIMARY KEY,

                global_regime TEXT NOT NULL,
                global_strength REAL NOT NULL,
                regime_confidence REAL NOT NULL,

                regime_1d TEXT,
                regime_1d_strength REAL,
                regime_4h TEXT,
                regime_4h_strength REAL,
                regime_1h TEXT,
                regime_1h_strength REAL,

                basket_size INTEGER,
                basket_symbols TEXT[],

                basket_adx_median REAL,
                basket_atr_close_median REAL,
                basket_ema_slope_median REAL,
                basket_volume_median REAL,

                is_stale BOOLEAN DEFAULT false,
                stale_reason TEXT,
                last_valid_ts BIGINT,

                config_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """
            )
        )

        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_mrh_regime
                ON market_regime_history (global_regime)
        """
            )
        )

        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_mrh_not_stale
                ON market_regime_history (ts_eval)
                WHERE is_stale = false
        """
            )
        )

        logger.info("Created table: market_regime_history")

        # 5. market_selection_whitelist (для white/black list)
        await session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS market_selection_lists (
                symbol TEXT NOT NULL,
                list_type TEXT NOT NULL CHECK (list_type IN ('whitelist', 'blacklist')),
                reason TEXT,
                added_at TIMESTAMPTZ DEFAULT NOW(),
                added_by TEXT,
                expires_at TIMESTAMPTZ,
                PRIMARY KEY (symbol, list_type)
            )
        """
            )
        )

        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_msl_type
                ON market_selection_lists (list_type)
        """
            )
        )

        logger.info("Created table: market_selection_lists")

        await session.commit()
        logger.info("All market_selection tables created successfully")
