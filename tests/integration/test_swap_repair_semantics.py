"""Integration tests for the redesigned OKX swap repair outcome semantics.

These tests exercise ``RunGapRepairUseCase`` end-to-end with a fake historical
source ("API"), an in-memory coverage/store, and a real ``NoProgressPolicy``.
They cover the four outcome scenarios the redesign plan requires:

* full window → outcome ``success``
* partial window → outcome ``partial`` (no exception)
* empty window (no new bars) → outcome ``empty`` (no exception)
* N consecutive empty iterations on a critical TF → ``ValueError``

Outcome is asserted via the telemetry event payload emitted by the use case
(``candles.repair.completed``), which is the current contract (see
``src/candles/application/repair/use_cases.py`` around the ``outcome=`` tag).

See ``history/planning/okx_swap_repair_semantics_redesign_plan_2026-04-21.md``
(task REPAIR-902) for the full requirement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.candles.application.repair.dto import RepairCommand
from src.candles.application.repair.use_cases import RunGapRepairUseCase
from src.candles.domain.repair import (
    NoProgressPolicy,
    RepairExecutionMode,
    RepairGuardrails,
    RepairStrategy,
)


@dataclass
class InMemoryCoverage:
    timestamps: list[int] = field(default_factory=list)
    count_result: int = 0

    async def list_timestamps(self, **_kwargs: Any) -> list[int]:
        return list(self.timestamps)

    async def count_candles(self, **_kwargs: Any) -> int:
        return self.count_result

    async def count_missing_timestamps(self, **kwargs: Any) -> int:
        start_ts_ms = int(kwargs["start_ts_ms"])
        end_ts_ms = int(kwargs["end_ts_ms"])
        existing = {ts for ts in self.timestamps if start_ts_ms <= ts < end_ts_ms}
        return sum(
            1 for ts in range(start_ts_ms, end_ts_ms, 60_000) if ts not in existing
        )


@dataclass
class FakeHistoricalApi:
    """Fake OKX-like API. Each ``fetch_range`` call pops the next response."""

    responses: list[list[dict[str, Any]]] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def fetch_range(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(kwargs)
        if self.responses:
            return self.responses.pop(0)
        return []


@dataclass
class InMemoryStore:
    coverage: InMemoryCoverage
    writes: list[list[dict[str, Any]]] = field(default_factory=list)

    async def selective_upsert_candles(self, **kwargs: Any) -> int:
        candles = list(kwargs["candles"])
        self.writes.append(candles)
        written = 0
        for candle in candles:
            ts = int(candle["timestamp"])
            if ts not in self.coverage.timestamps:
                self.coverage.timestamps.append(ts)
                written += 1
        return written


@dataclass
class RecordingTelemetry:
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def increment(self, metric: str, value: int | float = 1, **tags: str) -> None:
        return None

    def observe(self, metric: str, value: int | float, **tags: str) -> None:
        return None

    def event(self, name: str, **payload: Any) -> None:
        self.events.append((name, payload))

    def completion_payload(self) -> dict[str, Any]:
        for name, payload in self.events:
            if name == "candles.repair.completed":
                return payload
        raise AssertionError(
            f"candles.repair.completed event not emitted; got {[n for n, _ in self.events]}"
        )


def _guardrails() -> RepairGuardrails:
    return RepairGuardrails(
        max_gap_tasks_per_run=100,
        max_requested_bars_per_run=1_000,
        max_range_days=365,
        max_fail_ratio=1.0,
    )


def _command(
    *,
    start_ts_ms: int = 0,
    end_ts_ms: int = 5 * 60_000,
    timeframe: str = "1m",
) -> RepairCommand:
    return RepairCommand(
        symbol="BTC-USDT-SWAP",
        timeframe=timeframe,
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        mode=RepairExecutionMode.APPLY,
        strategy=RepairStrategy.GAP_REPAIR,
        guardrails=_guardrails(),
        now_ts_ms=end_ts_ms,
        padding_bars=0,
    )


def _bar(ts_ms: int) -> dict[str, Any]:
    return {
        "ts": ts_ms,
        "open": 1,
        "high": 2,
        "low": 0,
        "close": 1,
        "volume": 10,
    }


def _make_use_case(
    *,
    coverage: InMemoryCoverage,
    api: FakeHistoricalApi,
    store: InMemoryStore,
    telemetry: RecordingTelemetry | None = None,
    policy: NoProgressPolicy | None = None,
) -> RunGapRepairUseCase:
    return RunGapRepairUseCase(
        coverage_query=coverage,
        historical_source=api,
        repair_store=store,
        telemetry=telemetry,
        no_progress_policy=policy,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_window_yields_success_outcome() -> None:
    """API returns every missing bar → outcome is ``success``."""
    coverage = InMemoryCoverage(timestamps=[])
    api = FakeHistoricalApi(
        responses=[[_bar(i * 60_000) for i in range(5)]],
    )
    store = InMemoryStore(coverage=coverage)
    telemetry = RecordingTelemetry()
    use_case = _make_use_case(
        coverage=coverage, api=api, store=store, telemetry=telemetry
    )

    before_missing = await coverage.count_missing_timestamps(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=0,
        end_ts_ms=5 * 60_000,
    )
    result = await use_case.run(_command())
    after_missing = await coverage.count_missing_timestamps(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=0,
        end_ts_ms=5 * 60_000,
    )

    payload = telemetry.completion_payload()
    assert payload["outcome"] == "success"
    assert payload["received"] == 5
    assert payload["written"] == 5
    assert payload["progress"] == 5
    assert payload["api_fill_ratio"] == pytest.approx(1.0)
    assert payload["write_success_ratio"] == pytest.approx(1.0)
    assert before_missing == 5
    assert after_missing == 0
    assert result.rows_written == 5


@pytest.mark.integration
@pytest.mark.asyncio
async def test_half_window_yields_partial_outcome_without_exception() -> None:
    """API returns only half the window → outcome is ``partial``, no raise."""
    coverage = InMemoryCoverage(timestamps=[])
    api = FakeHistoricalApi(
        responses=[[_bar(i * 60_000) for i in range(2)]],
    )
    store = InMemoryStore(coverage=coverage)
    telemetry = RecordingTelemetry()
    use_case = _make_use_case(
        coverage=coverage, api=api, store=store, telemetry=telemetry
    )

    result = await use_case.run(_command())

    payload = telemetry.completion_payload()
    assert payload["outcome"] == "partial"
    assert payload["received"] == 2
    assert payload["requested"] == 5
    assert 0.0 < payload["api_fill_ratio"] < 1.0
    assert result.rows_written == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_empty_response_yields_empty_outcome_without_exception() -> None:
    """API returns an empty list → outcome is ``empty``, no raise."""
    coverage = InMemoryCoverage(timestamps=[])
    api = FakeHistoricalApi(responses=[[]])
    store = InMemoryStore(coverage=coverage)
    telemetry = RecordingTelemetry()
    use_case = _make_use_case(
        coverage=coverage, api=api, store=store, telemetry=telemetry
    )

    result = await use_case.run(_command())

    payload = telemetry.completion_payload()
    assert payload["outcome"] == "empty"
    assert payload["received"] == 0
    assert payload["progress"] == 0
    assert result.rows_written == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_three_consecutive_empty_on_1m_escalates_to_exception() -> None:
    """Critical TF ``1m`` → tracker raises after N consecutive empty iterations."""
    coverage = InMemoryCoverage(timestamps=[])
    api = FakeHistoricalApi(responses=[[], [], []])
    store = InMemoryStore(coverage=coverage)
    telemetry = RecordingTelemetry()
    policy = NoProgressPolicy(
        critical_timeframes=frozenset({"1m"}),
        no_progress_threshold=3,
    )
    use_case = _make_use_case(
        coverage=coverage,
        api=api,
        store=store,
        telemetry=telemetry,
        policy=policy,
    )

    command = _command(timeframe="1m")

    await use_case.run(command)
    await use_case.run(command)
    with pytest.raises(ValueError, match="no progress on critical TF 1m"):
        await use_case.run(command)
