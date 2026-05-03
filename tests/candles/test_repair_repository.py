from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.candles.infrastructure.repair_repository import RepairCandlesRepository


class _Result:
    def __init__(self, *, rows=None, scalar_value=None, rowcount: int = 1) -> None:
        self._rows = rows or []
        self._scalar_value = scalar_value
        self.rowcount = rowcount

    def fetchall(self):
        return self._rows

    def scalar(self):
        return self._scalar_value


class _FakeSession:
    def __init__(self, results: list[_Result]) -> None:
        self._results = list(results)
        self.execute_calls: list[tuple[object, object]] = []
        self.committed = False
        self.rolled_back = False

    async def execute(self, stmt, params=None):
        self.execute_calls.append((stmt, params))
        return self._results.pop(0)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.mark.asyncio
async def test_list_timestamps_returns_sorted_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession([_Result(rows=[(1000,), (2000,), (3000,)])])
    monkeypatch.setattr(
        "src.candles.infrastructure.repair_repository.get_db_session",
        lambda: _FakeSessionContext(session),
    )

    result = await RepairCandlesRepository().list_timestamps(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=1000,
        end_ts_ms=4000,
    )

    assert result == [1000, 2000, 3000]


@pytest.mark.asyncio
async def test_selective_upsert_updates_only_canonical_candle_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession([_Result(rowcount=2)])
    monkeypatch.setattr(
        "src.candles.infrastructure.repair_repository.get_db_session",
        lambda: _FakeSessionContext(session),
    )

    written = await RepairCandlesRepository().selective_upsert_candles(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        candles=[
            {
                "timestamp": 1000,
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10.0,
                "vol_ccy": None,
                "vol_usd": None,
                "fetched_at": datetime(2026, 4, 11, tzinfo=UTC),
            },
            {
                "timestamp": 2000,
                "open": 2.0,
                "high": 3.0,
                "low": 1.5,
                "close": 2.5,
                "volume": 11.0,
                "vol_ccy": None,
                "vol_usd": None,
                "fetched_at": datetime(2026, 4, 11, tzinfo=UTC),
            },
        ],
    )

    assert written == 2
    assert session.committed is True
    stmt, rows = session.execute_calls[0]
    sql = str(stmt)
    assert "funding_rate" not in sql
    assert "open_interest" not in sql
    assert rows[0]["symbol"] == "BTC-USDT-SWAP"
