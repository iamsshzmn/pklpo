from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from src.candles.interfaces import repair as repair_interface


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, statement: Any, params: dict[str, Any]) -> None:
        self.executed.append((str(statement), params))


@pytest.mark.asyncio
async def test_enqueue_indicator_recalc_persists_queue_item_without_inline_compute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()

    @asynccontextmanager
    async def _fake_get_db_session() -> Any:
        yield session

    monkeypatch.setattr(repair_interface, "get_db_session", _fake_get_db_session)
    monkeypatch.setattr(
        repair_interface,
        "create_feature_application_bootstrap",
        lambda: pytest.fail("enqueue must not build feature application bootstrap"),
        raising=False,
    )
    monkeypatch.setattr(
        repair_interface,
        "RecalcFeaturesInRange",
        lambda **kwargs: pytest.fail("enqueue must not run feature recalculation"),
        raising=False,
    )

    result = await repair_interface.enqueue_indicator_recalc(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        start_ts_ms=1_775_001_600_000,
        end_ts_ms=1_775_005_200_000,
        specs=["rsi", "macd"],
    )

    assert result == {
        "status": "queued",
        "symbol": "BTC-USDT-SWAP",
        "timeframe": "1H",
        "start_ts_ms": 1_775_001_600_000,
        "end_ts_ms": 1_775_005_200_000,
        "rows_written": 0,
        "queue_status": "queued",
        "warmup_bars": 500,
    }
    assert len(session.executed) == 1
    sql, params = session.executed[0]
    assert "INSERT INTO ops.indicator_recalc_queue" in sql
    assert "ON CONFLICT" in sql
    assert params["symbol"] == "BTC-USDT-SWAP"
    assert params["timeframe"] == "1H"
    assert params["range_start_ts"] == 1_775_001_600_000
    assert params["range_end_ts"] == 1_775_005_200_000
    assert params["warmup_bars"] == 500
    assert params["source_dag"] == "repair_interface"
    assert '"specs": ["rsi", "macd"]' in params["detail"]
