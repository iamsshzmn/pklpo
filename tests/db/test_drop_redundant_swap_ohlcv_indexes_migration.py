from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


def test_drop_redundant_swap_ohlcv_indexes_verifies_expected_index_shape() -> None:
    from src.db.migrations.migrate_drop_redundant_swap_ohlcv_indexes import (
        DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL,
        REDUNDANT_SWAP_OHLCV_INDEXES,
    )

    assert REDUNDANT_SWAP_OHLCV_INDEXES == (
        "idx_swap_ohlcv_p_symbol_timeframe_timestamp",
        "idx_swap_ohlcv_p_lookup",
    )
    assert "pg_index" in DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL
    assert "indisprimary IS FALSE" in DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL
    assert "indnkeyatts = 3" in DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL
    assert "indpred IS NULL" in DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL
    assert "indexprs IS NULL" in DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL
    assert "SELECT a.attname::text" in DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL
    assert "DROP INDEX IF EXISTS idx_swap_ohlcv_p_symbol_timeframe_timestamp" in (
        DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL
    )
    assert "DROP INDEX IF EXISTS idx_swap_ohlcv_p_lookup" in (
        DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL
    )


def test_drop_redundant_swap_ohlcv_indexes_migration_is_registered_after_390() -> None:
    from src.db.migration_registry import get_migrations

    migrations = get_migrations()
    ids = [migration.id for migration in migrations]

    assert ids[ids.index("390_research_tf_infinite_retention") + 1] == (
        "400_drop_redundant_swap_ohlcv_indexes"
    )


@pytest.mark.asyncio
async def test_drop_redundant_swap_ohlcv_indexes_executes_single_statements() -> None:
    from src.db.migrations import migrate_drop_redundant_swap_ohlcv_indexes as mig

    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    class _Ctx:
        async def __aenter__(self) -> Any:
            return session

        async def __aexit__(self, *_: Any) -> None:
            pass

    with patch(
        "src.db.migrations.migrate_drop_redundant_swap_ohlcv_indexes.get_db_session",
        return_value=_Ctx(),
    ):
        await mig.migrate_drop_redundant_swap_ohlcv_indexes()

    assert session.execute.call_count == 3
    statements = [str(call.args[0]) for call in session.execute.call_args_list]
    assert statements[0].strip().startswith("DO $$")
    assert (
        statements[1]
        .strip()
        .startswith("DROP INDEX IF EXISTS idx_swap_ohlcv_p_symbol_timeframe_timestamp")
    )
    assert (
        statements[2].strip().startswith("DROP INDEX IF EXISTS idx_swap_ohlcv_p_lookup")
    )
    session.commit.assert_called_once()
