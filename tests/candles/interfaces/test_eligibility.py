from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import pytest

from src.candles.domain.eligibility import CoverageFacts, EligibilityState


@dataclass
class _FakeSession:
    rows: list[dict[str, Any]]
    calls: list[tuple[str, dict[str, Any]]]

    async def execute(
        self,
        statement: Any,
        params: dict[str, Any] | None = None,
    ) -> Any:
        self.calls.append((str(statement), params or {}))
        return _Result(self.rows)


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> _Result:
        return self

    def first(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[dict[str, Any]]:
        return self._rows

    def scalar(self) -> Any:
        if not self._rows:
            return None
        return next(iter(self._rows[0].values()))


@dataclass
class _PushMetricsSession:
    calls: list[str]

    async def execute(self, statement: Any) -> Any:
        sql = str(statement)
        self.calls.append(sql)
        if "GROUP BY timeframe, state" in sql:
            return _Result([{"timeframe": "1H", "state": "insufficient_history", "count": 1}])
        if "WHERE can_compute_features = TRUE" in sql:
            return _Result([])
        if "FROM ops.feature_eligibility_transitions" in sql:
            return _Result([])
        if "WHERE state = 'invalid_history'" in sql:
            return _Result([{"count": 0}])
        if "MAX(evaluated_at)" in sql:
            return _Result([{"stale_seconds": 0.0}])
        if "required_bars" in sql and "actual_bars" in sql:
            return _Result(
                [
                    {
                        "symbol": "BTC-USDT-SWAP",
                        "timeframe": "1H",
                        "warmup_bars_remaining": 125,
                    }
                ]
            )
        return _Result([])


class _Repo:
    def __init__(self, _session: Any, **_: Any) -> None:
        self.records: dict[tuple[str, str], object] = {}

    async def read_coverage_facts(self) -> list[CoverageFacts]:
        return [
            CoverageFacts(
                symbol="BTC-USDT-SWAP",
                timeframe="1H",
                actual_bars=500,
                coverage_pct=100.0,
            )
        ]

    async def get_current(self, *, symbol: str, timeframe: str) -> object | None:
        return self.records.get((symbol, timeframe))

    async def upsert_verdict(self, verdict: object, *, evaluator_run_id: str) -> None:
        self.records[(verdict.symbol, verdict.timeframe)] = verdict

    async def append_transition(
        self,
        *,
        verdict: object,
        from_state: EligibilityState | None,
        evaluator_run_id: str,
    ) -> None:
        return None


@pytest.mark.asyncio
async def test_refresh_eligibility_runs_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.candles.interfaces import eligibility

    push_calls: list[object] = []

    @asynccontextmanager
    async def _session_scope():
        yield object()

    monkeypatch.setattr(eligibility, "get_db_session", _session_scope)
    monkeypatch.setattr(eligibility, "EligibilitySqlRepository", _Repo)
    async def _push_refresh_metrics(session: object) -> None:
        push_calls.append(session)

    monkeypatch.setattr(eligibility, "_push_refresh_metrics", _push_refresh_metrics)

    result = await eligibility.refresh_eligibility(evaluator_run_id="elig-run")

    assert result == {"evaluated": 1, "transitions": 1}
    assert len(push_calls) == 1


@pytest.mark.asyncio
async def test_read_helpers_query_capability_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.candles.interfaces import eligibility

    calls: list[tuple[str, dict[str, Any]]] = []
    session = _FakeSession(
        rows=[
            {
                "symbol": "BTC-USDT-SWAP",
                "timeframe": "1H",
                "state": "eligible",
                "can_compute_features": True,
                "can_score": True,
                "can_train_ml": True,
                "context_only": False,
                "reason_flags": [],
                "actual_bars": 500,
                "required_bars": 500,
                "coverage_pct": 100.0,
                "evaluated_at": None,
            }
        ],
        calls=calls,
    )

    @asynccontextmanager
    async def _session_scope():
        yield session

    monkeypatch.setattr(eligibility, "get_db_session", _session_scope)

    assert await eligibility.is_eligible("BTC-USDT-SWAP", "1H")
    assert await eligibility.filter_eligible(
        [("BTC-USDT-SWAP", "1H"), ("ETH-USDT-SWAP", "1H")]
    ) == [("BTC-USDT-SWAP", "1H"), ("ETH-USDT-SWAP", "1H")]
    assert await eligibility.eligible_symbols("1H") == ["BTC-USDT-SWAP"]
    state = await eligibility.get_state("BTC-USDT-SWAP", "1H")

    assert state is not None
    assert state.state == "eligible"
    assert "can_compute_features = TRUE" in calls[0][0]


@pytest.mark.asyncio
async def test_push_refresh_metrics_includes_warmup_bars_remaining(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.candles.interfaces import eligibility

    captured: dict[str, Any] = {}
    session = _PushMetricsSession(calls=[])

    def _push_feature_eligibility_metrics(snapshot: dict[str, Any]) -> bool:
        captured.update(snapshot)
        return True

    monkeypatch.setattr(
        eligibility,
        "push_feature_eligibility_metrics",
        _push_feature_eligibility_metrics,
    )

    await eligibility._push_refresh_metrics(session)

    assert captured["warmup_remaining"] == {("BTC-USDT-SWAP", "1H"): 125}
