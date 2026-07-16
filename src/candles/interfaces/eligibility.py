from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from src.candles.application.eligibility import RefreshEligibilityUseCase
from src.candles.domain.eligibility import build_timeframe_policies
from src.candles.infrastructure.eligibility_repository import EligibilitySqlRepository
from src.candles.observability.prometheus import push_feature_eligibility_metrics
from src.config.settings import get_settings
from src.utils.session_utils import get_db_session


@dataclass(frozen=True)
class EligibilityRecord:
    symbol: str
    timeframe: str
    state: str
    can_compute_features: bool
    can_score: bool
    can_train_ml: bool
    context_only: bool
    reason_flags: list[str]
    actual_bars: int
    required_bars: int
    coverage_pct: float | None
    evaluated_at: Any


async def refresh_eligibility(*, evaluator_run_id: str | None = None) -> dict[str, int]:
    run_id = evaluator_run_id or f"feature-eligibility-{uuid4()}"
    policies = build_timeframe_policies(
        get_settings().features.warmup_bars_by_timeframe
    )
    async with get_db_session() as session:
        repository = EligibilitySqlRepository(session, policies=policies)
        summary = await RefreshEligibilityUseCase(
            coverage_reader=repository,
            repository=repository,
            policies=policies,
        ).run(evaluator_run_id=run_id)
        await _push_refresh_metrics(session)
    return {"evaluated": summary.evaluated, "transitions": summary.transitions}


async def _push_refresh_metrics(session: Any) -> None:
    try:
        state_rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT timeframe, state, COUNT(*) AS count
                    FROM ops.feature_eligibility
                    GROUP BY timeframe, state
                    """
                    )
                )
            )
            .mappings()
            .all()
        )
        eligible_rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT timeframe, COUNT(*) AS count
                    FROM ops.feature_eligibility
                    WHERE can_compute_features = TRUE
                    GROUP BY timeframe
                    """
                    )
                )
            )
            .mappings()
            .all()
        )
        transition_rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT timeframe, from_state, to_state
                    FROM ops.feature_eligibility_transitions
                    WHERE occurred_at >= now() - interval '1 day'
                    """
                    )
                )
            )
            .mappings()
            .all()
        )
        invalid_total = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM ops.feature_eligibility
                    WHERE state = 'invalid_history'
                    """
                )
            )
        ).scalar()
        stale_seconds = (
            await session.execute(
                text(
                    """
                    SELECT COALESCE(EXTRACT(EPOCH FROM now() - MAX(evaluated_at)), 0)
                    FROM ops.feature_eligibility
                    """
                )
            )
        ).scalar()
        warmup_rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT
                        symbol,
                        timeframe,
                        GREATEST(required_bars - actual_bars, 0) AS warmup_bars_remaining
                    FROM ops.feature_eligibility
                    WHERE required_bars > 0
                    """
                    )
                )
            )
            .mappings()
            .all()
        )
        push_feature_eligibility_metrics(
            {
                "state_counts": {
                    (str(row["timeframe"]), str(row["state"])): int(row["count"])
                    for row in state_rows
                },
                "eligible_counts": {
                    str(row["timeframe"]): int(row["count"]) for row in eligible_rows
                },
                "transitions": [dict(row) for row in transition_rows],
                "invalid_total": int(invalid_total or 0),
                "stale_seconds": float(stale_seconds or 0.0),
                "warmup_remaining": {
                    (str(row["symbol"]), str(row["timeframe"])): int(
                        row["warmup_bars_remaining"] or 0
                    )
                    for row in warmup_rows
                },
            }
        )
    except Exception:
        pass


async def is_eligible(symbol: str, timeframe: str) -> bool:
    async with get_db_session() as session:
        result = await session.execute(
            text(
                """
                SELECT can_compute_features
                FROM ops.feature_eligibility
                WHERE symbol = :symbol
                  AND timeframe = :timeframe
                  AND can_compute_features = TRUE
                """
            ),
            {"symbol": symbol, "timeframe": timeframe},
        )
        return bool(result.scalar())


async def filter_eligible(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    eligible: list[tuple[str, str]] = []
    for symbol, timeframe in pairs:
        if await is_eligible(symbol, timeframe):
            eligible.append((symbol, timeframe))
    return eligible


async def eligible_symbols(timeframe: str) -> list[str]:
    async with get_db_session() as session:
        result = await session.execute(
            text(
                """
                SELECT symbol
                FROM ops.feature_eligibility
                WHERE timeframe = :timeframe
                  AND can_compute_features = TRUE
                ORDER BY symbol
                """
            ),
            {"timeframe": timeframe},
        )
        return [str(row["symbol"]) for row in result.mappings().all()]


async def get_state(symbol: str, timeframe: str) -> EligibilityRecord | None:
    async with get_db_session() as session:
        result = await session.execute(
            text(
                """
                SELECT
                    symbol,
                    timeframe,
                    state,
                    can_compute_features,
                    can_score,
                    can_train_ml,
                    context_only,
                    reason_flags,
                    actual_bars,
                    required_bars,
                    coverage_pct,
                    evaluated_at
                FROM ops.feature_eligibility
                WHERE symbol = :symbol AND timeframe = :timeframe
                """
            ),
            {"symbol": symbol, "timeframe": timeframe},
        )
        row = result.mappings().first()
    if row is None:
        return None
    return EligibilityRecord(
        symbol=str(row["symbol"]),
        timeframe=str(row["timeframe"]),
        state=str(row["state"]),
        can_compute_features=bool(row["can_compute_features"]),
        can_score=bool(row["can_score"]),
        can_train_ml=bool(row["can_train_ml"]),
        context_only=bool(row["context_only"]),
        reason_flags=list(row["reason_flags"] or []),
        actual_bars=int(row["actual_bars"]),
        required_bars=int(row["required_bars"]),
        coverage_pct=(
            float(row["coverage_pct"]) if row.get("coverage_pct") is not None else None
        ),
        evaluated_at=row["evaluated_at"],
    )
