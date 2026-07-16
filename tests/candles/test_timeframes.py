from __future__ import annotations

import pytest

from src.candles.domain.timeframes import TF_TO_MS, TF_TO_SEC

SWAP_BARS = ["1m", "5m", "15m", "30m", "1H", "4H", "12H", "1D", "1W", "1M"]


@pytest.mark.parametrize("tf", SWAP_BARS)
def test_timeframe_tables_cover_all_swap_bars(tf: str) -> None:
    assert tf in TF_TO_MS
    assert tf in TF_TO_SEC
    assert TF_TO_MS[tf] == TF_TO_SEC[tf] * 1000


def test_timeframe_tables_have_expected_size() -> None:
    assert len(TF_TO_MS) == 10
    assert len(TF_TO_SEC) == 10
