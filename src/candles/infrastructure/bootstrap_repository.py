from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text

from src.candles.application.bootstrap.dto import BootstrapProgress
from src.candles.infrastructure.repair_repository import RepairCandlesRepository
from src.utils.session_utils import get_db_session


class BootstrapCandlesRepository(RepairCandlesRepository):
    """Extends RepairCandlesRepository with BootstrapStatePort methods."""

    async def upsert_bootstrap_state(
        self,
        *,
        symbol: str,
        timeframe: str,
        lookback_days: int,
        target_start_ts: int,
        target_end_ts: int,
        expected_bars: int,
        status: str,
        checkpoint_ts: int | None = None,
        current_min_ts: int | None = None,
        current_max_ts: int | None = None,
        actual_bars: int | None = None,
        missing_bars: int | None = None,
        coverage_pct: float | None = None,
        bootstrap_completed: bool = False,
        completed_at_ms: int | None = None,
        last_run_id: str | None = None,
        last_error: str | None = None,
        error_streak: int = 0,
    ) -> None:
        completed_at = (
            datetime.fromtimestamp(completed_at_ms / 1000, tz=UTC)
            if completed_at_ms is not None
            else None
        )

        async def _operation() -> None:
            async with get_db_session() as session:
                await session.execute(
                    text(
                        """
                        INSERT INTO ops.swap_ohlcv_bootstrap_state (
                            symbol, timeframe, lookback_days,
                            target_start_ts, target_end_ts,
                            checkpoint_ts, current_min_ts, current_max_ts,
                            expected_bars, actual_bars, missing_bars, coverage_pct,
                            status, bootstrap_completed, completed_at,
                            last_run_id, last_error, error_streak,
                            created_at, updated_at
                        ) VALUES (
                            :symbol, :timeframe, :lookback_days,
                            :target_start_ts, :target_end_ts,
                            :checkpoint_ts, :current_min_ts, :current_max_ts,
                            :expected_bars, :actual_bars, :missing_bars, :coverage_pct,
                            :status, :bootstrap_completed, :completed_at,
                            :last_run_id, :last_error, :error_streak,
                            now(), now()
                        )
                        ON CONFLICT (symbol, timeframe) DO UPDATE SET
                            lookback_days       = EXCLUDED.lookback_days,
                            target_start_ts     = EXCLUDED.target_start_ts,
                            target_end_ts       = EXCLUDED.target_end_ts,
                            checkpoint_ts       = COALESCE(EXCLUDED.checkpoint_ts,
                                                           ops.swap_ohlcv_bootstrap_state.checkpoint_ts),
                            current_min_ts      = COALESCE(EXCLUDED.current_min_ts,
                                                           ops.swap_ohlcv_bootstrap_state.current_min_ts),
                            current_max_ts      = COALESCE(EXCLUDED.current_max_ts,
                                                           ops.swap_ohlcv_bootstrap_state.current_max_ts),
                            expected_bars       = EXCLUDED.expected_bars,
                            actual_bars         = COALESCE(EXCLUDED.actual_bars,
                                                           ops.swap_ohlcv_bootstrap_state.actual_bars),
                            missing_bars        = COALESCE(EXCLUDED.missing_bars,
                                                           ops.swap_ohlcv_bootstrap_state.missing_bars),
                            coverage_pct        = COALESCE(EXCLUDED.coverage_pct,
                                                           ops.swap_ohlcv_bootstrap_state.coverage_pct),
                            status              = EXCLUDED.status,
                            bootstrap_completed = EXCLUDED.bootstrap_completed,
                            completed_at        = COALESCE(EXCLUDED.completed_at,
                                                           ops.swap_ohlcv_bootstrap_state.completed_at),
                            last_run_id         = COALESCE(EXCLUDED.last_run_id,
                                                           ops.swap_ohlcv_bootstrap_state.last_run_id),
                            last_error          = EXCLUDED.last_error,
                            error_streak        = EXCLUDED.error_streak,
                            updated_at          = now()
                        """
                    ),
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "lookback_days": lookback_days,
                        "target_start_ts": target_start_ts,
                        "target_end_ts": target_end_ts,
                        "checkpoint_ts": checkpoint_ts,
                        "current_min_ts": current_min_ts,
                        "current_max_ts": current_max_ts,
                        "expected_bars": expected_bars,
                        "actual_bars": actual_bars,
                        "missing_bars": missing_bars,
                        "coverage_pct": coverage_pct,
                        "status": status,
                        "bootstrap_completed": bootstrap_completed,
                        "completed_at": completed_at,
                        "last_run_id": last_run_id,
                        "last_error": last_error,
                        "error_streak": error_streak,
                    },
                )
                await session.commit()

        await self._run_with_db_retry(_operation)

    async def get_bootstrap_state(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> BootstrapProgress | None:
        async def _operation() -> BootstrapProgress | None:
            async with get_db_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT
                            symbol, timeframe, lookback_days,
                            target_start_ts, target_end_ts,
                            checkpoint_ts, current_min_ts, current_max_ts,
                            expected_bars, actual_bars, missing_bars, coverage_pct,
                            status, bootstrap_completed, error_streak, last_error
                        FROM ops.swap_ohlcv_bootstrap_state
                        WHERE symbol = :symbol AND timeframe = :timeframe
                        LIMIT 1
                        """
                    ),
                    {"symbol": symbol, "timeframe": timeframe},
                )
                row = result.fetchone()
            if row is None:
                return None
            return BootstrapProgress(
                symbol=str(row[0]),
                timeframe=str(row[1]),
                lookback_days=int(row[2]),
                target_start_ts=int(row[3]),
                target_end_ts=int(row[4]),
                checkpoint_ts=int(row[5]) if row[5] is not None else None,
                current_min_ts=int(row[6]) if row[6] is not None else None,
                current_max_ts=int(row[7]) if row[7] is not None else None,
                expected_bars=int(row[8]),
                actual_bars=int(row[9]) if row[9] is not None else None,
                missing_bars=int(row[10]) if row[10] is not None else None,
                coverage_pct=float(row[11]) if row[11] is not None else None,
                status=str(row[12]),
                bootstrap_completed=bool(row[13]),
                error_streak=int(row[14]),
                last_error=str(row[15]) if row[15] is not None else None,
            )

        return await self._run_with_db_retry(_operation)
