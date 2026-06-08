from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.candles.application.bootstrap.dto import BootstrapCommand, BootstrapProgress
from src.candles.application.bootstrap.use_cases import RunBootstrapUseCase
from src.candles.domain.okx_calendar import StorageCalendar
from src.candles.domain.repair import CoverageReconciliation, RepairWindow
from src.candles.domain.repair_timeframes import list_expected_timestamps
from src.candles.domain.timeframes import TF_TO_MS

_1H_MS = TF_TO_MS["1H"]
_CAL = StorageCalendar()


@dataclass
class _FakeTelemetry:
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    action_log: list[str] | None = None

    def increment(self, metric: str, value: int | float = 1, **tags: str) -> None:
        pass

    def observe(self, metric: str, value: int | float, **tags: str) -> None:
        pass

    def event(self, name: str, **payload: Any) -> None:
        self.events.append((name, payload))
        if self.action_log is not None:
            self.action_log.append(f"telemetry:{name}")


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
    invalid_extra_rows: int = 0
    valid_count_calls: list[tuple[int, int]] = field(default_factory=list)

    async def count_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> int:
        return sum(1 for ts in self.inserted if start_ts_ms <= ts < end_ts_ms)

    async def count_valid_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> CoverageReconciliation:
        self.valid_count_calls.append((start_ts_ms, end_ts_ms))
        expected = set(
            list_expected_timestamps(
                start_ts_ms,
                end_ts_ms,
                timeframe,
                calendar=_CAL,
            )
        )
        stored = {ts for ts in self.inserted if start_ts_ms <= ts < end_ts_ms}
        valid_bars = len(stored & expected)
        return CoverageReconciliation(
            expected_bars=len(expected),
            valid_bars=valid_bars,
            missing_bars=len(expected) - valid_bars,
            invalid_extra_rows=self.invalid_extra_rows,
        )


@dataclass
class _FakeRepairStore:
    coverage: _FakeCoverageQuery
    writes: list[list[dict[str, Any]]] = field(default_factory=list)
    windows: list[RepairWindow | None] = field(default_factory=list)
    action_log: list[str] | None = None
    fail: bool = False

    async def selective_upsert_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
        window: RepairWindow | None = None,
    ) -> int:
        if self.action_log is not None:
            self.action_log.append("store_write")
        if self.fail:
            raise RuntimeError("write failed")
        self.writes.append(candles)
        self.windows.append(window)
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
    action_log: list[str] | None = None

    async def upsert_bootstrap_state(self, **kwargs: Any) -> None:
        self.upserts.append(kwargs)
        if self.action_log is not None:
            self.action_log.append(
                f"state:{kwargs['status']}:{kwargs.get('checkpoint_ts')}"
            )
        symbol, timeframe = str(kwargs["symbol"]), str(kwargs["timeframe"])
        checkpoint_ts = kwargs.get("checkpoint_ts")
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


def _make_raw_okx_candle_page(start_ts: int, count: int, tf_ms: int) -> list[dict[str, Any]]:
    return [
        {
            "ts": start_ts + i * tf_ms,
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0,
            "volume": 1.0,
            "volCcy": 10.0,
            "volUsd": 20.0,
        }
        for i in range(count)
    ]


def _make_uc(
    *,
    pages: list[list[dict[str, Any]]],
    listing_time_ms: int | None = None,
    existing: set[int] | None = None,
    invalid_extra_rows: int = 0,
) -> tuple[
    RunBootstrapUseCase,
    _FakeBootstrapState,
    _FakeCoverageQuery,
    _FakeHistoricalSource,
    _FakeRepairStore,
    _FakeTelemetry,
]:
    coverage = _FakeCoverageQuery(
        inserted=existing or set(),
        invalid_extra_rows=invalid_extra_rows,
    )
    source = _FakeHistoricalSource(pages=pages)
    store = _FakeRepairStore(coverage=coverage)
    anchor = _FakeAnchorMetadata(listing_time_ms=listing_time_ms)
    state = _FakeBootstrapState()
    telemetry = _FakeTelemetry()
    uc = RunBootstrapUseCase(
        historical_source=source,
        repair_store=store,
        coverage_query=coverage,
        anchor_metadata=anchor,
        bootstrap_state=state,
        calendar=_CAL,
        telemetry=telemetry,
    )
    return uc, state, coverage, source, store, telemetry


@pytest.mark.asyncio
async def test_happy_path_completes() -> None:
    """Full backward fetch loop with one chunk completes with status=completed."""
    # 3 bars of 1H, target window [0, 3*1H_MS)
    target_end = 3 * _1H_MS
    page = _make_candle_page(0, 3, _1H_MS)
    uc, _state, _coverage, _source, _store, _telemetry = _make_uc(pages=[page])

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
async def test_happy_path_accepts_raw_okx_ts_candles() -> None:
    """Historical source returns raw OKX-shaped candles; bootstrap normalizes for storage."""
    target_end = 3 * _1H_MS
    page = _make_raw_okx_candle_page(0, 3, _1H_MS)
    uc, _state, _coverage, _source, store, _telemetry = _make_uc(pages=[page])

    cmd = BootstrapCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        chunk_bars=500,
    )
    result = await uc.run(cmd, now_ms=target_end)

    assert result.status == "completed"
    assert result.rows_written == 3
    assert store.writes[0][0]["timestamp"] == 0
    assert store.writes[0][0]["vol_ccy"] == 10.0
    assert store.writes[0][0]["vol_usd"] == 20.0
    assert "fetched_at" in store.writes[0][0]


@pytest.mark.asyncio
async def test_bootstrap_passes_chunk_window_to_repair_store() -> None:
    target_end = 3 * _1H_MS
    page = _make_raw_okx_candle_page(0, 3, _1H_MS)
    uc, _state, _coverage, _source, store, _telemetry = _make_uc(pages=[page])

    cmd = BootstrapCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        chunk_bars=500,
    )
    await uc.run(cmd, now_ms=target_end)

    assert store.windows == [RepairWindow(0, target_end)]


@pytest.mark.asyncio
async def test_already_complete_skips_fetch() -> None:
    """Completed state that still matches live DB exits without calling source."""
    target_end = 3 * _1H_MS
    # DB has exactly the 3 bars that were bootstrapped — state is still valid.
    existing_ts = {i * _1H_MS for i in range(3)}
    uc, state, _coverage, source, _store, _telemetry = _make_uc(
        pages=[],
        existing=existing_ts,
    )

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
async def test_completed_state_reconciles_when_db_diverges() -> None:
    """State says completed but swap_ohlcv_p rows are gone → downgrade and re-fetch."""
    target_end = 3 * _1H_MS
    page = _make_candle_page(0, 3, _1H_MS)
    # DB starts empty — simulates rows deleted after a successful bootstrap.
    uc, state, _coverage, source, _store, _telemetry = _make_uc(
        pages=[page],
        existing=set(),
    )

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

    # Re-fetch must have happened.
    assert len(source.calls) > 0
    # After re-fetch the live count is 3 → completed.
    assert result.status == "completed"
    assert result.rows_written == 3
    assert result.missing_bars == 0


@pytest.mark.asyncio
async def test_completed_state_reconciles_partial_divergence() -> None:
    """State says completed but only some rows remain → downgrade to incomplete."""
    target_end = 3 * _1H_MS
    # Only 1 of 3 bars survives in the DB; source returns empty (simulating no more data).
    uc, state, _coverage, source, _store, _telemetry = _make_uc(
        pages=[],  # no more data available from OKX
        existing={0},  # only the first bar is present
    )

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

    # Source was queried (reconciliation triggered a re-fetch attempt).
    assert len(source.calls) > 0
    # Cannot reach 100% — ends as incomplete.
    assert result.status == "incomplete"
    assert result.actual_bars == 1
    assert result.missing_bars == 2


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
    uc, state, _coverage, source, _store, _telemetry = _make_uc(pages=[page])

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
async def test_stale_checkpoint_before_target_start_reinitializes_and_fetches() -> None:
    """A stale non-terminal checkpoint before the new window must not skip the loop."""
    target_start = 24 * _1H_MS
    target_end = target_start + 3 * _1H_MS
    stale_checkpoint = target_start - _1H_MS
    page = _make_candle_page(target_start, 3, _1H_MS)
    uc, state, _coverage, source, _store, _telemetry = _make_uc(pages=[page])

    await state.upsert_bootstrap_state(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        target_start_ts=0,
        target_end_ts=target_start,
        expected_bars=24,
        status="incomplete",
        checkpoint_ts=stale_checkpoint,
    )

    cmd = BootstrapCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        chunk_bars=500,
    )
    result = await uc.run(cmd, now_ms=target_end)

    assert source.calls[0][1] == target_end
    assert result.chunks_fetched == 1
    assert result.rows_written == 3


@pytest.mark.asyncio
async def test_checkpoint_inside_target_window_resumes_when_window_matches() -> None:
    """A checkpoint inside the current window remains resumable when metadata matches."""
    target_end = 10 * _1H_MS
    checkpoint = 5 * _1H_MS
    page = _make_candle_page(0, 5, _1H_MS)
    uc, state, _coverage, source, _store, _telemetry = _make_uc(pages=[page])

    await state.upsert_bootstrap_state(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        target_start_ts=0,
        target_end_ts=target_end,
        expected_bars=10,
        status="incomplete",
        checkpoint_ts=checkpoint,
    )

    cmd = BootstrapCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        chunk_bars=500,
    )
    await uc.run(cmd, now_ms=target_end)

    assert source.calls[0][1] == checkpoint


@pytest.mark.asyncio
async def test_changed_lookback_days_resets_checkpoint() -> None:
    """A non-terminal row for a different requested window must restart at target_end."""
    target_start = 24 * _1H_MS
    target_end = target_start + 3 * _1H_MS
    stale_checkpoint_inside_new_window = target_start + _1H_MS
    page = _make_candle_page(target_start, 3, _1H_MS)
    uc, state, _coverage, source, _store, _telemetry = _make_uc(pages=[page])

    await state.upsert_bootstrap_state(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=2,
        target_start_ts=0,
        target_end_ts=target_end,
        expected_bars=27,
        status="running",
        checkpoint_ts=stale_checkpoint_inside_new_window,
    )

    cmd = BootstrapCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        chunk_bars=500,
    )
    await uc.run(cmd, now_ms=target_end)

    assert source.calls[0][1] == target_end


@pytest.mark.asyncio
async def test_completed_matching_window_reconciles_and_skips_when_live_db_valid() -> None:
    target_end = 3 * _1H_MS
    existing_ts = {i * _1H_MS for i in range(3)}
    uc, state, coverage, source, _store, _telemetry = _make_uc(
        pages=[],
        existing=existing_ts,
    )

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

    assert coverage.valid_count_calls == [(0, target_end)]
    assert len(source.calls) == 0
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_completed_changed_window_reconciles_requested_window_before_skip() -> None:
    old_target_end = 3 * _1H_MS
    new_target_end = 4 * _1H_MS
    existing_ts = {i * _1H_MS for i in range(4)}
    uc, state, coverage, source, _store, _telemetry = _make_uc(
        pages=[],
        existing=existing_ts,
    )

    await state.upsert_bootstrap_state(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        target_start_ts=0,
        target_end_ts=old_target_end,
        expected_bars=3,
        status="completed",
        bootstrap_completed=True,
        actual_bars=3,
    )

    cmd = BootstrapCommand(symbol="BTC-USDT-SWAP", timeframe="1H", lookback_days=1)
    result = await uc.run(cmd, now_ms=new_target_end)

    assert coverage.valid_count_calls == [(0, new_target_end)]
    assert len(source.calls) == 0
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_dry_run_does_not_write() -> None:
    """dry_run=True: candles are fetched but not written to store."""
    target_end = 3 * _1H_MS
    page = _make_candle_page(0, 3, _1H_MS)
    uc, _state, _coverage, _source, store, _telemetry = _make_uc(pages=[page])

    cmd = BootstrapCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        dry_run=True,
    )
    await uc.run(cmd, now_ms=target_end)

    assert store.writes == []


@pytest.mark.asyncio
async def test_invalid_extra_rows_block_completed_status() -> None:
    target_end = 3 * _1H_MS
    page = _make_candle_page(0, 3, _1H_MS)
    uc, state, _coverage, _source, _store, _telemetry = _make_uc(
        pages=[page],
        invalid_extra_rows=1,
    )

    cmd = BootstrapCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        chunk_bars=500,
    )
    result = await uc.run(cmd, now_ms=target_end)

    assert result.status == "incomplete"
    assert result.actual_bars == 3
    assert result.missing_bars == 0
    progress = state.rows[("BTC-USDT-SWAP", "1H")]
    assert progress.bootstrap_completed is False


@pytest.mark.asyncio
async def test_emits_chunk_result_for_non_empty_and_empty_chunks() -> None:
    target_end = 4 * _1H_MS
    page = _make_candle_page(2 * _1H_MS, 2, _1H_MS)
    uc, _state, _coverage, _source, _store, telemetry = _make_uc(
        pages=[page, []],
    )

    cmd = BootstrapCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        chunk_bars=2,
        dry_run=True,
    )
    await uc.run(cmd, now_ms=target_end)

    chunk_events = [
        payload
        for name, payload in telemetry.events
        if name == "bootstrap.chunk_result"
    ]

    assert len(chunk_events) == 2
    assert {
        "symbol": "BTC-USDT-SWAP",
        "timeframe": "1H",
        "chunk_start_ts": 2 * _1H_MS,
        "chunk_end_ts": 4 * _1H_MS,
        "candles_returned": 2,
        "empty": False,
        "oldest_ts": 2 * _1H_MS,
        "newest_ts": 3 * _1H_MS,
    }.items() <= chunk_events[0].items()
    assert {
        "symbol": "BTC-USDT-SWAP",
        "timeframe": "1H",
        "chunk_start_ts": 0,
        "chunk_end_ts": 2 * _1H_MS,
        "candles_returned": 0,
        "empty": True,
        "oldest_ts": None,
        "newest_ts": None,
    }.items() <= chunk_events[1].items()


@pytest.mark.asyncio
async def test_chunk_result_fires_after_store_write_and_state_checkpoint() -> None:
    target_end = 3 * _1H_MS
    page = _make_candle_page(0, 3, _1H_MS)
    coverage = _FakeCoverageQuery()
    action_log: list[str] = []
    source = _FakeHistoricalSource(pages=[page])
    store = _FakeRepairStore(coverage=coverage, action_log=action_log)
    state = _FakeBootstrapState(action_log=action_log)
    telemetry = _FakeTelemetry(action_log=action_log)
    uc = RunBootstrapUseCase(
        historical_source=source,
        repair_store=store,
        coverage_query=coverage,
        anchor_metadata=_FakeAnchorMetadata(),
        bootstrap_state=state,
        calendar=_CAL,
        telemetry=telemetry,
    )

    cmd = BootstrapCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        chunk_bars=500,
    )
    await uc.run(cmd, now_ms=target_end)

    chunk_event_index = action_log.index("telemetry:bootstrap.chunk_result")
    assert action_log.index("store_write") < chunk_event_index
    assert action_log.index("state:running:0") < chunk_event_index

    event = next(
        payload
        for name, payload in telemetry.events
        if name == "bootstrap.chunk_result"
    )
    assert event["status"] == "ok"
    assert event["rows_written"] == 3
    assert event["checkpoint_before_ts"] == target_end
    assert event["checkpoint_after_ts"] == 0
    assert event["chunk_start_ts"] == 0
    assert event["chunk_end_ts"] == target_end
    assert event["invalid_rows"] == 0
    assert "fetch_latency_ms" in event
    assert "db_write_latency_ms" in event
    assert "state_write_latency_ms" in event
    assert "progress_pct" in event


@pytest.mark.asyncio
async def test_chunk_write_failure_emits_failed_event_without_result() -> None:
    target_end = 3 * _1H_MS
    page = _make_candle_page(0, 3, _1H_MS)
    coverage = _FakeCoverageQuery()
    source = _FakeHistoricalSource(pages=[page])
    store = _FakeRepairStore(coverage=coverage, fail=True)
    state = _FakeBootstrapState()
    telemetry = _FakeTelemetry()
    uc = RunBootstrapUseCase(
        historical_source=source,
        repair_store=store,
        coverage_query=coverage,
        anchor_metadata=_FakeAnchorMetadata(),
        bootstrap_state=state,
        calendar=_CAL,
        telemetry=telemetry,
    )

    cmd = BootstrapCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        lookback_days=1,
        chunk_bars=500,
    )
    with pytest.raises(RuntimeError, match="write failed"):
        await uc.run(cmd, now_ms=target_end)

    event_names = [name for name, _payload in telemetry.events]
    assert "bootstrap.chunk_result" not in event_names
    assert event_names == ["bootstrap.chunk_failed"]
    failed = telemetry.events[0][1]
    assert failed["status"] == "error"
    assert failed["error"] == "write failed"
    assert failed["rows_written"] == 0
    assert failed["checkpoint_before_ts"] == target_end
    assert failed["checkpoint_after_ts"] is None
    assert failed["chunk_start_ts"] == 0
    assert failed["chunk_end_ts"] == target_end
