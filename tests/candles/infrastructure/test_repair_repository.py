from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

from src.candles.infrastructure import repair_repository as repair_repository_module
from src.candles.infrastructure.repair_repository import RepairCandlesRepository


@dataclass
class FakeResult:
    fetchall_rows: list[tuple[Any, ...]] = field(default_factory=list)
    scalar_value: Any = None
    rowcount: int = 0

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.fetchall_rows

    def scalar(self) -> Any:
        return self.scalar_value

    def one(self) -> tuple[Any, ...]:
        if not self.fetchall_rows:
            raise AssertionError("no rows available")
        return self.fetchall_rows[0]

    def fetchone(self) -> tuple[Any, ...] | None:
        if not self.fetchall_rows:
            return None
        return self.fetchall_rows[0]


@dataclass
class FakeSession:
    execute_results: list[FakeResult] = field(default_factory=list)
    executed: list[tuple[str, Any]] = field(default_factory=list)
    committed: bool = False
    rolled_back: bool = False

    async def execute(self, stmt: Any, params: Any = None) -> FakeResult:
        self.executed.append((str(stmt), params))
        return self.execute_results.pop(0)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class FakeSessionContext:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> FakeSession:
        return self._session

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


def _session_factory(session: FakeSession):
    def _factory() -> FakeSessionContext:
        return FakeSessionContext(session)

    return _factory


@pytest.mark.asyncio
async def test_get_listing_time_ts_ms_returns_listing_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(
        execute_results=[FakeResult(fetchall_rows=[(61_000, 123_000)])]
    )
    repository = RepairCandlesRepository()

    async def passthrough(operation: Any) -> Any:
        return await operation()

    monkeypatch.setattr(
        repair_repository_module, "get_db_session", _session_factory(session)
    )
    monkeypatch.setattr(repository, "_run_with_db_retry", passthrough)

    result = await repository.get_listing_time_ts_ms(symbol="BTC-USDT-SWAP")

    assert result == 61_000
    assert session.executed[0][1] == {"symbol": "BTC-USDT-SWAP"}


@pytest.mark.asyncio
async def test_get_listing_time_ts_ms_returns_none_for_missing_or_null_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(execute_results=[FakeResult(scalar_value=None)])
    repository = RepairCandlesRepository()

    async def passthrough(operation: Any) -> Any:
        return await operation()

    monkeypatch.setattr(
        repair_repository_module, "get_db_session", _session_factory(session)
    )
    monkeypatch.setattr(repository, "_run_with_db_retry", passthrough)

    result = await repository.get_listing_time_ts_ms(symbol="BTC-USDT-SWAP")

    assert result is None


@pytest.mark.asyncio
async def test_get_listing_anchor_metadata_returns_listing_time_and_freshness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(
        execute_results=[FakeResult(fetchall_rows=[(61_000, 123_000)])]
    )
    repository = RepairCandlesRepository()

    async def passthrough(operation: Any) -> Any:
        return await operation()

    monkeypatch.setattr(
        repair_repository_module, "get_db_session", _session_factory(session)
    )
    monkeypatch.setattr(repository, "_run_with_db_retry", passthrough)

    metadata = await repository.get_listing_anchor_metadata(symbol="BTC-USDT-SWAP")

    assert metadata is not None
    assert metadata.list_time_ts_ms == 61_000
    assert metadata.metadata_refreshed_at_ms == 123_000
    assert session.executed[0][1] == {"symbol": "BTC-USDT-SWAP"}


@pytest.mark.asyncio
async def test_list_timestamps_maps_rows_to_ints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(
        execute_results=[FakeResult(fetchall_rows=[(60_000,), (120_000,)])]
    )
    repository = RepairCandlesRepository()

    async def passthrough(operation: Any) -> Any:
        return await operation()

    monkeypatch.setattr(
        repair_repository_module, "get_db_session", _session_factory(session)
    )
    monkeypatch.setattr(repository, "_run_with_db_retry", passthrough)

    result = await repository.list_timestamps(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=0,
        end_ts_ms=180_000,
    )

    assert result == [60_000, 120_000]
    assert session.executed[0][1] == {
        "symbol": "BTC-USDT-SWAP",
        "timeframe": "1m",
        "start_ts_ms": 0,
        "end_ts_ms": 180_000,
    }


@pytest.mark.asyncio
async def test_count_candles_returns_scalar_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(execute_results=[FakeResult(scalar_value=7)])
    repository = RepairCandlesRepository()

    async def passthrough(operation: Any) -> Any:
        return await operation()

    monkeypatch.setattr(
        repair_repository_module, "get_db_session", _session_factory(session)
    )
    monkeypatch.setattr(repository, "_run_with_db_retry", passthrough)

    result = await repository.count_candles(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=0,
        end_ts_ms=180_000,
    )

    assert result == 7


@pytest.mark.asyncio
async def test_selective_upsert_returns_zero_for_empty_input() -> None:
    repository = RepairCandlesRepository()

    result = await repository.selective_upsert_candles(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        candles=[],
    )

    assert result == 0


@pytest.mark.asyncio
async def test_selective_upsert_updates_only_canonical_candle_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(
        execute_results=[FakeResult(), FakeResult(), FakeResult(rowcount=2)]
    )
    repository = RepairCandlesRepository()

    async def passthrough(operation: Any) -> Any:
        return await operation()

    monkeypatch.setattr(
        repair_repository_module, "get_db_session", _session_factory(session)
    )
    monkeypatch.setattr(repository, "_run_with_db_retry", passthrough)

    result = await repository.selective_upsert_candles(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        candles=[
            {
                "timestamp": 0,
                "open": 1,
                "high": 2,
                "low": 1,
                "close": 1,
                "volume": 10,
                "vol_ccy": 11,
                "vol_usd": 12,
                "fetched_at": datetime(2026, 4, 11, tzinfo=UTC),
            },
            {
                "timestamp": 60_000,
                "open": 2,
                "high": 3,
                "low": 1,
                "close": 2,
                "volume": 20,
                "vol_ccy": 21,
                "vol_usd": 22,
                "fetched_at": datetime(2026, 4, 11, 0, 1, tzinfo=UTC),
            },
        ],
    )

    assert result == 2
    assert session.committed is True
    assert session.rolled_back is False
    statement, rows = session.executed[-1]
    assert "funding_rate" not in statement
    assert "open_interest" not in statement
    assert rows == [
        {
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "timestamp": 0,
            "open": 1,
            "high": 2,
            "low": 1,
            "close": 1,
            "volume": 10,
            "vol_ccy": 11,
            "vol_usd": 12,
            "fetched_at": datetime(2026, 4, 11, tzinfo=UTC),
        },
        {
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "timestamp": 60_000,
            "open": 2,
            "high": 3,
            "low": 1,
            "close": 2,
            "volume": 20,
            "vol_ccy": 21,
            "vol_usd": 22,
            "fetched_at": datetime(2026, 4, 11, 0, 1, tzinfo=UTC),
        },
    ]
