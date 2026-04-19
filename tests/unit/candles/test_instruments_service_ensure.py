from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def test_ensure_symbols_registered_no_missing_is_noop() -> None:
    """If all symbols are already in DB, no OKX call is made."""
    mock_repo = AsyncMock()
    mock_repo.find_missing_symbols = AsyncMock(return_value=[])

    with patch("src.candles.instruments_service.build_market_data_adapter") as mock_adapter:
        from src.candles.instruments_service import ensure_symbols_registered
        await ensure_symbols_registered(
            ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
            repository=mock_repo,
            logger=logging.getLogger("test"),
        )

    mock_adapter.assert_not_called()


async def test_ensure_symbols_registered_fetches_and_saves_missing() -> None:
    """Missing symbols are fetched from OKX and saved to DB."""
    mock_repo = AsyncMock()
    mock_repo.find_missing_symbols = AsyncMock(return_value=["SOL-USDT-SWAP"])

    okx_instruments = [
        {"instId": "BTC-USDT-SWAP", "instType": "SWAP", "state": "live"},
        {"instId": "SOL-USDT-SWAP", "instType": "SWAP", "state": "live"},
    ]
    mock_client = AsyncMock()
    mock_client.get_instruments = AsyncMock(return_value=okx_instruments)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("src.candles.instruments_service.build_market_data_adapter", return_value=mock_ctx), \
         patch("src.candles.instruments_service.save_instruments_to_db", new_callable=AsyncMock) as mock_save:
        mock_save.return_value = (1, 0)
        from src.candles.instruments_service import ensure_symbols_registered
        await ensure_symbols_registered(
            ["BTC-USDT-SWAP", "SOL-USDT-SWAP"],
            repository=mock_repo,
            logger=logging.getLogger("test"),
        )

    saved_instruments = mock_save.call_args[0][0]
    assert any(i["instId"] == "SOL-USDT-SWAP" for i in saved_instruments)


async def test_ensure_symbols_registered_raises_if_symbol_not_on_okx() -> None:
    """If a missing symbol is not returned by OKX, raise ValueError."""
    mock_repo = AsyncMock()
    mock_repo.find_missing_symbols = AsyncMock(return_value=["FAKE-USDT-SWAP"])

    mock_client = AsyncMock()
    mock_client.get_instruments = AsyncMock(return_value=[
        {"instId": "BTC-USDT-SWAP", "instType": "SWAP", "state": "live"},
    ])
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("src.candles.instruments_service.build_market_data_adapter", return_value=mock_ctx):
        from src.candles.instruments_service import ensure_symbols_registered
        with pytest.raises(ValueError, match="FAKE-USDT-SWAP"):
            await ensure_symbols_registered(
                ["BTC-USDT-SWAP", "FAKE-USDT-SWAP"],
                repository=mock_repo,
                logger=logging.getLogger("test"),
            )
