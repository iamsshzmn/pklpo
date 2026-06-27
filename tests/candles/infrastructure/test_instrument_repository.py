from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from src.candles.infrastructure.instrument_repository import InstrumentSqlRepository


async def test_find_missing_symbols_returns_symbols_not_in_db() -> None:
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("BTC-USDT-SWAP",), ("ETH-USDT-SWAP",)]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "src.candles.infrastructure.instrument_repository.get_db_session",
        return_value=mock_ctx,
    ):
        repo = InstrumentSqlRepository()
        missing = await repo.find_missing_symbols(
            ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]
        )

    assert missing == ["SOL-USDT-SWAP"]


async def test_find_missing_symbols_returns_empty_when_all_present() -> None:
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("BTC-USDT-SWAP",)]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "src.candles.infrastructure.instrument_repository.get_db_session",
        return_value=mock_ctx,
    ):
        repo = InstrumentSqlRepository()
        missing = await repo.find_missing_symbols(["BTC-USDT-SWAP"])

    assert missing == []


async def test_find_missing_symbols_returns_all_when_db_empty() -> None:
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "src.candles.infrastructure.instrument_repository.get_db_session",
        return_value=mock_ctx,
    ):
        repo = InstrumentSqlRepository()
        missing = await repo.find_missing_symbols(["BTC-USDT-SWAP", "ETH-USDT-SWAP"])

    assert missing == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
