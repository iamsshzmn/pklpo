from __future__ import annotations

from typing import Any

import pytest

from src.candles.ccxt_okx_adapter import _OKXHistoryCandlesClient


def _history_row(ts: int) -> list[str]:
    return [str(ts), "1.0", "2.0", "0.5", "1.5", "10.0", "11.0", "12.0"]


async def _no_sleep(_seconds: float) -> None:
    return None


@pytest.mark.asyncio
async def test_history_client_paginates_backward_deduplicates_and_sorts() -> None:
    calls: list[dict[str, Any]] = []
    responses = [
        {"data": [_history_row(240_000), _history_row(180_000)]},
        {"data": [_history_row(120_000), _history_row(60_000), _history_row(60_000)]},
        {"data": [_history_row(0)]},
    ]

    async def _request(*, path: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append({"path": path, "params": dict(params)})
        return responses.pop(0)

    client = _OKXHistoryCandlesClient(
        request=_request,
        sleep=_no_sleep,
        page_limit=2,
        max_transport_retries=0,
        max_partial_retries=0,
    )

    candles = await client.fetch_range(
        inst_id="BTC-USDT-SWAP",
        bar="1m",
        start_ts_ms=0,
        end_ts_ms=300_000,
    )

    assert [candle["ts"] for candle in candles] == [
        0,
        60_000,
        120_000,
        180_000,
        240_000,
    ]
    assert calls == [
        {
            "path": "/api/v5/market/history-candles",
            "params": {
                "instId": "BTC-USDT-SWAP",
                "bar": "1m",
                "before": "120000",
                "after": "300000",
                "limit": "2",
            },
        },
        {
            "path": "/api/v5/market/history-candles",
            "params": {
                "instId": "BTC-USDT-SWAP",
                "bar": "1m",
                "before": "0",
                "after": "180000",
                "limit": "2",
            },
        },
        {
            "path": "/api/v5/market/history-candles",
            "params": {
                "instId": "BTC-USDT-SWAP",
                "bar": "1m",
                "before": "0",
                "after": "60000",
                "limit": "2",
            },
        },
    ]


@pytest.mark.asyncio
async def test_history_client_stops_on_empty_page() -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def _request(*, path: str, params: dict[str, Any]) -> dict[str, Any]:
        return {"data": []}

    client = _OKXHistoryCandlesClient(
        request=_request,
        sleep=_no_sleep,
        page_limit=3,
        max_transport_retries=0,
        max_partial_retries=0,
        trace=lambda name, **payload: events.append((name, payload)),
    )

    candles = await client.fetch_range(
        inst_id="BTC-USDT-SWAP",
        bar="1m",
        start_ts_ms=0,
        end_ts_ms=180_000,
    )

    assert candles == []
    assert events == [
        (
            "okx.history_candles.page",
            {
                "endpoint": "history-candles",
                "symbol": "BTC-USDT-SWAP",
                "timeframe": "1m",
                "okx_bar": "1m",
                "requested_start_ts_ms": 0,
                "requested_end_ts_ms": 180_000,
                "received_rows": 0,
                "expected_rows": 3,
                "oldest_ts": None,
                "newest_ts": None,
                "status": "EMPTY",
                "before": "0",
                "after": "180000",
                "limit": 3,
            },
        )
    ]


@pytest.mark.asyncio
async def test_history_client_retries_partial_pages_before_emitting_partial() -> None:
    calls: list[dict[str, Any]] = []
    events: list[tuple[str, dict[str, Any]]] = []

    async def _request(*, path: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append({"path": path, "params": dict(params)})
        return {"data": [_history_row(120_000), _history_row(60_000)]}

    client = _OKXHistoryCandlesClient(
        request=_request,
        sleep=_no_sleep,
        page_limit=3,
        max_transport_retries=0,
        max_partial_retries=2,
        trace=lambda name, **payload: events.append((name, payload)),
    )

    candles = await client.fetch_range(
        inst_id="BTC-USDT-SWAP",
        bar="1m",
        start_ts_ms=0,
        end_ts_ms=180_000,
    )

    assert [candle["ts"] for candle in candles] == [60_000, 120_000]
    assert len(calls) == 4
    assert calls[:3] == [calls[0], calls[0], calls[0]]
    assert events[0] == (
        "okx.history_candles.page",
        {
            "endpoint": "history-candles",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "okx_bar": "1m",
            "requested_start_ts_ms": 0,
            "requested_end_ts_ms": 180_000,
            "received_rows": 2,
            "expected_rows": 3,
            "oldest_ts": 60_000,
            "newest_ts": 120_000,
            "status": "PARTIAL",
            "before": "0",
            "after": "180000",
            "limit": 3,
        },
    )


@pytest.mark.asyncio
async def test_history_client_retries_transport_errors_then_recovers() -> None:
    calls = 0

    async def _request(*, path: str, params: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError("temporary timeout")
        return {"data": [_history_row(60_000), _history_row(0)]}

    client = _OKXHistoryCandlesClient(
        request=_request,
        sleep=_no_sleep,
        page_limit=2,
        max_transport_retries=2,
        max_partial_retries=0,
    )

    candles = await client.fetch_range(
        inst_id="BTC-USDT-SWAP",
        bar="1m",
        start_ts_ms=0,
        end_ts_ms=120_000,
    )

    assert [candle["ts"] for candle in candles] == [0, 60_000]
    assert calls == 3


@pytest.mark.asyncio
async def test_history_client_uses_okx_history_candles_parameter_direction() -> None:
    calls: list[dict[str, Any]] = []

    async def _request(*, path: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append({"path": path, "params": dict(params)})
        return {"data": [_history_row(240_000), _history_row(180_000)]}

    client = _OKXHistoryCandlesClient(
        request=_request,
        sleep=_no_sleep,
        page_limit=2,
        max_transport_retries=0,
        max_partial_retries=0,
    )

    candles = await client.fetch_range(
        inst_id="BTC-USDT-SWAP",
        bar="1m",
        start_ts_ms=180_000,
        end_ts_ms=300_000,
    )

    assert [candle["ts"] for candle in candles] == [180_000, 240_000]
    assert calls == [
        {
            "path": "/api/v5/market/history-candles",
            "params": {
                "instId": "BTC-USDT-SWAP",
                "bar": "1m",
                "before": "120000",
                "after": "300000",
                "limit": "2",
            },
        }
    ]
