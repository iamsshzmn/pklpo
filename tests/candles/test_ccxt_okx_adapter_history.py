from __future__ import annotations

from typing import Any

import pytest

from src.candles.ccxt_okx_adapter import _OKXHistoryCandlesClient


@pytest.mark.asyncio
async def test_history_candles_shifts_before_cursor_by_one_bar() -> None:
    calls: list[dict[str, Any]] = []

    async def _request(*, path: str, params: dict[str, Any]) -> dict[str, Any]:
        del path
        calls.append(dict(params))
        return {
            "data": [
                [60_000, "1", "1", "1", "1", "1"],
                [120_000, "2", "2", "2", "2", "2"],
                [180_000, "3", "3", "3", "3", "3"],
            ]
        }

    client = _OKXHistoryCandlesClient(
        request=_request,
        sleep=lambda _: _noop(),
        page_limit=100,
        max_partial_retries=0,
    )

    candles = await client.fetch_range(
        inst_id="BTC-USDT-SWAP",
        bar="1m",
        start_ts_ms=60_000,
        end_ts_ms=180_000,
    )

    assert calls[0]["before"] == "0"
    assert calls[0]["after"] == "180000"
    assert [candle["ts"] for candle in candles] == [60_000, 120_000]


async def _noop() -> None:
    return None
