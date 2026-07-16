"""
Persistence Layer for Market Selection

Handles:
- Atomic upserts to market_scores_tf
- Atomic version publication to market_universe
- Version status management
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.market_selection.domain.quality_gate import QualityResult
    from src.market_selection.domain.regime import GlobalRegime
    from src.market_selection.domain.scoring import TFScore
    from src.market_selection.domain.universe import UniverseEntry, UniverseVersion

logger = logging.getLogger(__name__)


class LockTimeoutError(RuntimeError):
    """Raised when PostgreSQL advisory lock wait exceeds configured timeout."""


class MarketSelectionPersistence:
    """
    Persistence operations for market selection results.

    All operations are designed to be atomic and idempotent.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_scores_tf(
        self,
        ts_eval: int,
        timeframe: str,
        scores: list[TFScore],
        quality_results: dict[str, QualityResult],
        metrics_raw: dict[str, dict],
        regime: GlobalRegime,
        config_hash: str,
        window_days: int,
    ) -> int:
        """
        Upsert per-TF scores to market_scores_tf.

        Returns number of rows upserted.
        """
        if not scores:
            return 0

        values = []
        for score in scores:
            quality = quality_results.get(score.symbol)
            raw = metrics_raw.get(score.symbol, {})

            values.append(
                {
                    "symbol": score.symbol,
                    "timeframe": timeframe,
                    "ts_eval": ts_eval,
                    # Raw metrics
                    "vol_raw": raw.get("vol_raw"),
                    "trend_q_raw": raw.get("trend_q_raw"),
                    "noise_raw": raw.get("noise_raw"),
                    "stability_raw": raw.get("stability_raw"),
                    "liq_raw": raw.get("liq_raw"),
                    # Normalized scores
                    "vol_score": score.vol_score,
                    "trend_q_score": score.trend_q_score,
                    "noise_score": score.noise_score,
                    "stability_score": score.stability_score,
                    "liq_score": score.liq_score,
                    # Aggregated
                    "score_tf_base": score.score_tf_base,
                    "score_tf": score.score_tf,
                    # Quality
                    "quality_score": quality.quality_score if quality else 1.0,
                    "fill_rate": quality.fill_rate if quality else 1.0,
                    "gap_rate": quality.gap_rate if quality else 0.0,
                    "data_lag_seconds": quality.data_lag_seconds if quality else 0,
                    "valid_bars": quality.valid_bars if quality else 0,
                    "expected_bars": quality.expected_bars if quality else 0,
                    "eligible": quality.eligible if quality else True,
                    # Regime
                    "global_regime": regime.regime.value,
                    "global_strength": regime.strength,
                    "regime_confidence": regime.confidence,
                    # Metadata
                    "reason_flags": [
                        f.value for f in (quality.reason_flags if quality else [])
                    ],
                    "window_days": window_days,
                    "config_hash": config_hash,
                }
            )

        # Build UPSERT query
        query = text(
            """
            INSERT INTO market_scores_tf (
                symbol, timeframe, ts_eval,
                vol_raw, trend_q_raw, noise_raw, stability_raw, liq_raw,
                vol_score, trend_q_score, noise_score, stability_score, liq_score,
                score_tf_base, score_tf,
                quality_score, fill_rate, gap_rate, data_lag_seconds,
                valid_bars, expected_bars, eligible,
                global_regime, global_strength, regime_confidence,
                reason_flags, window_days, config_hash
            ) VALUES (
                :symbol, :timeframe, :ts_eval,
                :vol_raw, :trend_q_raw, :noise_raw, :stability_raw, :liq_raw,
                :vol_score, :trend_q_score, :noise_score, :stability_score, :liq_score,
                :score_tf_base, :score_tf,
                :quality_score, :fill_rate, :gap_rate, :data_lag_seconds,
                :valid_bars, :expected_bars, :eligible,
                :global_regime, :global_strength, :regime_confidence,
                :reason_flags, :window_days, :config_hash
            )
            ON CONFLICT (symbol, timeframe, ts_eval)
            DO UPDATE SET
                vol_raw = EXCLUDED.vol_raw,
                trend_q_raw = EXCLUDED.trend_q_raw,
                noise_raw = EXCLUDED.noise_raw,
                stability_raw = EXCLUDED.stability_raw,
                liq_raw = EXCLUDED.liq_raw,
                vol_score = EXCLUDED.vol_score,
                trend_q_score = EXCLUDED.trend_q_score,
                noise_score = EXCLUDED.noise_score,
                stability_score = EXCLUDED.stability_score,
                liq_score = EXCLUDED.liq_score,
                score_tf_base = EXCLUDED.score_tf_base,
                score_tf = EXCLUDED.score_tf,
                quality_score = EXCLUDED.quality_score,
                fill_rate = EXCLUDED.fill_rate,
                gap_rate = EXCLUDED.gap_rate,
                data_lag_seconds = EXCLUDED.data_lag_seconds,
                valid_bars = EXCLUDED.valid_bars,
                expected_bars = EXCLUDED.expected_bars,
                eligible = EXCLUDED.eligible,
                global_regime = EXCLUDED.global_regime,
                global_strength = EXCLUDED.global_strength,
                regime_confidence = EXCLUDED.regime_confidence,
                reason_flags = EXCLUDED.reason_flags,
                window_days = EXCLUDED.window_days,
                config_hash = EXCLUDED.config_hash,
                created_at = NOW()
        """
        )

        for val in values:
            await self.session.execute(query, val)

        logger.info(f"Upserted {len(values)} scores for {timeframe}")
        return len(values)

    async def insert_universe_version(
        self,
        version: UniverseVersion,
    ) -> None:
        """
        Insert a new universe version record.

        Status should be 'building' initially.
        """
        query = text(
            """
            INSERT INTO market_universe_versions (
                ts_version, ts_eval, status, universe_size, eligible_count,
                eligible_5m, eligible_15m, eligible_1h, eligible_4h,
                global_regime, global_strength,
                avg_quality_score, min_final_score, max_final_score,
                source_version, fallback_reason,
                config_hash, execution_time_seconds, notes
            ) VALUES (
                :ts_version, :ts_eval, :status, :universe_size, :eligible_count,
                :eligible_5m, :eligible_15m, :eligible_1h, :eligible_4h,
                :global_regime, :global_strength,
                :avg_quality_score, :min_final_score, :max_final_score,
                :source_version, :fallback_reason,
                :config_hash, :execution_time_seconds, :notes
            )
            ON CONFLICT (ts_version) DO UPDATE SET
                status = EXCLUDED.status,
                universe_size = EXCLUDED.universe_size,
                eligible_count = EXCLUDED.eligible_count,
                eligible_5m = EXCLUDED.eligible_5m,
                eligible_15m = EXCLUDED.eligible_15m,
                eligible_1h = EXCLUDED.eligible_1h,
                eligible_4h = EXCLUDED.eligible_4h,
                global_regime = EXCLUDED.global_regime,
                global_strength = EXCLUDED.global_strength,
                avg_quality_score = EXCLUDED.avg_quality_score,
                min_final_score = EXCLUDED.min_final_score,
                max_final_score = EXCLUDED.max_final_score,
                source_version = EXCLUDED.source_version,
                fallback_reason = EXCLUDED.fallback_reason,
                execution_time_seconds = EXCLUDED.execution_time_seconds,
                notes = EXCLUDED.notes
        """
        )

        await self.session.execute(query, version.to_dict())
        logger.info(
            f"Inserted universe version {version.ts_version} with status {version.status.value}"
        )

    async def insert_universe_entries(
        self,
        ts_version: int,
        entries: list[UniverseEntry],
        config_hash: str,
    ) -> int:
        """
        Insert universe entries for a version.

        Returns number of rows inserted.
        """
        if not entries:
            return 0

        query = text(
            """
            INSERT INTO market_universe (
                ts_version, symbol, final_score, rank,
                score_4h, score_1h, score_15m, score_5m,
                best_tf, worst_tf,
                score_std_7d, score_std_30d, days_in_universe,
                global_regime_at_time, global_strength_at_time,
                reason_flags, penalty_applied,
                config_hash, source_version
            ) VALUES (
                :ts_version, :symbol, :final_score, :rank,
                :score_4h, :score_1h, :score_15m, :score_5m,
                :best_tf, :worst_tf,
                :score_std_7d, :score_std_30d, :days_in_universe,
                :global_regime_at_time, :global_strength_at_time,
                :reason_flags, :penalty_applied,
                :config_hash, :source_version
            )
            ON CONFLICT (ts_version, symbol) DO UPDATE SET
                final_score = EXCLUDED.final_score,
                rank = EXCLUDED.rank,
                score_4h = EXCLUDED.score_4h,
                score_1h = EXCLUDED.score_1h,
                score_15m = EXCLUDED.score_15m,
                score_5m = EXCLUDED.score_5m,
                best_tf = EXCLUDED.best_tf,
                worst_tf = EXCLUDED.worst_tf,
                score_std_7d = EXCLUDED.score_std_7d,
                score_std_30d = EXCLUDED.score_std_30d,
                days_in_universe = EXCLUDED.days_in_universe,
                global_regime_at_time = EXCLUDED.global_regime_at_time,
                global_strength_at_time = EXCLUDED.global_strength_at_time,
                reason_flags = EXCLUDED.reason_flags,
                penalty_applied = EXCLUDED.penalty_applied
        """
        )

        for entry in entries:
            data = entry.to_dict()
            data["ts_version"] = ts_version
            data["config_hash"] = config_hash
            await self.session.execute(query, data)

        logger.info(
            f"Inserted {len(entries)} universe entries for version {ts_version}"
        )
        return len(entries)

    async def update_version_status(
        self,
        ts_version: int,
        status: str,
        notes: str | None = None,
    ) -> None:
        """Update status of a universe version."""
        query = text(
            """
            UPDATE market_universe_versions
            SET status = :status, notes = COALESCE(:notes, notes)
            WHERE ts_version = :ts_version
        """
        )

        await self.session.execute(
            query,
            {"ts_version": ts_version, "status": status, "notes": notes},
        )
        logger.info(f"Updated version {ts_version} status to {status}")

    async def copy_previous_universe(
        self,
        new_ts_version: int,
        source_ts_version: int,
        config_hash: str,
    ) -> int:
        """
        Copy entries from previous universe to new version.

        Used for fallback.
        Returns number of rows copied.
        """
        metrics = await self.copy_previous_universe_with_metrics(
            new_ts_version=new_ts_version,
            source_ts_version=source_ts_version,
            config_hash=config_hash,
        )
        return metrics["inserted_count"]

    async def copy_previous_universe_with_metrics(
        self,
        new_ts_version: int,
        source_ts_version: int,
        config_hash: str,
    ) -> dict[str, int]:
        """
        Copy previous universe with deterministic, transactional metrics.

        Metrics:
        - source_count: rows in source snapshot
        - source_duplicates: duplicate symbols in source snapshot
        - inserted_count: rows inserted in destination snapshot
        - skipped_conflicts: deduped source rows that conflicted on target PK
        """
        query = text(
            """
            WITH source_rows AS (
                SELECT
                    symbol, final_score, rank,
                    score_4h, score_1h, score_15m, score_5m,
                    best_tf, worst_tf,
                    score_std_7d, score_std_30d, days_in_universe,
                    global_regime_at_time, global_strength_at_time,
                    reason_flags, penalty_applied
                FROM market_universe
                WHERE ts_version = :source_ts_version
            ),
            source_stats AS (
                SELECT
                    COUNT(*)::int AS source_count,
                    (COUNT(*) - COUNT(DISTINCT symbol))::int AS source_duplicates
                FROM source_rows
            ),
            source_dedup AS (
                SELECT DISTINCT ON (symbol)
                    symbol, final_score, rank,
                    score_4h, score_1h, score_15m, score_5m,
                    best_tf, worst_tf,
                    score_std_7d, score_std_30d, days_in_universe,
                    global_regime_at_time, global_strength_at_time,
                    reason_flags, penalty_applied
                FROM source_rows
                ORDER BY symbol, rank
            ),
            inserted AS (
                INSERT INTO market_universe (
                    ts_version, symbol, final_score, rank,
                    score_4h, score_1h, score_15m, score_5m,
                    best_tf, worst_tf,
                    score_std_7d, score_std_30d, days_in_universe,
                    global_regime_at_time, global_strength_at_time,
                    reason_flags, penalty_applied,
                    config_hash, source_version
                )
                SELECT
                    :new_ts_version, symbol, final_score, rank,
                    score_4h, score_1h, score_15m, score_5m,
                    best_tf, worst_tf,
                    score_std_7d, score_std_30d, days_in_universe + 1,
                    global_regime_at_time, global_strength_at_time,
                    reason_flags, penalty_applied,
                    :config_hash, :source_ts_version
                FROM source_dedup
                ON CONFLICT (ts_version, symbol) DO NOTHING
                RETURNING 1
            )
            SELECT
                source_stats.source_count,
                source_stats.source_duplicates,
                (SELECT COUNT(*)::int FROM inserted) AS inserted_count,
                (
                    source_stats.source_count
                    - source_stats.source_duplicates
                    - (SELECT COUNT(*)::int FROM inserted)
                )::int AS skipped_conflicts
            FROM source_stats
        """
        )

        result = await self.session.execute(
            query,
            {
                "new_ts_version": new_ts_version,
                "source_ts_version": source_ts_version,
                "config_hash": config_hash,
            },
        )
        row = result.mappings().one()
        metrics = {
            "source_count": int(row["source_count"]),
            "source_duplicates": int(row["source_duplicates"]),
            "inserted_count": int(row["inserted_count"]),
            "skipped_conflicts": int(row["skipped_conflicts"]),
        }
        logger.info(
            "Fallback copy metrics: source=%s inserted=%s skipped=%s source_duplicates=%s "
            "(source_version=%s target_version=%s)",
            metrics["source_count"],
            metrics["inserted_count"],
            metrics["skipped_conflicts"],
            metrics["source_duplicates"],
            source_ts_version,
            new_ts_version,
        )
        return metrics

    async def acquire_write_lock_for_ts_version(
        self,
        ts_version: int,
        lock_timeout_ms: int = 10_000,
    ) -> float:
        """
        Acquire PostgreSQL advisory transaction lock for ts_version.

        PostgreSQL-specific behavior:
        - lock key: ts_version (signed int8)
        - lock lifetime: current transaction
        """
        min_int8 = -(2**63)
        max_int8 = 2**63 - 1
        if not (min_int8 <= ts_version <= max_int8):
            raise ValueError(f"ts_version out of signed BIGINT range: {ts_version}")

        lock_start = time.monotonic()
        await self.session.execute(
            text("SELECT set_config('lock_timeout', :lock_timeout, true)"),
            {"lock_timeout": f"{lock_timeout_ms}ms"},
        )

        try:
            await self.session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": ts_version},
            )
        except Exception as exc:
            message = str(exc).lower()
            if (
                "lock timeout" in message
                or "canceling statement due to lock timeout" in message
            ):
                raise LockTimeoutError(
                    f"Advisory lock timeout for ts_version={ts_version} after {lock_timeout_ms}ms"
                ) from exc
            raise

        wait_seconds = time.monotonic() - lock_start
        logger.info(
            "Acquired write advisory lock for ts_version=%s in %.3fs",
            ts_version,
            wait_seconds,
        )
        return wait_seconds

    async def insert_regime_history(
        self,
        ts_eval: int,
        regime: GlobalRegime,
        config_hash: str,
    ) -> None:
        """Insert regime history record."""
        query = text(
            """
            INSERT INTO market_regime_history (
                ts_eval, global_regime, global_strength, regime_confidence,
                regime_1d, regime_1d_strength,
                regime_4h, regime_4h_strength,
                regime_1h, regime_1h_strength,
                basket_size, basket_symbols,
                basket_adx_median, basket_atr_close_median, basket_ema_slope_median,
                is_stale, config_hash
            ) VALUES (
                :ts_eval, :global_regime, :global_strength, :regime_confidence,
                :regime_1d, :regime_1d_strength,
                :regime_4h, :regime_4h_strength,
                :regime_1h, :regime_1h_strength,
                :basket_size, :basket_symbols,
                :basket_adx_median, :basket_atr_close_median, :basket_ema_slope_median,
                :is_stale, :config_hash
            )
            ON CONFLICT (ts_eval) DO UPDATE SET
                global_regime = EXCLUDED.global_regime,
                global_strength = EXCLUDED.global_strength,
                regime_confidence = EXCLUDED.regime_confidence,
                regime_1d = EXCLUDED.regime_1d,
                regime_1d_strength = EXCLUDED.regime_1d_strength,
                regime_4h = EXCLUDED.regime_4h,
                regime_4h_strength = EXCLUDED.regime_4h_strength,
                regime_1h = EXCLUDED.regime_1h,
                regime_1h_strength = EXCLUDED.regime_1h_strength,
                basket_size = EXCLUDED.basket_size,
                basket_symbols = EXCLUDED.basket_symbols,
                basket_adx_median = EXCLUDED.basket_adx_median,
                basket_atr_close_median = EXCLUDED.basket_atr_close_median,
                basket_ema_slope_median = EXCLUDED.basket_ema_slope_median,
                is_stale = EXCLUDED.is_stale
        """
        )

        data = regime.to_dict()
        data["ts_eval"] = ts_eval
        data["is_stale"] = regime.stale
        data["config_hash"] = config_hash

        await self.session.execute(query, data)
        logger.info(f"Inserted regime history for ts_eval {ts_eval}")

    async def cleanup_old_data(
        self,
        scores_retention_days: int = 180,
        universe_retention_days: int = 90,
    ) -> tuple[int, int]:
        """
        Clean up old data beyond retention period.

        Returns (scores_deleted, universe_deleted)
        """
        # Cleanup old scores
        scores_query = text(
            """
            DELETE FROM market_scores_tf
            WHERE created_at < NOW() - INTERVAL ':days days'
        """.replace(":days", str(scores_retention_days))
        )

        scores_result = await self.session.execute(scores_query)
        scores_deleted = scores_result.rowcount

        # Cleanup old universe entries and versions
        universe_query = text(
            """
            WITH old_versions AS (
                SELECT ts_version FROM market_universe_versions
                WHERE created_at < NOW() - INTERVAL ':days days'
            )
            DELETE FROM market_universe
            WHERE ts_version IN (SELECT ts_version FROM old_versions)
        """.replace(":days", str(universe_retention_days))
        )

        universe_result = await self.session.execute(universe_query)
        universe_deleted = universe_result.rowcount

        # Cleanup version records
        version_query = text(
            """
            DELETE FROM market_universe_versions
            WHERE created_at < NOW() - INTERVAL ':days days'
        """.replace(":days", str(universe_retention_days))
        )

        await self.session.execute(version_query)

        logger.info(
            f"Cleaned up: {scores_deleted} score rows, {universe_deleted} universe rows"
        )
        return scores_deleted, universe_deleted
