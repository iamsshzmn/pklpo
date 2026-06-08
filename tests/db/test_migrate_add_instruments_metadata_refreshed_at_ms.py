from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.db.migrations.migrate_add_instruments_metadata_refreshed_at_ms import (
    migrate_add_instruments_metadata_refreshed_at_ms,
)


@dataclass
class _FakeResult:
    rowcount: int = 0
    scalar_value: Any = None
    rows: list[tuple[Any, ...]] = field(default_factory=list)

    def scalar(self) -> Any:
        return self.scalar_value

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows


@dataclass
class _FakeSession:
    results: list[_FakeResult] = field(default_factory=list)
    executed: list[str] = field(default_factory=list)
    committed: bool = False

    async def execute(self, stmt: Any, params: Any = None) -> _FakeResult:
        del params
        self.executed.append(str(stmt))
        return self.results.pop(0)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        return None


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


@pytest.mark.asyncio
async def test_migration_adds_and_backfills_metadata_refreshed_at_ms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession(results=[_FakeResult(), _FakeResult()])

    def _fake_get_db_session() -> _FakeSessionContext:
        return _FakeSessionContext(session)

    monkeypatch.setattr(
        "src.db.migrations.migrate_add_instruments_metadata_refreshed_at_ms.get_db_session",
        _fake_get_db_session,
    )

    await migrate_add_instruments_metadata_refreshed_at_ms()

    assert session.committed is True
    assert "metadata_refreshed_at_ms" in session.executed[0]
    assert "COALESCE" in session.executed[1]
