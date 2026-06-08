from __future__ import annotations

import json
from typing import Any

import pytest


class _Result:
    def __init__(
        self,
        *,
        rows: list[Any] | None = None,
        mappings_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self._rows = rows or []
        self._mappings_rows = mappings_rows or []

    def fetchall(self) -> list[Any]:
        return self._rows

    def mappings(self) -> _Result:
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._mappings_rows


class _FakeSession:
    def __init__(self, results: list[_Result] | None = None) -> None:
        self.results = results or []
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []
        self.committed = False
        self.rolled_back = False

    async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _Result:
        self.statements.append(str(statement))
        self.params.append(params)
        if self.results:
            return self.results.pop(0)
        return _Result()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class _SessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> _FakeSession:
        return self.session

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


def _session_factory(session: _FakeSession):
    def _factory() -> _SessionContext:
        return _SessionContext(session)

    return _factory


class _FakeSettings:
    class _Candles:
        def __init__(self, *, db_alignment_trigger_enabled: bool) -> None:
            self.db_alignment_trigger_enabled = db_alignment_trigger_enabled

    def __init__(self, *, db_alignment_trigger_enabled: bool) -> None:
        self.candles = self._Candles(
            db_alignment_trigger_enabled=db_alignment_trigger_enabled
        )


@pytest.mark.asyncio
async def test_constraint_migration_emits_not_valid_catalog_guarded_constraints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.db.migrations import migrate_add_swap_ohlcv_constraints as module

    session = _FakeSession()
    monkeypatch.setattr(module, "get_db_session", _session_factory(session))

    await module.migrate_add_swap_ohlcv_constraints()

    sql = "\n".join(session.statements)
    assert "pg_constraint" in sql
    assert "conrelid = 'swap_ohlcv_p'::regclass" in sql
    assert "END;\n$$" in sql
    assert "ADD CONSTRAINT chk_swap_ohlcv_p_timestamp_nonneg" in sql
    assert "CHECK (timestamp >= 0) NOT VALID" in sql
    assert "ADD CONSTRAINT chk_swap_ohlcv_p_prices_positive" in sql
    assert "CHECK (open > 0 AND high > 0 AND low > 0 AND close > 0) NOT VALID" in sql
    assert "ADD CONSTRAINT chk_swap_ohlcv_p_volume_nonneg" in sql
    assert "CHECK (volume >= 0) NOT VALID" in sql
    assert "ADD CONSTRAINT chk_swap_ohlcv_p_geometry" in sql
    assert "high >= GREATEST(open, close)" in sql
    assert "low <= LEAST(open, close)" in sql
    assert "ADD CONSTRAINT chk_swap_ohlcv_p_timeframe_supported" in sql
    assert "'1m','5m','15m','30m','1H','4H','12H','1D','1W','1M'" in sql
    assert session.committed


@pytest.mark.asyncio
async def test_validate_migration_audits_dirty_constraint_without_validating_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.db.migrations import migrate_validate_swap_ohlcv_constraints as module

    session = _FakeSession(
        results=[
            _Result(),
            _Result(),
            _Result(rows=[("swap_ohlcv_p_2026_05",)]),
            _Result(mappings_rows=[{"symbol": "BTC-USDT-SWAP", "timestamp": 1}]),
        ]
    )
    monkeypatch.setattr(module, "get_db_session", _session_factory(session))

    await module.migrate_validate_swap_ohlcv_constraints()

    sql = "\n".join(session.statements)
    assert "CREATE TABLE IF NOT EXISTS ops.swap_ohlcv_constraint_validation_audit" in sql
    assert not any(
        "CREATE SCHEMA" in statement and "CREATE TABLE" in statement
        for statement in session.statements
    )
    assert "swap_ohlcv_p_2026_05" in sql
    validate_sql = [
        statement for statement in session.statements if "VALIDATE CONSTRAINT" in statement
    ]
    assert not any("chk_swap_ohlcv_p_timestamp_nonneg" in sql for sql in validate_sql)
    assert len(validate_sql) == 8
    assert sum(
        1 for sql in validate_sql if "ALTER TABLE swap_ohlcv_p VALIDATE CONSTRAINT" in sql
    ) == 4
    assert any(params and params["status"] == "dirty" for params in session.params)
    assert any(
        params
        and json.loads(params["violations_sample"])
        == [{"symbol": "BTC-USDT-SWAP", "timestamp": 1}]
        for params in session.params
    )
    assert session.committed


@pytest.mark.asyncio
async def test_validate_migration_validates_clean_constraints_when_one_is_dirty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.db.migrations import migrate_validate_swap_ohlcv_constraints as module

    session = _FakeSession(
        results=[
            _Result(),
            _Result(),
            _Result(rows=[("swap_ohlcv_p_2026_05",)]),
            _Result(mappings_rows=[]),
            _Result(mappings_rows=[]),
            _Result(mappings_rows=[{"symbol": "BTC-USDT-SWAP", "volume": -1}]),
            _Result(mappings_rows=[]),
            _Result(mappings_rows=[]),
        ]
    )
    monkeypatch.setattr(module, "get_db_session", _session_factory(session))

    await module.migrate_validate_swap_ohlcv_constraints()

    validate_sql = [
        statement for statement in session.statements if "VALIDATE CONSTRAINT" in statement
    ]
    assert len(validate_sql) == 8
    assert any("chk_swap_ohlcv_p_timestamp_nonneg" in sql for sql in validate_sql)
    assert any("chk_swap_ohlcv_p_prices_positive" in sql for sql in validate_sql)
    assert not any("chk_swap_ohlcv_p_volume_nonneg" in sql for sql in validate_sql)
    assert any("chk_swap_ohlcv_p_geometry" in sql for sql in validate_sql)
    assert any("chk_swap_ohlcv_p_timeframe_supported" in sql for sql in validate_sql)
    assert not any(
        "ALTER TABLE swap_ohlcv_p VALIDATE CONSTRAINT chk_swap_ohlcv_p_volume_nonneg"
        in sql
        for sql in validate_sql
    )
    assert any(params and params["status"] == "dirty" for params in session.params)
    assert sum(
        1 for params in session.params if params and params["status"] == "validated"
    ) == 4
    assert not any(params and params["status"] == "skipped" for params in session.params)


@pytest.mark.asyncio
async def test_alignment_trigger_migration_creates_disabled_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.db.migrations import migrate_add_swap_ohlcv_alignment_trigger as module

    session = _FakeSession()
    monkeypatch.setattr(module, "get_db_session", _session_factory(session))

    await module.migrate_add_swap_ohlcv_alignment_trigger()

    sql = "\n".join(session.statements)
    assert "CREATE OR REPLACE FUNCTION public.swap_ohlcv_p_align_check()" in sql
    assert "WHEN '1W'" in sql
    assert "345600000" in sql
    assert "WHEN '1M'" in sql
    assert "CREATE TRIGGER trg_swap_ohlcv_p_align_check" in sql
    assert "END;\n$$" in sql
    assert "pg_trigger" in sql
    assert "ALTER TABLE swap_ohlcv_p DISABLE TRIGGER trg_swap_ohlcv_p_align_check" in sql
    assert session.committed


@pytest.mark.asyncio
async def test_alignment_trigger_migration_can_enable_trigger_via_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.db.migrations import migrate_add_swap_ohlcv_alignment_trigger as module

    session = _FakeSession()
    monkeypatch.setattr(module, "get_db_session", _session_factory(session))
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: _FakeSettings(db_alignment_trigger_enabled=True),
    )

    await module.migrate_add_swap_ohlcv_alignment_trigger()

    sql = "\n".join(session.statements)
    assert "ALTER TABLE swap_ohlcv_p ENABLE TRIGGER trg_swap_ohlcv_p_align_check" in sql
    assert session.committed
