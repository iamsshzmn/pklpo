from __future__ import annotations

from typing import Any

import pytest

from src.candles.domain.eligibility import (
    CoverageFacts,
    EligibilityState,
    evaluate_feature_eligibility,
)


class _Result:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or []

    def mappings(self) -> _Result:
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows

    def first(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(
        self,
        statement: Any,
        params: dict[str, Any] | None = None,
    ) -> _Result:
        self.calls.append((str(statement), params or {}))
        return _Result(self.rows)


@pytest.mark.asyncio
async def test_repository_reads_coverage_facts_from_swap_ohlcv() -> None:
    from src.candles.infrastructure.eligibility_repository import (
        EligibilitySqlRepository,
    )

    session = _Session(
        [
            {
                "symbol": "BTC-USDT-SWAP",
                "timeframe": "1H",
                "actual_window_bars": 498,
                "total_bars": 900,
                "first_ts": 1,
                "last_ts": 500,
                "coverage_pct": 99.6,
                "missing_count": 2,
                "duplicate_count": 1,
                "misaligned_count": 0,
            }
        ]
    )
    repo = EligibilitySqlRepository(session)

    facts = await repo.read_coverage_facts()

    assert facts == [
        CoverageFacts(
            symbol="BTC-USDT-SWAP",
            timeframe="1H",
            actual_bars=498,
            coverage_pct=99.6,
            first_ts=1,
            last_ts=500,
            has_interior_gap=True,
            integrity_ok=False,
            detail={
                "total_bars": 900,
                "missing_count": 2,
                "duplicate_count": 1,
                "misaligned_count": 0,
            },
        )
    ]
    query = session.calls[0][0]
    assert "100.0::float AS coverage_pct" not in query
    assert "last_aligned" in query
    assert "generate_series" in query
    assert "raw_integrity" in query
    assert "duplicate_count" in query
    assert "actual_window_bars" in query
    assert "FROM swap_ohlcv_p" in session.calls[0][0]


@pytest.mark.asyncio
async def test_repository_upserts_verdict_and_appends_transition() -> None:
    from src.candles.infrastructure.eligibility_repository import (
        EligibilitySqlRepository,
    )

    session = _Session()
    repo = EligibilitySqlRepository(session)
    verdict = evaluate_feature_eligibility(
        CoverageFacts(
            symbol="BTC-USDT-SWAP",
            timeframe="1H",
            actual_bars=500,
            coverage_pct=100.0,
        )
    )

    await repo.upsert_verdict(verdict, evaluator_run_id="elig-run")
    await repo.append_transition(
        verdict=verdict,
        from_state=EligibilityState.INSUFFICIENT_HISTORY,
        evaluator_run_id="elig-run",
    )

    assert "INSERT INTO ops.feature_eligibility" in session.calls[0][0]
    assert "ON CONFLICT (symbol, timeframe) DO UPDATE" in session.calls[0][0]
    assert session.calls[0][1]["state"] == "eligible"
    assert "INSERT INTO ops.feature_eligibility_transitions" in session.calls[1][0]
    assert session.calls[1][1]["from_state"] == "insufficient_history"
    assert session.calls[1][1]["to_state"] == "eligible"
