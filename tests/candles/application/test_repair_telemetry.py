from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.candles.application.repair.dto import RepairCommand
from src.candles.application.repair.use_cases import RunGapRepairUseCase
from src.candles.domain.repair import (
    RepairExecutionMode,
    RepairGuardrails,
    RepairStrategy,
)


@dataclass
class CoverageQueryStub:
    timestamps: list[int] = field(default_factory=list)

    async def list_timestamps(self, **kwargs: Any) -> list[int]:
        del kwargs
        return self.timestamps

    async def count_missing_timestamps(self, **kwargs: Any) -> int:
        start_ts_ms = int(kwargs["start_ts_ms"])
        end_ts_ms = int(kwargs["end_ts_ms"])
        existing = {ts for ts in self.timestamps if start_ts_ms <= ts < end_ts_ms}
        return sum(
            1 for ts in range(start_ts_ms, end_ts_ms, 60_000) if ts not in existing
        )


@dataclass
class HistoricalSourceStub:
    responses: list[list[dict[str, Any]]] = field(default_factory=list)

    async def fetch_range(self, **kwargs: Any) -> list[dict[str, Any]]:
        del kwargs
        if self.responses:
            return self.responses.pop(0)
        return []


@dataclass
class RepairStoreStub:
    coverage: CoverageQueryStub

    async def selective_upsert_candles(self, **kwargs: Any) -> int:
        for candle in kwargs["candles"]:
            timestamp = int(candle["timestamp"])
            if timestamp not in self.coverage.timestamps:
                self.coverage.timestamps.append(timestamp)
        return len(kwargs["candles"])


@dataclass
class TelemetryStub:
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def increment(self, metric: str, value: int | float = 1, **tags: str) -> None:
        del metric, value, tags

    def observe(self, metric: str, value: int | float, **tags: str) -> None:
        del metric, value, tags

    def event(self, name: str, **payload: Any) -> None:
        self.events.append((name, payload))


def _command() -> RepairCommand:
    return RepairCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=0,
        end_ts_ms=5 * 60_000,
        mode=RepairExecutionMode.APPLY,
        strategy=RepairStrategy.GAP_REPAIR,
        guardrails=RepairGuardrails(
            max_gap_tasks_per_run=100,
            max_requested_bars_per_run=1_000,
            max_range_days=365,
            max_fail_ratio=1.0,
        ),
        now_ts_ms=5 * 60_000,
        padding_bars=0,
    )


@pytest.mark.asyncio
async def test_repair_completed_telemetry_includes_semantic_fields() -> None:
    coverage = CoverageQueryStub(timestamps=[0, 60_000, 4 * 60_000])
    telemetry = TelemetryStub()
    use_case = RunGapRepairUseCase(
        coverage_query=coverage,
        historical_source=HistoricalSourceStub(
            responses=[
                [
                    {"ts": 2 * 60_000, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 10},
                    {"ts": 3 * 60_000, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 11},
                ]
            ]
        ),
        repair_store=RepairStoreStub(coverage=coverage),
        telemetry=telemetry,
    )

    await use_case.run(_command())

    assert telemetry.events[0][0] == "candles.repair.completed"
    payload = telemetry.events[0][1]
    assert payload["requested"] == 2
    assert payload["received"] == 2
    assert payload["written"] == 2
    assert payload["remaining_missing_before"] == 2
    assert payload["remaining_missing_after"] == 0
    assert payload["progress"] == 2
    assert payload["api_fill_ratio"] == 1.0
    assert payload["write_success_ratio"] == 1.0
    assert payload["outcome"] == "success"
