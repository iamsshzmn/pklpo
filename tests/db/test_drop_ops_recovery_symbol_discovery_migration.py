"""Tests for migration 490: DROP IF EXISTS ops.recovery_symbol_discovery.

Verifies idempotency: migration must succeed both when the table exists and
when it does not (DROP IF EXISTS semantics).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_session_ctx() -> tuple[object, AsyncMock]:
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    class _Ctx:
        async def __aenter__(self) -> AsyncMock:
            return session

        async def __aexit__(self, *_: object) -> None:
            pass

    return _Ctx(), session


@pytest.mark.asyncio
async def test_migration_executes_drop_if_exists() -> None:
    """Migration issues DROP IF EXISTS ops.recovery_symbol_discovery."""
    from src.db.migrations.migrate_drop_ops_recovery_symbol_discovery import (
        migrate_drop_ops_recovery_symbol_discovery,
    )

    ctx, session = _make_session_ctx()

    with patch(
        "src.db.migrations.migrate_drop_ops_recovery_symbol_discovery.get_db_session",
        return_value=ctx,
    ):
        await migrate_drop_ops_recovery_symbol_discovery()

    assert session.execute.call_count == 1
    sql = str(session.execute.call_args[0][0])
    assert "DROP TABLE IF EXISTS ops.recovery_symbol_discovery" in sql
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_migration_is_idempotent_when_table_absent() -> None:
    """Running migration twice must not raise even if the table is already gone."""
    from src.db.migrations.migrate_drop_ops_recovery_symbol_discovery import (
        migrate_drop_ops_recovery_symbol_discovery,
    )

    ctx, _session = _make_session_ctx()

    with patch(
        "src.db.migrations.migrate_drop_ops_recovery_symbol_discovery.get_db_session",
        return_value=ctx,
    ):
        # Both calls must complete without exception
        await migrate_drop_ops_recovery_symbol_discovery()
        await migrate_drop_ops_recovery_symbol_discovery()


@pytest.mark.asyncio
async def test_migration_registered_as_490() -> None:
    """490_drop_ops_recovery_symbol_discovery must appear in migration_registry."""
    from src.db.migration_registry import get_migrations

    migrations = get_migrations()
    ids = [m.id for m in migrations]
    assert "490_drop_ops_recovery_symbol_discovery" in ids

    # Must come after 480
    idx_480 = ids.index("480_ops_symbol_succession")
    idx_490 = ids.index("490_drop_ops_recovery_symbol_discovery")
    assert idx_490 > idx_480
