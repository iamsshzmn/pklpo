"""
Тесты для CLI commands.

Skipped: src.market_selection.cli was removed.
Delete this file once equivalent tests exist under the new module structure.
"""

import pytest

pytestmark = pytest.mark.skip(reason="src.market_selection.cli module was removed")

import argparse
from unittest.mock import AsyncMock, Mock, patch

import pytest

try:
    from src.market_selection.cli import commands
except ImportError:  # pragma: no cover - module removed; see pytestmark skip above
    commands = None  # type: ignore[assignment]


@pytest.fixture
def mock_engine():
    """Фикстура мок-движка БД."""
    return Mock()


@pytest.fixture
def mock_session():
    """Фикстура мок-сессии БД."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_run_pipeline_success(mock_engine, mock_session):
    """Тест успешного запуска пайплайна."""
    with patch("src.database.get_async_engine", return_value=mock_engine):
        with patch("sqlalchemy.ext.asyncio.AsyncSession") as mock_session_class:
            mock_session_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "src.market_selection.infrastructure.factory.build_market_selection_pipeline"
            ) as mock_pipeline_factory:
                mock_pipeline = Mock()
                mock_pipeline.run = AsyncMock(
                    return_value=Mock(
                        success=True,
                        ts_version=1000000,
                        universe_size=30,
                        status=Mock(value="published"),
                        global_regime=Mock(value="TREND_UP"),
                        execution_time_seconds=1.5,
                        error_message=None,
                    )
                )
                mock_pipeline_factory.return_value = mock_pipeline

                result = await commands._run_pipeline(top_n=30, dry_run=False)

                assert result["success"] is True
                assert result["ts_version"] == 1000000
                assert result["universe_size"] == 30
                assert result["status"] == "published"
                assert result["regime"] == "TREND_UP"
                assert result["execution_time"] == 1.5


@pytest.mark.asyncio
async def test_run_pipeline_dry_run(mock_engine, mock_session):
    """Тест dry-run режима."""
    with patch("src.database.get_async_engine", return_value=mock_engine):
        with patch("sqlalchemy.ext.asyncio.AsyncSession") as mock_session_class:
            mock_session_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "src.market_selection.infrastructure.factory.build_market_selection_pipeline"
            ) as mock_pipeline_factory:
                mock_pipeline = Mock()
                mock_pipeline.db.resolve_ts_eval = AsyncMock(return_value=1000000)
                mock_pipeline._compute_regime = AsyncMock(
                    return_value=Mock(
                        regime=Mock(value="TREND_UP"),
                        strength=0.8,
                    )
                )
                mock_pipeline_factory.return_value = mock_pipeline

                result = await commands._run_pipeline(top_n=30, dry_run=True)

                assert result["dry_run"] is True
                assert result["ts_eval"] == 1000000
                assert result["regime"] == "TREND_UP"
                assert result["strength"] == 0.8


@pytest.mark.asyncio
async def test_get_status(mock_engine, mock_session):
    """Тест получения статуса."""
    mock_rows = [
        (
            1000000,
            1000000,
            "published",
            30,
            "TREND_UP",
            0.8,
            1.5,
            "hash123",
            "2024-01-01 00:00:00",
        ),
        (
            999000,
            999000,
            "published",
            28,
            "RANGE",
            0.6,
            1.2,
            "hash122",
            "2024-01-01 00:00:00",
        ),
    ]

    mock_result = Mock()
    mock_result.fetchall = Mock(return_value=mock_rows)
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("src.database.get_async_engine", return_value=mock_engine):
        with patch("sqlalchemy.ext.asyncio.AsyncSession") as mock_session_class:
            mock_session_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await commands._get_status()

            assert "versions" in result
            assert len(result["versions"]) == 2
            assert result["versions"][0]["ts_version"] == 1000000
            assert result["versions"][0]["status"] == "published"
            assert result["versions"][0]["universe_size"] == 30


@pytest.mark.asyncio
async def test_explain_symbol_in_universe(mock_engine, mock_session):
    """Тест объяснения символа в вселенной."""
    # Мок версии
    version_result = Mock()
    version_result.fetchone = Mock(return_value=(1000000, 1000000))
    mock_session.execute = AsyncMock(side_effect=[version_result, Mock(), Mock()])

    # Мок вселенной
    universe_result = Mock()
    universe_result.fetchone = Mock(
        return_value=(
            0.85,  # final_score
            1,  # rank
            "1H",  # best_tf
            "5M",  # worst_tf
            0.8,  # score_4h
            0.85,  # score_1h
            0.7,  # score_15m
            0.6,  # score_5m
            [],  # reason_flags
            0.0,  # penalty_applied
        )
    )
    mock_session.execute = AsyncMock(
        side_effect=[version_result, universe_result, Mock()]
    )

    # Мок TF scores
    scores_result = Mock()
    scores_result.fetchall = Mock(
        return_value=[
            (
                "1H",
                0.85,
                0.95,
                0.98,
                0.01,
                True,
                [],
                0.8,
                0.9,
                0.7,
                0.95,
                0.9,
            )
        ]
    )
    mock_session.execute = AsyncMock(
        side_effect=[version_result, universe_result, scores_result]
    )

    with patch("src.database.get_async_engine", return_value=mock_engine):
        with patch("sqlalchemy.ext.asyncio.AsyncSession") as mock_session_class:
            mock_session_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await commands._explain_symbol("BTC-USDT")

            assert result["symbol"] == "BTC-USDT"
            assert result["in_universe"] is True
            assert result["ts_version"] == 1000000
            assert "universe" in result
            assert result["universe"]["rank"] == 1
            assert result["universe"]["final_score"] == 0.85
            assert len(result["tf_scores"]) == 1


@pytest.mark.asyncio
async def test_explain_symbol_not_in_universe(mock_engine, mock_session):
    """Тест объяснения символа не в вселенной."""
    version_result = Mock()
    version_result.fetchone = Mock(return_value=(1000000, 1000000))
    universe_result = Mock()
    universe_result.fetchone = Mock(return_value=None)
    scores_result = Mock()
    scores_result.fetchall = Mock(return_value=[])

    mock_session.execute = AsyncMock(
        side_effect=[version_result, universe_result, scores_result]
    )

    with patch("src.database.get_async_engine", return_value=mock_engine):
        with patch("sqlalchemy.ext.asyncio.AsyncSession") as mock_session_class:
            mock_session_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await commands._explain_symbol("BTC-USDT")

            assert result["symbol"] == "BTC-USDT"
            assert result["in_universe"] is False
            assert "universe" not in result


@pytest.mark.asyncio
async def test_explain_symbol_no_version(mock_engine, mock_session):
    """Тест объяснения символа без версии."""
    version_result = Mock()
    version_result.fetchone = Mock(return_value=None)
    mock_session.execute = AsyncMock(return_value=version_result)

    with patch("src.database.get_async_engine", return_value=mock_engine):
        with patch("sqlalchemy.ext.asyncio.AsyncSession") as mock_session_class:
            mock_session_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await commands._explain_symbol("BTC-USDT")

            assert "error" in result
            assert result["error"] == "No published universe found"


@pytest.mark.asyncio
async def test_run_migrations(mock_engine, mock_session):
    """Тест запуска миграций."""
    before = {"table1": False, "table2": False}
    after = {"table1": True, "table2": True}

    with patch("src.database.get_async_engine", return_value=mock_engine):
        with patch("sqlalchemy.ext.asyncio.AsyncSession") as mock_session_class:
            mock_session_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "src.market_selection.migrations.check_tables_exist",
                side_effect=[before, after],
            ):
                with patch(
                    "src.market_selection.migrations.run_market_selection_migrations"
                ) as mock_migrate:
                    mock_migrate.return_value = None

                    result = await commands._run_migrations()

                    assert result["before"] == before
                    assert result["after"] == after
                    assert result["created"] == ["table1", "table2"]


@pytest.mark.asyncio
async def test_get_universe(mock_engine, mock_session):
    """Тест получения вселенной."""
    mock_rows = [
        (
            "BTC-USDT",
            0.85,
            1,
            "1H",
            0.8,
            0.85,
            0.7,
            0.6,
            "TREND_UP",
        ),
        (
            "ETH-USDT",
            0.80,
            2,
            "4H",
            0.8,
            0.75,
            0.7,
            0.65,
            "TREND_UP",
        ),
    ]

    mock_result = Mock()
    mock_result.fetchall = Mock(return_value=mock_rows)
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("src.database.get_async_engine", return_value=mock_engine):
        with patch("sqlalchemy.ext.asyncio.AsyncSession") as mock_session_class:
            mock_session_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await commands._get_universe(limit=10)

            assert len(result) == 2
            assert result[0]["symbol"] == "BTC-USDT"
            assert result[0]["rank"] == 1
            assert result[0]["score"] == 0.85
            assert result[1]["symbol"] == "ETH-USDT"
            assert result[1]["rank"] == 2


@pytest.mark.asyncio
async def test_get_regime(mock_engine, mock_session):
    """Тест получения режима."""
    mock_row = (
        1000000,  # ts_eval
        "TREND_UP",  # global_regime
        0.8,  # global_strength
        0.9,  # regime_confidence
        "TREND_UP",  # regime_1d
        "TREND_UP",  # regime_4h
        "TREND_UP",  # regime_1h
        10,  # basket_size
        25.0,  # basket_adx_median
        0.02,  # basket_atr_close_median
        "2024-01-01 00:00:00",  # created_at
    )

    mock_result = Mock()
    mock_result.fetchone = Mock(return_value=mock_row)
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("src.database.get_async_engine", return_value=mock_engine):
        with patch("sqlalchemy.ext.asyncio.AsyncSession") as mock_session_class:
            mock_session_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await commands._get_regime()

            assert result["ts_eval"] == 1000000
            assert result["regime"] == "TREND_UP"
            assert result["strength"] == 0.8
            assert result["confidence"] == 0.9
            assert result["basket_size"] == 10


@pytest.mark.asyncio
async def test_get_regime_no_data(mock_engine, mock_session):
    """Тест получения режима без данных."""
    mock_result = Mock()
    mock_result.fetchone = Mock(return_value=None)
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("src.database.get_async_engine", return_value=mock_engine):
        with patch("sqlalchemy.ext.asyncio.AsyncSession") as mock_session_class:
            mock_session_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await commands._get_regime()

            assert "error" in result
            assert result["error"] == "No regime history found"


def test_register():
    """Тест регистрации команд."""
    subparsers = Mock()
    parser = Mock()
    subparsers.add_parser = Mock(return_value=parser)
    parser.add_subparsers = Mock(return_value=Mock())
    parser.set_defaults = Mock()

    commands.register(subparsers)

    subparsers.add_parser.assert_called_once_with(
        "market-selection", help="Market selection operations"
    )


def test_handle_no_action(capsys):
    """Тест обработчика без действия."""
    args = argparse.Namespace(action=None)
    result = commands.handle(args)

    assert result == 1
    captured = capsys.readouterr()
    assert "Usage:" in captured.out


def test_handle_run_success(capsys):
    """Тест обработчика команды run (успех)."""
    import asyncio

    args = argparse.Namespace(action="run", top_n=30, dry_run=False)

    with patch("src.market_selection.cli.commands._run_pipeline") as mock_run:
        mock_run.return_value = {
            "success": True,
            "universe_size": 30,
            "status": "published",
            "regime": "TREND_UP",
            "execution_time": 1.5,
        }

        with patch("asyncio.new_event_loop") as mock_loop:
            with patch("asyncio.set_event_loop"):
                loop = asyncio.new_event_loop()
                loop.run_until_complete = Mock(
                    side_effect=lambda coro: mock_run.return_value
                )
                mock_loop.return_value = loop

                result = commands.handle(args)

                assert result == 0
                captured = capsys.readouterr()
                assert "Pipeline completed successfully" in captured.out
                assert "Universe size: 30" in captured.out
                loop.close()


def test_handle_run_failure(capsys):
    """Тест обработчика команды run (ошибка)."""
    import asyncio

    args = argparse.Namespace(action="run", top_n=30, dry_run=False)

    with patch("src.market_selection.cli.commands._run_pipeline") as mock_run:
        mock_run.return_value = {
            "success": False,
            "error": "Test error",
        }

        with patch("asyncio.new_event_loop") as mock_loop:
            with patch("asyncio.set_event_loop"):
                loop = asyncio.new_event_loop()
                loop.run_until_complete = Mock(
                    side_effect=lambda coro: mock_run.return_value
                )
                mock_loop.return_value = loop

                result = commands.handle(args)

                assert result == 1
                captured = capsys.readouterr()
                assert "Pipeline failed" in captured.out
                loop.close()


def test_handle_status(capsys):
    """Тест обработчика команды status."""
    args = argparse.Namespace(action="status")

    with patch("src.market_selection.cli.commands._get_status") as mock_get:
        mock_get.return_value = {
            "versions": [
                {
                    "ts_version": 1000000,
                    "status": "published",
                    "universe_size": 30,
                    "regime": "TREND_UP",
                    "created_at": "2024-01-01",
                }
            ]
        }

        import asyncio

        with patch("asyncio.new_event_loop") as mock_loop:
            loop = asyncio.new_event_loop()
            loop.run_until_complete = Mock(
                side_effect=lambda coro: mock_get.return_value
            )
            mock_loop.return_value = loop
            with patch("asyncio.set_event_loop"):
                result = commands.handle(args)

                assert result == 0
                captured = capsys.readouterr()
                assert "Recent Universe Versions" in captured.out
                loop.close()


def test_handle_explain(capsys):
    """Тест обработчика команды explain."""
    args = argparse.Namespace(action="explain", symbol="BTC-USDT")

    with patch("src.market_selection.cli.commands._explain_symbol") as mock_explain:
        mock_explain.return_value = {
            "symbol": "BTC-USDT",
            "in_universe": True,
            "tf_scores": [],
        }

        import asyncio

        with patch("asyncio.new_event_loop") as mock_loop:
            with patch("asyncio.set_event_loop"):
                loop = asyncio.new_event_loop()
                loop.run_until_complete = Mock(
                    side_effect=lambda coro: mock_explain.return_value
                )
                mock_loop.return_value = loop

                result = commands.handle(args)

                assert result == 0
                captured = capsys.readouterr()
                assert "Symbol: BTC-USDT" in captured.out
                loop.close()


def test_handle_explain_error(capsys):
    """Тест обработчика команды explain с ошибкой."""
    args = argparse.Namespace(action="explain", symbol="BTC-USDT")

    with patch("src.market_selection.cli.commands._explain_symbol") as mock_explain:
        mock_explain.return_value = {"error": "No published universe found"}

        import asyncio

        with patch("asyncio.new_event_loop") as mock_loop:
            with patch("asyncio.set_event_loop"):
                loop = asyncio.new_event_loop()
                loop.run_until_complete = Mock(
                    side_effect=lambda coro: mock_explain.return_value
                )
                mock_loop.return_value = loop

                result = commands.handle(args)

                assert result == 1
                captured = capsys.readouterr()
                assert "Error:" in captured.out
                loop.close()


def test_handle_migrate(capsys):
    """Тест обработчика команды migrate."""
    args = argparse.Namespace(action="migrate")

    with patch("src.market_selection.cli.commands._run_migrations") as mock_migrate:
        mock_migrate.return_value = {
            "created": ["table1"],
            "after": {"table1": True},
        }

        import asyncio

        with patch("asyncio.new_event_loop") as mock_loop:
            with patch("asyncio.set_event_loop"):
                loop = asyncio.new_event_loop()
                loop.run_until_complete = Mock(
                    side_effect=lambda coro: mock_migrate.return_value
                )
                mock_loop.return_value = loop

                result = commands.handle(args)

                assert result == 0
                captured = capsys.readouterr()
                assert "Migrations completed" in captured.out
                loop.close()


def test_handle_universe_table(capsys):
    """Тест обработчика команды universe (table format)."""
    args = argparse.Namespace(action="universe", limit=10, format="table")

    with patch("src.market_selection.cli.commands._get_universe") as mock_get:
        mock_get.return_value = [
            {"symbol": "BTC-USDT", "score": 0.85, "rank": 1, "best_tf": "1H"}
        ]

        import asyncio

        with patch("asyncio.new_event_loop") as mock_loop:
            loop = asyncio.new_event_loop()
            loop.run_until_complete = Mock(
                side_effect=lambda coro: mock_get.return_value
            )
            mock_loop.return_value = loop
            with patch("asyncio.set_event_loop"):
                result = commands.handle(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "Current Universe" in captured.out


def test_handle_universe_json(capsys):
    """Тест обработчика команды universe (json format)."""
    args = argparse.Namespace(action="universe", limit=10, format="json")

    with patch("src.market_selection.cli.commands._get_universe") as mock_get:
        mock_get.return_value = [
            {"symbol": "BTC-USDT", "score": 0.85, "rank": 1, "best_tf": "1H"}
        ]

        import asyncio

        with patch("asyncio.new_event_loop") as mock_loop:
            loop = asyncio.new_event_loop()
            loop.run_until_complete = Mock(
                side_effect=lambda coro: mock_get.return_value
            )
            mock_loop.return_value = loop
            with patch("asyncio.set_event_loop"):
                result = commands.handle(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "BTC-USDT" in captured.out


def test_handle_universe_csv(capsys):
    """Тест обработчика команды universe (csv format)."""
    args = argparse.Namespace(action="universe", limit=10, format="csv")

    with patch("src.market_selection.cli.commands._get_universe") as mock_get:
        mock_get.return_value = [
            {
                "symbol": "BTC-USDT",
                "score": 0.85,
                "rank": 1,
                "best_tf": "1H",
                "score_4h": 0.8,
                "score_1h": 0.85,
                "score_15m": 0.7,
                "score_5m": 0.6,
            }
        ]

        import asyncio

        with patch("asyncio.new_event_loop") as mock_loop:
            loop = asyncio.new_event_loop()
            loop.run_until_complete = Mock(
                side_effect=lambda coro: mock_get.return_value
            )
            mock_loop.return_value = loop
            with patch("asyncio.set_event_loop"):
                result = commands.handle(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "symbol,score,rank" in captured.out


def test_handle_regime(capsys):
    """Тест обработчика команды regime."""
    args = argparse.Namespace(action="regime")

    with patch("src.market_selection.cli.commands._get_regime") as mock_get:
        mock_get.return_value = {
            "regime": "TREND_UP",
            "strength": 0.8,
            "confidence": 0.9,
            "regime_1d": "TREND_UP",
            "regime_4h": "TREND_UP",
            "regime_1h": "TREND_UP",
            "basket_size": 10,
            "basket_adx_median": 25.0,
            "basket_atr_close_median": 0.02,
        }

        import asyncio

        with patch("asyncio.new_event_loop") as mock_loop:
            loop = asyncio.new_event_loop()
            loop.run_until_complete = Mock(
                side_effect=lambda coro: mock_get.return_value
            )
            mock_loop.return_value = loop
            with patch("asyncio.set_event_loop"):
                result = commands.handle(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "Current Global Regime" in captured.out
            assert "TREND_UP" in captured.out


def test_handle_regime_error(capsys):
    """Тест обработчика команды regime с ошибкой."""
    args = argparse.Namespace(action="regime")

    with patch("src.market_selection.cli.commands._get_regime") as mock_get:
        mock_get.return_value = {"error": "No regime history found"}

        import asyncio

        with patch("asyncio.new_event_loop") as mock_loop:
            loop = asyncio.new_event_loop()
            loop.run_until_complete = Mock(
                side_effect=lambda coro: mock_get.return_value
            )
            mock_loop.return_value = loop
            with patch("asyncio.set_event_loop"):
                result = commands.handle(args)

            assert result == 1
            captured = capsys.readouterr()
            assert "Error:" in captured.out


def test_handle_exception(capsys):
    """Тест обработчика с исключением."""
    args = argparse.Namespace(action="run", top_n=30, dry_run=False)

    import asyncio

    with patch("asyncio.new_event_loop") as mock_loop:
        with patch("asyncio.set_event_loop"):
            loop = asyncio.new_event_loop()
            loop.run_until_complete = Mock(side_effect=Exception("Test error"))
            mock_loop.return_value = loop

            result = commands.handle(args)
            loop.close()

        assert result == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.out
