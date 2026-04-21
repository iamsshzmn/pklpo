from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.candles.infrastructure import repair_audit_repository as module
from src.candles.infrastructure.repair_audit_repository import SwapRepairAuditRepository


@dataclass
class _FakeResult:
    rowcount: int = 0


@dataclass
class _FakeSession:
    executed: list[tuple[str, Any]] = field(default_factory=list)
    committed: bool = False

    async def execute(self, stmt: Any, params: Any = None) -> _FakeResult:
        self.executed.append((str(stmt), params))
        return _FakeResult(rowcount=len(params) if isinstance(params, list) else 1)

    async def commit(self) -> None:
        self.committed = True


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, *_args: Any) -> None:
        return None


def _session_factory(session: _FakeSession):
    def _factory() -> _FakeSessionContext:
        return _FakeSessionContext(session)

    return _factory


def _base_record(**overrides: Any) -> dict[str, Any]:
    record = {
        "dag_id": "dag",
        "dag_run_id": "run",
        "logical_date": None,
        "symbol": "BTC-USDT-SWAP",
        "timeframe": "1m",
        "mode": "apply",
        "strategy": "gap-repair",
        "auto_apply_window": False,
        "auto_apply_incomplete": False,
        "verified": True,
        "gap_tasks": 1,
        "requested_bars": 1,
        "remaining_gap_tasks": 0,
        "remaining_requested_bars": 0,
        "rows_written": 1,
        "fetch_calls": 1,
        "window_start_ts_ms": 0,
        "window_end_ts_ms": 60_000,
        "verification_method": "gap-detection",
        "preview_payload": {},
        "summary_payload": {"symbol": "BTC-USDT-SWAP"},
        "requested_conf": {},
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_insert_records_propagates_new_semantic_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    monkeypatch.setattr(module, "get_db_session", _session_factory(session))

    record = _base_record(
        outcome="partial",
        received_bars=2,
        remaining_missing_before=5,
        remaining_missing_after=3,
        progress=2,
        api_fill_ratio=0.5,
        write_success_ratio=1.0,
    )
    count = await SwapRepairAuditRepository().insert_records([record])

    assert count == 1
    stmt_sql, params = session.executed[0]
    assert "outcome" in stmt_sql
    assert "received_bars" in stmt_sql
    assert "api_fill_ratio" in stmt_sql
    assert len(params) == 1
    bound = params[0]
    assert bound["outcome"] == "partial"
    assert bound["received_bars"] == 2
    assert bound["remaining_missing_before"] == 5
    assert bound["remaining_missing_after"] == 3
    assert bound["progress"] == 2
    assert bound["api_fill_ratio"] == 0.5
    assert bound["write_success_ratio"] == 1.0


@pytest.mark.asyncio
async def test_insert_records_tolerates_missing_new_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    monkeypatch.setattr(module, "get_db_session", _session_factory(session))

    record = _base_record()
    await SwapRepairAuditRepository().insert_records([record])

    _stmt_sql, params = session.executed[0]
    bound = params[0]
    assert bound["outcome"] is None
    assert bound["received_bars"] is None
    assert bound["remaining_missing_before"] is None
    assert bound["remaining_missing_after"] is None
    assert bound["progress"] is None
    assert bound["api_fill_ratio"] is None
    assert bound["write_success_ratio"] is None
