from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.market_selection import migrations


class _DummyResult:
    def __init__(self, value: bool) -> None:
        self._value = value

    def scalar(self) -> bool:
        return self._value


class _AsyncTxContext:
    async def __aenter__(self) -> "_AsyncTxContext":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> bool:
        return False


@pytest.mark.asyncio
async def test_run_market_selection_migrations_executes_all_sql_in_transaction() -> None:
    class _DummyFile:
        def __init__(self, name: str, content: str) -> None:
            self.name = name
            self._content = content

        def read_text(self, encoding: str = "utf-8") -> str:
            return self._content

        def __lt__(self, other: Any) -> bool:
            return self.name < other.name

    dummy_files = [
        _DummyFile("001_test.sql", "SELECT 1; SELECT 2;"),
        _DummyFile("002_test.sql", "SELECT 3;"),
    ]

    mock_dir = MagicMock(spec=Path)
    mock_dir.glob.return_value = dummy_files  # type: ignore[assignment]

    with patch.object(migrations, "MIGRATIONS_DIR", mock_dir):
        session = MagicMock()
        session.execute = AsyncMock()
        session.begin.return_value = _AsyncTxContext()

        await migrations.run_market_selection_migrations(session)

    assert session.execute.await_count == 3
    session.begin.assert_called_once()


@pytest.mark.asyncio
async def test_run_market_selection_migrations_handles_leading_comments() -> None:
    class _DummyFile:
        name = "001_comments.sql"

        @staticmethod
        def read_text(encoding: str = "utf-8") -> str:
            return """
            -- migration header
            -- one more comment

            CREATE TABLE IF NOT EXISTS test_table (id INTEGER);
            """

    mock_dir = MagicMock(spec=Path)
    mock_dir.glob.return_value = [_DummyFile()]  # type: ignore[assignment]

    with patch.object(migrations, "MIGRATIONS_DIR", mock_dir):
        session = MagicMock()
        session.execute = AsyncMock()
        session.begin.return_value = _AsyncTxContext()

        await migrations.run_market_selection_migrations(session)

    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_run_market_selection_migrations_is_idempotent_on_rerun() -> None:
    class _DummyFile:
        name = "001_idempotent.sql"

        @staticmethod
        def read_text(encoding: str = "utf-8") -> str:
            return "CREATE TABLE IF NOT EXISTS test_table (id INTEGER);"

    mock_dir = MagicMock(spec=Path)
    mock_dir.glob.return_value = [_DummyFile()]  # type: ignore[assignment]

    with patch.object(migrations, "MIGRATIONS_DIR", mock_dir):
        session = MagicMock()
        session.execute = AsyncMock()
        session.begin.return_value = _AsyncTxContext()

        await migrations.run_market_selection_migrations(session)
        await migrations.run_market_selection_migrations(session)

    assert session.execute.await_count == 2
    assert session.begin.call_count == 2


@pytest.mark.asyncio
async def test_run_market_selection_migrations_propagates_errors() -> None:
    class _ErrorFile:
        name = "001_error.sql"

        @staticmethod
        def read_text(encoding: str = "utf-8") -> str:
            return "SELECT 1;"

    mock_dir = MagicMock(spec=Path)
    mock_dir.glob.return_value = [_ErrorFile()]  # type: ignore[assignment]

    with patch.object(migrations, "MIGRATIONS_DIR", mock_dir):
        session = MagicMock()
        session.execute = AsyncMock(side_effect=RuntimeError("db error"))
        session.begin.return_value = _AsyncTxContext()

        with pytest.raises(RuntimeError, match="db error"):
            await migrations.run_market_selection_migrations(session)

    session.begin.assert_called_once()


@pytest.mark.asyncio
async def test_check_tables_exist_builds_correct_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _fake_execute(query: Any, params: dict[str, Any]) -> _DummyResult:
        calls.append({"query": str(query), "params": params})
        table_name = params["table_name"]
        return _DummyResult(table_name in {"market_scores_tf", "market_universe"})

    session = AsyncMock()
    session.execute.side_effect = _fake_execute

    def _fake_text(sql: str) -> str:
        return f"SQL:{sql.strip()[:20]}"

    monkeypatch.setattr(migrations, "text", _fake_text, raising=False)

    result = await migrations.check_tables_exist(session)

    expected_keys = {
        "market_scores_tf",
        "market_universe",
        "market_universe_versions",
        "market_regime_history",
    }
    assert set(result.keys()) == expected_keys
    assert result["market_scores_tf"] is True
    assert result["market_universe"] is True
    assert result["market_universe_versions"] is False
    assert result["market_regime_history"] is False

    called_tables = {call["params"]["table_name"] for call in calls}
    assert called_tables == expected_keys
