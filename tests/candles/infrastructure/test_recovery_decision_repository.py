"""Tests for RecoveryDecisionRepository insert and cooldown query.

These are integration-style tests that use a real (or mocked) DB session.
Since we use mocks here, the tests verify the SQL contracts without DB access.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from src.candles.infrastructure.recovery_decision_repository import (
    RecoveryDecisionRepository,
    _INSERT_SQL,
)


class _FakeRow:
    def __init__(self, *values: Any) -> None:
        self._values = values

    def __getitem__(self, idx: int) -> Any:
        return self._values[idx]


def _make_session_context(
    *, fetchone_return: Any = None, fetchall_return: list | None = None
):
    """Build a fake asyncpg/SQLAlchemy session context manager."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    if fetchone_return is not None:
        result = MagicMock()
        result.fetchone = MagicMock(return_value=fetchone_return)
        session.execute.return_value = result
    elif fetchall_return is not None:
        result = MagicMock()
        result.fetchall = MagicMock(return_value=fetchall_return)
        session.execute.return_value = result
    else:
        result = MagicMock()
        result.fetchone = MagicMock(return_value=_FakeRow(999, datetime.now(UTC)))
        result.fetchall = MagicMock(return_value=[])
        session.execute.return_value = result

    class _Ctx:
        async def __aenter__(self) -> Any:
            return session

        async def __aexit__(self, *_: Any) -> None:
            pass

    return _Ctx(), session


@pytest.mark.asyncio
async def test_insert_decision_returns_id_and_created_at() -> None:
    now = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)
    fake_row = _FakeRow(42, now)

    ctx, session = _make_session_context(fetchone_return=fake_row)

    with patch(
        "src.candles.infrastructure.recovery_decision_repository.get_db_session",
        return_value=ctx,
    ):
        repo = RecoveryDecisionRepository()
        result = await repo.insert_decision(
            controller_dag_id="pipeline_recovery_controller",
            controller_dag_run_id="run_123",
            logical_date=None,
            decision_status="skip",
            action_kind="none",
            target_dag_id=None,
            target_run_id=None,
            reason="no_recovery_needed",
            symbol=None,
            timeframe=None,
            priority=0,
            cooldown_until=None,
        )

    assert result["id"] == 42
    assert result["created_at"] == now
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_insert_decision_calls_commit_after_execute() -> None:
    fake_row = _FakeRow(1, datetime.now(UTC))
    ctx, session = _make_session_context(fetchone_return=fake_row)

    with patch(
        "src.candles.infrastructure.recovery_decision_repository.get_db_session",
        return_value=ctx,
    ):
        repo = RecoveryDecisionRepository()
        await repo.insert_decision(
            controller_dag_id="pipeline_recovery_controller",
            controller_dag_run_id=None,
            logical_date=None,
            decision_status="triggered",
            action_kind="repair",
            target_dag_id="okx_swap_repair_v1",
            target_run_id=None,
            reason="repair_gap_detected",
            symbol="BTC-USDT-SWAP",
            timeframe="1H",
            priority=5,
            cooldown_until=datetime.now(UTC) + timedelta(hours=4),
        )

    session.commit.assert_called_once()
    # execute was called once (INSERT)
    session.execute.assert_called_once()


def test_insert_decision_sql_compiles_json_payload_binds_for_asyncpg() -> None:
    """JSONB payload binds must compile as parameters, not raw :param::jsonb."""
    compiled = str(_INSERT_SQL.compile(dialect=postgresql.dialect()))

    assert ":precheck_payload::jsonb" not in compiled
    assert ":trigger_conf::jsonb" not in compiled
    assert ":safety_payload::jsonb" not in compiled


@pytest.mark.asyncio
async def test_get_cooldown_rows_returns_empty_when_no_rows() -> None:
    ctx, _session = _make_session_context(fetchall_return=[])

    with patch(
        "src.candles.infrastructure.recovery_decision_repository.get_db_session",
        return_value=ctx,
    ):
        repo = RecoveryDecisionRepository()
        rows = await repo.get_cooldown_rows(
            action_kind="repair",
            target_dag_id="okx_swap_repair_v1",
            symbol="BTC-USDT-SWAP",
            timeframe="1H",
            cooldown_minutes=240,
        )

    assert rows == []


@pytest.mark.asyncio
async def test_get_cooldown_rows_parses_returned_rows() -> None:
    now = datetime.now(UTC)
    fake_rows = [
        _FakeRow(
            10,
            now,
            "triggered",
            "repair",
            "okx_swap_repair_v1",
            "BTC-USDT-SWAP",
            "1H",
            None,
        ),
    ]
    ctx, _session = _make_session_context(fetchall_return=fake_rows)

    with patch(
        "src.candles.infrastructure.recovery_decision_repository.get_db_session",
        return_value=ctx,
    ):
        repo = RecoveryDecisionRepository()
        rows = await repo.get_cooldown_rows(
            action_kind="repair",
            target_dag_id="okx_swap_repair_v1",
            symbol="BTC-USDT-SWAP",
            timeframe="1H",
            cooldown_minutes=240,
        )

    assert len(rows) == 1
    assert rows[0]["id"] == 10
    assert rows[0]["decision_status"] == "triggered"
    assert rows[0]["action_kind"] == "repair"
    assert rows[0]["symbol"] == "BTC-USDT-SWAP"
    assert rows[0]["timeframe"] == "1H"


@pytest.mark.asyncio
async def test_get_cooldown_rows_query_uses_cooldown_key() -> None:
    """Verify the cooldown query receives the correct key parameters."""
    ctx, session = _make_session_context(fetchall_return=[])

    with patch(
        "src.candles.infrastructure.recovery_decision_repository.get_db_session",
        return_value=ctx,
    ):
        repo = RecoveryDecisionRepository()
        await repo.get_cooldown_rows(
            action_kind="bootstrap",
            target_dag_id="okx_swap_ohlcv_bootstrap_v1",
            symbol="ETH-USDT-SWAP",
            timeframe="4H",
            cooldown_minutes=120,
        )

    session.execute.assert_called_once()
    call_args = session.execute.call_args
    params = call_args[0][1]  # second positional arg is params dict
    assert params["action_kind"] == "bootstrap"
    assert params["target_dag_id"] == "okx_swap_ohlcv_bootstrap_v1"
    assert params["symbol"] == "ETH-USDT-SWAP"
    assert params["timeframe"]
