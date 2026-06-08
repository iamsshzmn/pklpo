import pytest

from src.candles.ccxt_okx_adapter import _to_ccxt_symbol


def test_to_ccxt_symbol_valid_swap() -> None:
    assert _to_ccxt_symbol("BTC-USDT-SWAP") == "BTC/USDT:USDT"


@pytest.mark.parametrize(
    "inst_id",
    [
        "",
        "BTC-USDT",
        "BTC-USDT-SPOT",
        "BTC--SWAP",
        "BTC-USDT-SWAP-EXTRA",
    ],
)
def test_to_ccxt_symbol_invalid_format(inst_id: str) -> None:
    with pytest.raises(ValueError, match="Expected BASE-QUOTE-SWAP"):
        _to_ccxt_symbol(inst_id)
