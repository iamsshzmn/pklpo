from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from src.candles.application.eligibility.ports import EligibilitySnapshot
from src.candles.domain.eligibility import (
    TIMEFRAME_POLICIES,
    CoverageFacts,
    EligibilityState,
    TimeframeEligibilityPolicy,
)
from src.features.domain.timeframe import timeframe_to_seconds

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.candles.domain.eligibility import EligibilityVerdict

RESEARCH_TIMEFRAMES = ("1H", "4H", "1D", "1W", "1M")


class EligibilitySqlRepository:
    def __init__(
        self,
        session: AsyncSession,
        policies: dict[str, TimeframeEligibilityPolicy] | None = None,
    ) -> None:
        self._session = session
        self._policies = policies or TIMEFRAME_POLICIES

    async def read_coverage_facts(self) -> list[CoverageFacts]:
        policy_sql, policy_params = _policy_cte(self._policies)
        result = await self._session.execute(
            text(
                f"""
                WITH policy(timeframe, step_ms, required_bars) AS (
                    {policy_sql}
                ),
                raw AS (
                    SELECT
                        o.symbol,
                        o.timeframe,
                        o.timestamp,
                        p.step_ms,
                        p.required_bars
                    FROM swap_ohlcv_p o
                    JOIN policy p ON p.timeframe = o.timeframe
                ),
                raw_integrity AS (
                    SELECT
                        symbol,
                        timeframe,
                        COUNT(*) AS total_bars,
                        COUNT(*) - COUNT(DISTINCT timestamp) AS duplicate_count,
                        COUNT(*) FILTER (WHERE timestamp % step_ms <> 0) AS misaligned_count
                    FROM raw
                    GROUP BY symbol, timeframe
                ),
                last_aligned AS (
                    SELECT
                        symbol,
                        timeframe,
                        MAX(timestamp) AS last_ts
                    FROM raw
                    WHERE timestamp % step_ms = 0
                    GROUP BY symbol, timeframe
                ),
                window_bounds AS (
                    SELECT
                        l.symbol,
                        l.timeframe,
                        l.last_ts,
                        p.step_ms,
                        p.required_bars,
                        CASE
                            WHEN p.required_bars > 0
                            THEN l.last_ts - ((p.required_bars - 1) * p.step_ms)
                            ELSE l.last_ts
                        END AS window_start_ts
                    FROM last_aligned l
                    JOIN policy p ON p.timeframe = l.timeframe
                ),
                actual_window AS (
                    SELECT
                        w.symbol,
                        w.timeframe,
                        COUNT(DISTINCT r.timestamp) AS actual_window_bars,
                        MIN(r.timestamp) AS first_ts,
                        MAX(r.timestamp) AS last_ts
                    FROM window_bounds w
                    LEFT JOIN raw r
                      ON r.symbol = w.symbol
                     AND r.timeframe = w.timeframe
                     AND r.timestamp BETWEEN w.window_start_ts AND w.last_ts
                    GROUP BY w.symbol, w.timeframe
                ),
                expected_window AS (
                    SELECT
                        w.symbol,
                        w.timeframe,
                        expected_ts
                    FROM window_bounds w
                    CROSS JOIN LATERAL generate_series(
                        w.window_start_ts,
                        w.last_ts,
                        w.step_ms
                    ) AS expected_series(expected_ts)
                    WHERE w.required_bars > 0
                ),
                missing_window AS (
                    SELECT
                        e.symbol,
                        e.timeframe,
                        COUNT(*) AS missing_count
                    FROM expected_window e
                    LEFT JOIN raw r
                      ON r.symbol = e.symbol
                     AND r.timeframe = e.timeframe
                     AND r.timestamp = e.expected_ts
                    WHERE r.timestamp IS NULL
                    GROUP BY e.symbol, e.timeframe
                )
                SELECT
                    w.symbol,
                    w.timeframe,
                    COALESCE(a.actual_window_bars, 0) AS actual_window_bars,
                    ri.total_bars,
                    a.first_ts,
                    a.last_ts,
                    CASE
                        WHEN w.required_bars > 0
                        THEN ROUND(
                            100.0 * COALESCE(a.actual_window_bars, 0)
                            / NULLIF(w.required_bars, 0),
                            2
                        )
                        ELSE 100.0
                    END AS coverage_pct,
                    COALESCE(m.missing_count, 0) AS missing_count,
                    COALESCE(ri.duplicate_count, 0) AS duplicate_count,
                    COALESCE(ri.misaligned_count, 0) AS misaligned_count
                FROM window_bounds w
                LEFT JOIN actual_window a
                  ON a.symbol = w.symbol AND a.timeframe = w.timeframe
                LEFT JOIN raw_integrity ri
                  ON ri.symbol = w.symbol AND ri.timeframe = w.timeframe
                LEFT JOIN missing_window m
                  ON m.symbol = w.symbol AND m.timeframe = w.timeframe
                ORDER BY w.symbol, w.timeframe
                """
            ),
            policy_params,
        )
        rows = result.mappings().all()
        return [
            CoverageFacts(
                symbol=str(row["symbol"]),
                timeframe=str(row["timeframe"]),
                actual_bars=int(row["actual_window_bars"]),
                coverage_pct=(
                    float(row["coverage_pct"])
                    if row.get("coverage_pct") is not None
                    else None
                ),
                first_ts=int(row["first_ts"]) if row.get("first_ts") is not None else None,
                last_ts=int(row["last_ts"]) if row.get("last_ts") is not None else None,
                has_interior_gap=int(row.get("missing_count") or 0) > 0,
                integrity_ok=(
                    int(row.get("duplicate_count") or 0) == 0
                    and int(row.get("misaligned_count") or 0) == 0
                ),
                detail={
                    "total_bars": int(row.get("total_bars") or 0),
                    "missing_count": int(row.get("missing_count") or 0),
                    "duplicate_count": int(row.get("duplicate_count") or 0),
                    "misaligned_count": int(row.get("misaligned_count") or 0),
                },
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


def _policy_cte(
    policies: dict[str, TimeframeEligibilityPolicy],
) -> tuple[str, dict[str, Any]]:
    entries = [
        (timeframe, policy)
        for timeframe, policy in policies.items()
        if timeframe in RESEARCH_TIMEFRAMES
    ]
    if not entries:
        raise ValueError("at least one research timeframe policy is required")

    selects: list[str] = []
    params: dict[str, Any] = {}
    for index, (timeframe, policy) in enumerate(entries):
        tf_key = f"tf_{index}"
        step_key = f"step_ms_{index}"
        bars_key = f"required_bars_{index}"
        selects.append(
            f"SELECT :{tf_key} AS timeframe, :{step_key} AS step_ms, "
            f":{bars_key} AS required_bars"
        )
        params[tf_key] = timeframe
        params[step_key] = timeframe_to_seconds(timeframe) * 1000
        params[bars_key] = int(policy.required_bars)
    return "\n                    UNION ALL\n                    ".join(selects), params
