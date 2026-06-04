from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from src.candles.application.eligibility.ports import EligibilitySnapshot
from src.candles.domain.eligibility import CoverageFacts, EligibilityState

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.candles.domain.eligibility import EligibilityVerdict

RESEARCH_TIMEFRAMES = ("1H", "4H", "1D", "1W", "1M")


class EligibilitySqlRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def read_coverage_facts(self) -> list[CoverageFacts]:
        result = await self._session.execute(
            text(
                """
                SELECT
                    symbol,
                    timeframe,
                    COUNT(*) AS actual_bars,
                    MIN(timestamp) AS first_ts,
                    MAX(timestamp) AS last_ts,
                    100.0::float AS coverage_pct
                FROM swap_ohlcv_p
                WHERE timeframe = ANY(:timeframes)
                GROUP BY symbol, timeframe
                ORDER BY symbol, timeframe
                """
            ),
            {"timeframes": list(RESEARCH_TIMEFRAMES)},
        )
        rows = result.mappings().all()
        return [
            CoverageFacts(
                symbol=str(row["symbol"]),
                timeframe=str(row["timeframe"]),
                actual_bars=int(row["actual_bars"]),
                coverage_pct=(
                    float(row["coverage_pct"])
                    if row.get("coverage_pct") is not None
                    else None
                ),
                first_ts=int(row["first_ts"]) if row.get("first_ts") is not None else None,
                last_ts=int(row["last_ts"]) if row.get("last_ts") is not None else None,
            )
            for row in rows
        ]

    async def get_current(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> EligibilitySnapshot | None:
        result = await self._session.execute(
            text(
                """
                SELECT symbol, timeframe, state
                FROM ops.feature_eligibility
                WHERE symbol = :symbol AND timeframe = :timeframe
                """
            ),
            {"symbol": symbol, "timeframe": timeframe},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return EligibilitySnapshot(
            symbol=str(row["symbol"]),
            timeframe=str(row["timeframe"]),
            state=EligibilityState(str(row["state"])),
        )

    async def upsert_verdict(
        self,
        verdict: EligibilityVerdict,
        *,
        evaluator_run_id: str,
    ) -> None:
        await self._session.execute(
            text(
                """
                INSERT INTO ops.feature_eligibility (
                    symbol,
                    timeframe,
                    state,
                    required_bars,
                    actual_bars,
                    coverage_pct,
                    first_ts,
                    last_ts,
                    reason_flags,
                    can_compute_features,
                    can_score,
                    can_train_ml,
                    context_only,
                    detail,
                    previous_state,
                    state_changed_at,
                    evaluated_at,
                    evaluator_run_id
                )
                VALUES (
                    :symbol,
                    :timeframe,
                    :state,
                    :required_bars,
                    :actual_bars,
                    :coverage_pct,
                    :first_ts,
                    :last_ts,
                    :reason_flags,
                    :can_compute_features,
                    :can_score,
                    :can_train_ml,
                    :context_only,
                    CAST(:detail AS jsonb),
                    NULL,
                    now(),
                    now(),
                    :evaluator_run_id
                )
                ON CONFLICT (symbol, timeframe) DO UPDATE
                SET
                    previous_state = ops.feature_eligibility.state,
                    state_changed_at = CASE
                        WHEN ops.feature_eligibility.state <> EXCLUDED.state THEN now()
                        ELSE ops.feature_eligibility.state_changed_at
                    END,
                    state = EXCLUDED.state,
                    required_bars = EXCLUDED.required_bars,
                    actual_bars = EXCLUDED.actual_bars,
                    coverage_pct = EXCLUDED.coverage_pct,
                    first_ts = EXCLUDED.first_ts,
                    last_ts = EXCLUDED.last_ts,
                    reason_flags = EXCLUDED.reason_flags,
                    can_compute_features = EXCLUDED.can_compute_features,
                    can_score = EXCLUDED.can_score,
                    can_train_ml = EXCLUDED.can_train_ml,
                    context_only = EXCLUDED.context_only,
                    detail = EXCLUDED.detail,
                    evaluated_at = now(),
                    evaluator_run_id = EXCLUDED.evaluator_run_id
                """
            ),
            _verdict_params(verdict, evaluator_run_id=evaluator_run_id),
        )

    async def append_transition(
        self,
        *,
        verdict: EligibilityVerdict,
        from_state: EligibilityState | None,
        evaluator_run_id: str,
    ) -> None:
        await self._session.execute(
            text(
                """
                INSERT INTO ops.feature_eligibility_transitions (
                    symbol,
                    timeframe,
                    from_state,
                    to_state,
                    actual_bars,
                    reason_flags,
                    evaluator_run_id
                )
                VALUES (
                    :symbol,
                    :timeframe,
                    :from_state,
                    :to_state,
                    :actual_bars,
                    :reason_flags,
                    :evaluator_run_id
                )
                """
            ),
            {
                "symbol": verdict.symbol,
                "timeframe": verdict.timeframe,
                "from_state": from_state.value if from_state is not None else None,
                "to_state": verdict.state.value,
                "actual_bars": verdict.actual_bars,
                "reason_flags": [flag.value for flag in verdict.reason_flags],
                "evaluator_run_id": evaluator_run_id,
            },
        )


def _verdict_params(
    verdict: EligibilityVerdict,
    *,
    evaluator_run_id: str,
) -> dict[str, Any]:
    return {
        "symbol": verdict.symbol,
        "timeframe": verdict.timeframe,
        "state": verdict.state.value,
        "required_bars": verdict.required_bars,
        "actual_bars": verdict.actual_bars,
        "coverage_pct": verdict.coverage_pct,
        "first_ts": verdict.first_ts,
        "last_ts": verdict.last_ts,
        "reason_flags": [flag.value for flag in verdict.reason_flags],
        "can_compute_features": verdict.can_compute_features,
        "can_score": verdict.can_score,
        "can_train_ml": verdict.can_train_ml,
        "context_only": verdict.context_only,
        "detail": json.dumps(verdict.detail),
        "evaluator_run_id": evaluator_run_id,
    }
