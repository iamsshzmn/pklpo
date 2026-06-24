from __future__ import annotations

import asyncio
import importlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

from src.candles.application.sync.policy import RetryPolicy
from src.candles.application.sync.use_cases import RunCandleSyncUseCase, _SyncStats
from src.candles.domain.repair import RepairWindow


@dataclass
class _MarketDataStub:
    candles: list[dict[str, Any]]

    async def fetch_candles(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.candles


@dataclass
class _CandleStoreStub:
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def upsert_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
        additional_data: dict[str, Any],
        window: RepairWindow,
    ) -> int:
        self.calls.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "candles": candles,
                "additional_data": additional_data,
                "window": window,
            }
        )
        return len(candles)


class _FailingCandleStore(_CandleStoreStub):
    async def upsert_candles(self, **kwargs: Any) -> int:
        raise RuntimeError("write failed")


@dataclass
class _InstrumentCatalogStub:
    pass


@dataclass
class _TelemetrySpy:
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def increment(self, metric: str, value: int | float = 1, **tags: str) -> None:
        return None

    def observe(self, metric: str, value: int | float, **tags: str) -> None:
        return None

    def event(self, name: str, **payload: Any) -> None:
        self.events.append((name, payload))


def _use_case(
    *,
    market_data: _MarketDataStub,
    candle_store: _CandleStoreStub,
    telemetry: _TelemetrySpy | None = None,
) -> RunCandleSyncUseCase:
    return RunCandleSyncUseCase(
        market_data=market_data,
        candle_store=candle_store,
        instrument_catalog=_InstrumentCatalogStub(),
        retry_policy=RetryPolicy(max_retries=1, retry_delay=0, batch_size=100),
        telemetry=telemetry,
    )


@pytest.mark.asyncio
async def test_sync_bar_passes_chunk_window_when_no_latest_timestamp() -> None:
    store = _CandleStoreStub()
    use_case = _use_case(
        market_data=_MarketDataStub(
            candles=[
                {"ts": 0, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
                {
                    "ts": 60_000,
                    "open": 1,
                    "high": 1,
                    "low": 1,
                    "close": 1,
                    "volume": 1,
                },
            ]
        ),
        candle_store=store,
    )

    await use_case._sync_bar(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        before=None,
        latest_stored_ts=None,
        extra_data_loader=None,
        stats=_SyncStats(),
    )

    assert store.calls[0]["window"] == RepairWindow(0, 120_000)


@pytest.mark.asyncio
async def test_sync_bar_passes_incremental_window_after_latest_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.candles.application.sync.use_cases as use_cases

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(1970, 1, 1, 0, 3, 30, tzinfo=UTC)

    monkeypatch.setattr(use_cases, "datetime", _FixedDateTime)
    store = _CandleStoreStub()
    use_case = _use_case(
        market_data=_MarketDataStub(
            candles=[
                {"ts": 0, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
                {
                    "ts": 60_000,
                    "open": 1,
                    "high": 1,
                    "low": 1,
                    "close": 1,
                    "volume": 1,
                },
                {
                    "ts": 120_000,
                    "open": 1,
                    "high": 1,
                    "low": 1,
                    "close": 1,
                    "volume": 1,
                },
            ]
        ),
        candle_store=store,
    )

    await use_case._sync_bar(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        before=None,
        latest_stored_ts=0,
        extra_data_loader=None,
        stats=_SyncStats(),
    )

    assert [int(candle["ts"]) for candle in store.calls[0]["candles"]] == [
        60_000,
        120_000,
    ]
    assert store.calls[0]["window"] == RepairWindow(60_000, 180_000)


@pytest.mark.asyncio
async def test_sync_bar_incremental_window_end_uses_current_closed_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.candles.application.sync.use_cases as use_cases

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(1970, 1, 1, 0, 3, 30, tzinfo=UTC)

    monkeypatch.setattr(use_cases, "datetime", _FixedDateTime)
    store = _CandleStoreStub()
    use_case = _use_case(
        market_data=_MarketDataStub(
            candles=[
                {
                    "ts": 60_000,
                    "open": 1,
                    "high": 1,
                    "low": 1,
                    "close": 1,
                    "volume": 1,
                },
                {
                    "ts": 3_600_000,
                    "open": 1,
                    "high": 1,
                    "low": 1,
                    "close": 1,
                    "volume": 1,
                },
            ]
        ),
        candle_store=store,
    )

    await use_case._sync_bar(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        before=None,
        latest_stored_ts=0,
        extra_data_loader=None,
        stats=_SyncStats(),
    )

    assert store.calls[0]["window"] == RepairWindow(60_000, 180_000)


@pytest.mark.asyncio
async def test_sync_bar_drops_open_candle_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the only new candle is the currently-open bar, nothing is written."""
    import src.candles.application.sync.use_cases as use_cases

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(1970, 1, 1, 0, 3, 30, tzinfo=UTC)

    monkeypatch.setattr(use_cases, "datetime", _FixedDateTime)
    store = _CandleStoreStub()
    use_case = _use_case(
        market_data=_MarketDataStub(
            candles=[
                {
                    "ts": 180_000,
                    "open": 1,
                    "high": 1,
                    "low": 1,
                    "close": 1,
                    "volume": 1,
                },
            ]
        ),
        candle_store=store,
    )

    count, _ = await use_case._sync_bar(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        before=None,
        latest_stored_ts=120_000,
        extra_data_loader=None,
        stats=_SyncStats(),
    )

    assert count == 0
    assert store.calls == []


@pytest.mark.asyncio
async def test_sync_bar_drops_open_candle_saves_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closed candles are written; the currently-open bar is silently dropped."""
    import src.candles.application.sync.use_cases as use_cases

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(1970, 1, 1, 0, 3, 30, tzinfo=UTC)

    monkeypatch.setattr(use_cases, "datetime", _FixedDateTime)
    store = _CandleStoreStub()
    use_case = _use_case(
        market_data=_MarketDataStub(
            candles=[
                {
                    "ts": 120_000,
                    "open": 1,
                    "high": 1,
                    "low": 1,
                    "close": 1,
                    "volume": 1,
                },
                {
                    "ts": 180_000,
                    "open": 1,
                    "high": 1,
                    "low": 1,
                    "close": 1,
                    "volume": 1,
                },
            ]
        ),
        candle_store=store,
    )

    await use_case._sync_bar(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        before=None,
        latest_stored_ts=60_000,
        extra_data_loader=None,
        stats=_SyncStats(),
    )

    assert [int(c["ts"]) for c in store.calls[0]["candles"]] == [120_000]
    assert store.calls[0]["window"] == RepairWindow(120_000, 180_000)


def test_sync_bar_upsert_failed_emits_error_type_and_exc_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_run_sync_bar_upsert_failed_emits_error_type_and_exc_info(monkeypatch))


async def _run_sync_bar_upsert_failed_emits_error_type_and_exc_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_cases = importlib.import_module("src.candles.application.sync.use_cases")

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(1970, 1, 1, 0, 3, 30, tzinfo=UTC)

    monkeypatch.setattr(use_cases, "datetime", _FixedDateTime)
    telemetry = _TelemetrySpy()
    use_case = _use_case(
        market_data=_MarketDataStub(
            candles=[
                {
                    "ts": 120_000,
                    "open": 1,
                    "high": 1,
                    "low": 1,
                    "close": 1,
                    "volume": 1,
                },
            ]
        ),
        candle_store=_FailingCandleStore(),
        telemetry=telemetry,
    )

    with pytest.raises(RuntimeError, match="write failed"):
        await use_case._sync_bar(
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            before=None,
            latest_stored_ts=60_000,
            extra_data_loader=None,
            stats=_SyncStats(),
        )

    assert telemetry.events == [
        (
            "upsert_failed",
            {
                "symbol": "BTC-USDT-SWAP",
                "timeframe": "1m",
                "error": "write failed",
                "error_type": "unexpected_error",
                "exc_info": True,
            },
        )
    ]
