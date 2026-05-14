from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.candles.application.bootstrap.dto import BootstrapCommand, BootstrapProgress
from src.candles.application.bootstrap.use_cases import RunBootstrapUseCase
from src.candles.domain.okx_calendar import StorageCalendar
from src.candles.domain.timeframes import TF_TO_MS

_1H_MS = TF_TO_MS["1H"]
_CAL = StorageCalendar()


@dataclass
class _FakeTelemetry:
    def increment(self, metric: str, value: int | float = 1, **tags: str) -> None:
        pass

    def observe(self, metric: str, value: int | float, **tags: str) -> None:
        pass

    def event(self, name: str, **payload: Any) -> None:
        pass


@dataclass
class _FakeHistoricalSource:
    pages: list[list[dict[str, Any]]]
    calls: list[tuple[int, int]] = field(default_factory=list)

    async def fetch_range(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[dict[str, Any]]:
        self.calls.append((start_ts_ms, end_ts_ms))
        if not self.pages:
            return []
        return self.pages.pop(0)


@dataclass
class _FakeCoverageQuery:
    inserted: set[int] = field(default_factory=set)

    async def count_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> int:
        return sum(1 for ts in self.inserted if start_ts_ms <= ts < end_ts_ms)


@dataclass
class _FakeRepairStore:
    coverage: _FakeCoverageQuery
    writes: list[list[dict[str, Any]]] = field(default_factory=list)

    async def selective_upsert_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
    ) -> int:
        self.writes.append(candles)
        for c in candles:
            self.coverage.inserted.add(int(c["timestamp"]))
        return len(candles)


@dataclass
class _FakeAnchorMetadata:
    listing_time_ms: int | None = None

    async def get_listing_time_ts_ms(self, *, symbol: str) -> int | None:
        return self.listing_time_ms


@dataclass
class _FakeBootstrapState:
    rows: dict[tuple[str, str], BootstrapProgress] = field(default_factory=dict)
    upserts: list[dict[str, Any]] = field(default_factory=list)

    async def upsert_bootstrap_state(self, **kwargs: Any) -> None:
        self.upserts.append(kwargs)
        symbol, timeframe = str(kwargs["symbol"]), str(kwargs["timeframe"])
        existing = self.rows.get((symbol, timeframe))
        checkpoint_ts = kwargs.get("checkpoint_ts")
        if existing is not None and checkpoint_ts is None:
            checkpoint_ts = existing.checkpoint_ts
        self.rows[(symbol, timeframe)] = BootstrapProgress(
            symbol=symbol,
            timeframe=timeframe,
            lookback_days=int(kwargs["lookback_days"]),
            target_start_ts=int(kwargs["target_start_ts"]),
            target_end_ts=int(kwargs["target_end_ts"]),
            checkpoint_ts=checkpoint_ts,
            current_min_ts=kwargs.get("current_min_ts"),
            current_max_ts=kwargs.get("current_max_ts"),
            expected_bars=int(kwargs["expected_bars"]),
            actual_bars=kwargs.get("actual_bars"),
            missing_bars=kwargs.get("missing_bars"),
            coverage_pct=kwargs.get("coverage_pct"),
            status=str(kwargs["status"]),
            bootstrap_completed=bool(kwargs.get("bootstrap_completed", False)),
            error_streak=int(kwargs.get("error_streak", 0)),
            last_error=kwargs.get("last_error"),
        )

    async def get_bootstrap_state(self, *, symbol: str, timeframe: str) -> BootstrapProgress | None:
        return self.rows.get((symbol, timeframe))


def _make_candle_page(start_ts: int, count: int, tf_ms: int) -> list[dict[str, Any]]:
    return [
        {"timestamp": start_ts + i * tf_ms, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}
        for i in range(count)
    ]


def _make_uc(
    *,
    pages: list[list[dict[str, Any]]],
    listing_time_ms: int | None = None,
    existing: set[int] | None = None,
) -> tuple[RunBootstrapUseCase, _FakeBootstrapState, _FakeCoverageQuery, _FakeHistoricalSource, _FakeRepairStore]:
    coverage = _FakeCoverageQuery(inserted=existing or set())
    source = _FakeHistoricalSource(pages=pages)
    store = _FakeRepairStore(coverage=coverage)
    anchor = _FakeAnchorMetadata(listing_time_ms=listing_time_ms)
    state = _FakeBootstrapState()
    uc = RunBootstrapUseCase(
        historical_source=source,
        repair_store=store,
        coverage_query=coverage,
        anchor_metadata=anchor,
        bootstrap_state=state,
        calendar=_CAL,
        telemetry=_FakeTelemetry(),
    )
    return uc, state, coverage, source, store


@pytest.mark.asyncio
async def test_happy_path_completes() -> None:
    """Full backward fetch loop with one chunk completes with status=completed."""
    # 3 bars of 1H, target window [0, 3*1H_MS)
    target_end = 3 * _1H_MS
    page = _make_candle_page(0, 3, _1H_MS)
    uc, state, coverage, source, store = _make_uc(pages=[page])

    cmd = BootstrapCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        chunk_bars=500,
    )
    result = await uc.run(cmd, now_ms=target_end)

    assert result.status == "completed"
    assert result.rows_written == 3
    assert result.chunks_fetched == 1
    assert result.missing_bars == 0
    assert result.coverage_pct == 100.0


@pytest.mark.asyncio
async def test_already_complete_skips_fetch() -> None:
    """If state row already has status=completed, use case exits without calling source."""
    target_end = 3 * _1H_MS
    uc, state, coverage, source, store = _make_uc(pages=[])

    # Pre-populate as completed
    await state.upsert_bootstrap_state(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        target_start_ts=0,
        target_end_ts=target_end,
        expected_bars=3,
        status="completed",
        bootstrap_completed=True,
        actual_bars=3,
    )

    cmd = BootstrapCommand(symbol="BTC-USDT-SWAP", timeframe="1H", lookback_days=1)
    result = await uc.run(cmd, now_ms=target_end)

    assert result.status == "completed"
    assert len(source.calls) == 0


@pytest.mark.asyncio
async def test_circuit_break_on_repeated_errors() -> None:
    """error_streak >= circuit_break_after → status=stuck, exits cleanly."""

    class _ErrorSource:
        calls: int = 0

        async def fetch_range(
            self,
            *,
            symbol: str,
            timeframe: str,
            start_ts_ms: int,
            end_ts_ms: int,
        ) -> list[dict[str, Any]]:
            self.calls += 1
            raise RuntimeError("OKX unavailable")

    coverage = _FakeCoverageQuery()
    store = _FakeRepairStore(coverage=coverage)
    anchor = _FakeAnchorMetadata()
    state_store = _FakeBootstrapState()
    error_source = _ErrorSource()

    uc = RunBootstrapUseCase(
        historical_source=error_source,
        repair_store=store,
        coverage_query=coverage,
        anchor_metadata=anchor,
        bootstrap_state=state_store,
        calendar=_CAL,
        telemetry=_FakeTelemetry(),
    )

    cmd = BootstrapCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        circuit_break_after=3,
    )
    result = await uc.run(cmd, now_ms=5 * _1H_MS)

    assert result.status == "stuck"
    assert error_source.calls == 3


@pytest.mark.asyncio
async def test_resumable_from_checkpoint() -> None:
    """If state row has checkpoint_ts=X, fetch loop starts from X not target_end_ts."""
    target_end = 10 * _1H_MS
    checkpoint = 5 * _1H_MS

    page = _make_candle_page(0, 5, _1H_MS)
    uc, state, coverage, source, store = _make_uc(pages=[page])

    # Pre-populate with existing checkpoint
    await state.upsert_bootstrap_state(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        target_start_ts=0,
        target_end_ts=target_end,
        expected_bars=10,
        status="running",
        checkpoint_ts=checkpoint,
    )

    cmd = BootstrapCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        chunk_bars=500,
    )
    await uc.run(cmd, now_ms=target_end)

    # First fetch call's end_ts must be the checkpoint, not target_end
    assert source.calls[0][1] == checkpoint


@pytest.mark.asyncio
async def test_dry_run_does_not_write() -> None:
    """dry_run=True: candles are fetched but not written to store."""
    target_end = 3 * _1H_MS
    page = _make_candle_page(0, 3, _1H_MS)
    uc, state, coverage, source, store = _make_uc(pages=[page])

    cmd = BootstrapCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        dry_run=True,
    )
    await uc.run(cmd, now_ms=target_end)

    assert store.writes == []
