from __future__ import annotations

import pytest

from src.candles.application.metadata.instrument_validation import (
    validate_instrument_exists,
)
from src.candles.domain.exceptions import InstrumentNotFoundError


class _FakeRepo:
    def __init__(self, *, exists: bool) -> None:
        self._exists = exists

    async def instrument_exists(self, symbol: str) -> bool:
        return self._exists


@pytest.mark.asyncio
async def test_validate_instrument_exists_passes_for_known_symbol() -> None:
    await validate_instrument_exists("BTC-USDT-SWAP", repository=_FakeRepo(exists=True))


@pytest.mark.asyncio
async def test_validate_instrument_exists_raises_for_unknown_symbol() -> None:
    with pytest.raises(InstrumentNotFoundError) as exc_info:
        await validate_instrument_exists(
            "FAKE-USDT-SWAP", repository=_FakeRepo(exists=False)
        )
    assert exc_info.value.symbol == "FAKE-USDT-SWAP"
    assert "FAKE-USDT-SWAP" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_instrument_exists_error_message_includes_symbol() -> None:
    with pytest.raises(InstrumentNotFoundError) as exc_info:
        await validate_instrument_exists(
            "ETH-USDT-SWAP", repository=_FakeRepo(exists=False)
        )
    assert "ETH-USDT-SWAP" in str(exc_info.value)
    assert exc_info.value.symbol == "ETH-USDT-SWAP"


def test_instrument_not_found_error_has_symbol_attribute() -> None:
    err = InstrumentNotFoundError("SOL-USDT-SWAP")
    assert err.symbol == "SOL-USDT-SWAP"
    assert "SOL-USDT-SWAP" in str(err)
