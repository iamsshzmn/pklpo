from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pytest

from src.candles.domain.repair import RepairExecutionMode, RepairStrategy
from src.candles.domain.repair_timeframes import expected_next_open
from src.candles.interfaces import repair as repair_interface


@dataclass
class FakeRepository:
    list_timestamps_calls: int = 0
    count_candles_calls: int = 0
    timestamps: list[int] = field(default_factory=list)

    async def list_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[int]:
        del symbol, timeframe, start_ts_ms, end_ts_ms
        self.list_timestamps_calls += 1
        return list(self.timestamps)

    async def count_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> int:
        del symbol, timeframe, start_ts_ms, end_ts_ms
        self.count_candles_calls += 1
        return len(self.timestamps)


class FakeUseCase:
    init_calls: list[dict[str, Any]] = []
    run_calls: list[Any] = []

    def __init__(self, **kwargs: Any) -> None:
        type(self).init_calls.append(kwargs)

    async def run(self, command: Any) -> Any:
        type(self).run_calls.append(command)
        return type(
            "FakeResult",
            (),
            {
                "mode": command.mode,
                "strategy": command.strategy,
                "plan": type(
                    "FakePlan",
                    (),
                    {
                        "symbol": command.symbol,
                        "timeframe": command.timeframe,
                        "window": type(
                            "FakeWindow",
                            (),
                            {
                                "start_ts_ms": command.start_ts_ms,
                                "end_ts_ms": command.end_ts_ms,
                            },
                        )(),
                        "gap_tasks": 2,
                        "requested_bars": 5,
                        "range_days": 0.0,
                    },
                )(),
                "rows_written": 4,
                "fetch_calls": 1,
                "verified": True,
                "remaining_gap_tasks": 2,
                "remaining_requested_bars": 5,
                "verification_method": type(
                    "FakeVerificationMethod",
                    (),
                    {"value": "plan-only"},
                )(),
                "watermark_updated": False,
            },
        )()


class FakeMarketDataContext:
    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter

    async def __aenter__(self) -> Any:
        return self.adapter

    async def __aexit__(self, *exc: Any) -> None:
        return None


class FakeMarketPort:
    async def fetch_candles(self, **kwargs: Any) -> list[dict[str, Any]]:
        return []


class FakeTelemetry:
    pass


@pytest.mark.asyncio
async def test_run_swap_repair_wires_gap_repair_use_case_without_market_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeUseCase.init_calls = []
    FakeUseCase.run_calls = []

    monkeypatch.setattr(repair_interface, "RepairCandlesRepository", FakeRepository)
    monkeypatch.setattr(
        repair_interface,
        "build_market_data_adapter",
        lambda config: pytest.fail("detect-only should not build market adapter"),
    )
    monkeypatch.setattr(
        repair_interface,
        "datetime",
        type(
            "_DateTimeModule",
            (),
            {
                "now": staticmethod(
                    lambda tz=None: datetime(2026, 4, 11, 12, 34, tzinfo=tz)
                ),
                "fromisoformat": staticmethod(datetime.fromisoformat),
            },
        )(),
    )
    monkeypatch.setattr(repair_interface, "_TracingTelemetryAdapter", FakeTelemetry)
    monkeypatch.setattr(repair_interface, "RunGapRepairUseCase", FakeUseCase)

    summary = await repair_interface.run_swap_repair(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=1,
        end_ts_ms=2,
        mode=RepairExecutionMode.DETECT_ONLY,
        strategy=RepairStrategy.GAP_REPAIR,
        max_gap_tasks_per_run=10,
        max_requested_bars_per_run=100,
        max_range_days=7,
        max_fail_ratio=0.2,
        padding_bars=3,
    )

    assert FakeUseCase.init_calls
    assert FakeUseCase.run_calls[0].strategy is RepairStrategy.GAP_REPAIR
    assert FakeUseCase.run_calls[0].now_ts_ms == 1_775_910_840_000
    assert summary == {
        "mode": "detect-only",
        "strategy": "gap-repair",
        "symbol": "BTC-USDT-SWAP",
        "timeframe": "1m",
        "window": {"start_ts_ms": 1, "end_ts_ms": 2},
        "gap_tasks": 2,
        "requested_bars": 5,
        "remaining_gap_tasks": 2,
        "remaining_requested_bars": 5,
        "verification_method": "plan-only",
        "rows_written": 4,
        "fetch_calls": 1,
        "verified": True,
        "padding_bars": 3,
        "guardrail_violations": [],
        "watermark_updated": False,
        "auto_apply_incomplete": True,
        "received_bars": 0,
        "remaining_missing_before": 0,
        "remaining_missing_after": 0,
        "progress": 0,
        "api_fill_ratio": 0.0,
        "write_success_ratio": 0.0,
        "outcome": "success",
        "blocked": False,
        "blocked_reason": None,
        "blocked_cause": None,
    }


@pytest.mark.asyncio
async def test_run_swap_repair_selects_backfill_use_case_without_market_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeUseCase.init_calls = []
    FakeUseCase.run_calls = []

    monkeypatch.setattr(repair_interface, "RepairCandlesRepository", FakeRepository)
    monkeypatch.setattr(
        repair_interface,
        "build_market_data_adapter",
        lambda config: pytest.fail("dry-run should not build market adapter"),
    )
    monkeypatch.setattr(repair_interface, "_TracingTelemetryAdapter", FakeTelemetry)
    monkeypatch.setattr(repair_interface, "RunHistoricalBackfillUseCase", FakeUseCase)

    await repair_interface.run_swap_repair(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=10,
        end_ts_ms=20,
        mode=RepairExecutionMode.DRY_RUN,
        strategy=RepairStrategy.BACKFILL,
        max_gap_tasks_per_run=10,
        max_requested_bars_per_run=100,
        max_range_days=7,
        max_fail_ratio=0.2,
        padding_bars=0,
        config={"provider": "test"},
    )

    assert FakeUseCase.init_calls
    assert FakeUseCase.run_calls[0].strategy is RepairStrategy.BACKFILL


@pytest.mark.asyncio
async def test_run_swap_repair_apply_uses_market_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeUseCase.init_calls = []
    FakeUseCase.run_calls = []
    build_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(repair_interface, "RepairCandlesRepository", FakeRepository)

    def _build_market_data_adapter(config: dict[str, Any]) -> dict[str, Any]:
        build_calls.append(config)
        return {"config": config}

    monkeypatch.setattr(
        repair_interface, "build_market_data_adapter", _build_market_data_adapter
    )
    monkeypatch.setattr(
        repair_interface,
        "_MarketDataPortAdapter",
        lambda adapter: FakeMarketDataContext(FakeMarketPort()),
    )
    monkeypatch.setattr(repair_interface, "_TracingTelemetryAdapter", FakeTelemetry)
    monkeypatch.setattr(repair_interface, "RunGapRepairUseCase", FakeUseCase)

    summary = await repair_interface.run_swap_repair(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=100,
        end_ts_ms=200,
        mode=RepairExecutionMode.APPLY,
        strategy=RepairStrategy.GAP_REPAIR,
        max_gap_tasks_per_run=10,
        max_requested_bars_per_run=100,
        max_range_days=7,
        max_fail_ratio=0.2,
        padding_bars=0,
        config={"provider": "test"},
    )

    assert build_calls == [{"provider": "test"}]
    assert summary["verification_method"] == "plan-only"
    assert "remaining_gap_tasks" in summary
    assert "remaining_requested_bars" in summary


@pytest.mark.asyncio
async def test_run_swap_repair_auto_apply_delegates_with_explicit_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _fake_run_swap_repair_timeframe(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "mode": "apply",
            "strategy": "gap-repair",
            "symbol": kwargs["symbol"],
            "timeframe": kwargs["timeframe"],
            "window": {"start_ts_ms": 10, "end_ts_ms": 100},
            "gap_tasks": 2,
            "requested_bars": 20,
            "remaining_gap_tasks": 0,
            "remaining_requested_bars": 0,
            "verification_method": "gap-detection",
            "rows_written": 20,
            "fetch_calls": 2,
            "verified": True,
            "padding_bars": kwargs["padding_bars"],
            "guardrail_violations": [],
            "watermark_updated": False,
        }

    monkeypatch.setattr(
        repair_interface, "run_swap_repair_timeframe", _fake_run_swap_repair_timeframe
    )

    summary = await repair_interface.run_swap_repair_auto_apply(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        strategy=RepairStrategy.GAP_REPAIR,
        max_gap_tasks_per_run=10,
        max_requested_bars_per_run=100,
        max_range_days=7,
        max_fail_ratio=0.2,
        padding_bars=0,
        anchor_ts_ms=1_775_001_600_000,
        auto_apply_anchor_strategy="explicit",
    )

    assert len(calls) == 1
    assert calls[0]["timeframe"] == "1m"
    assert calls[0]["max_range_days"] == 7
    assert calls[0]["anchor_ts_ms"] == 1_775_001_600_000
    assert calls[0]["auto_apply_anchor_strategy"] == "explicit"
    assert calls[0]["auto_apply_window"] is True
    assert summary["window"] == {"start_ts_ms": 10, "end_ts_ms": 100}
    assert summary["rows_written"] == 20
    assert summary["remaining_gap_tasks"] == 0


@pytest.mark.asyncio
async def test_run_swap_repair_auto_apply_passes_listing_date_strategy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _fake_run_swap_repair_timeframe(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "mode": "apply",
            "strategy": "gap-repair",
            "symbol": kwargs["symbol"],
            "timeframe": kwargs["timeframe"],
            "window": {"start_ts_ms": 10, "end_ts_ms": 100},
            "gap_tasks": 0,
            "requested_bars": 0,
            "remaining_gap_tasks": 0,
            "remaining_requested_bars": 0,
            "verification_method": "gap-detection",
            "rows_written": 0,
            "fetch_calls": 0,
            "verified": True,
            "padding_bars": kwargs["padding_bars"],
            "guardrail_violations": [],
            "watermark_updated": False,
        }

    monkeypatch.setattr(
        repair_interface, "run_swap_repair_timeframe", _fake_run_swap_repair_timeframe
    )

    await repair_interface.run_swap_repair_auto_apply(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        strategy=RepairStrategy.GAP_REPAIR,
        max_gap_tasks_per_run=10,
        max_requested_bars_per_run=100,
        max_range_days=7,
        max_fail_ratio=0.2,
        padding_bars=0,
        auto_apply_anchor_strategy="listing-date",
    )

    assert calls[0]["auto_apply_anchor_strategy"] == "listing-date"
    assert calls[0]["anchor_ts_ms"] is None


@pytest.mark.asyncio
async def test_run_swap_repair_auto_apply_allows_calendar_bar_wider_than_planner_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _MonthlyRepository:
        def __init__(self) -> None:
            self.timestamps = {
                int(datetime(2026, 1, 1).timestamp() * 1000),
                int(datetime(2026, 2, 1).timestamp() * 1000),
                int(datetime(2026, 3, 1).timestamp() * 1000),
            }

        async def get_coverage_bounds(
            self,
            *,
            symbol: str,
            timeframe: str,
            end_ts_ms: int,
        ) -> tuple[int | None, int | None]:
            del symbol, timeframe, end_ts_ms
            return min(self.timestamps), max(self.timestamps)

        async def list_timestamps(
            self,
            *,
            symbol: str,
            timeframe: str,
            start_ts_ms: int,
            end_ts_ms: int,
        ) -> list[int]:
            del symbol, timeframe
            return sorted(
                ts for ts in self.timestamps if start_ts_ms <= ts < end_ts_ms
            )

        async def count_missing_timestamps(
            self,
            *,
            symbol: str,
            timeframe: str,
            start_ts_ms: int,
            end_ts_ms: int,
        ) -> int:
            del symbol
            expected: list[int] = []
            cursor = start_ts_ms
            while cursor < end_ts_ms:
                expected.append(cursor)
                cursor = expected_next_open(cursor, timeframe)
            existing = {
                ts for ts in self.timestamps if start_ts_ms <= ts < end_ts_ms
            }
            return sum(1 for ts in expected if ts not in existing)

        async def selective_upsert_candles(
            self,
            *,
            symbol: str,
            timeframe: str,
            candles: list[dict[str, Any]],
        ) -> int:
            del symbol, timeframe
            written = 0
            for candle in candles:
                ts = int(candle["timestamp"])
                if ts not in self.timestamps:
                    self.timestamps.add(ts)
                    written += 1
            return written

    class _FakeMarketPort:
        async def fetch_history_candles(
            self,
            *,
            instrument_id: str,
            timeframe: str,
            start_ts_ms: int,
            end_ts_ms: int,
        ) -> list[dict[str, Any]]:
            del instrument_id, timeframe, end_ts_ms
            return [
                {
                    "ts": start_ts_ms,
                    "open": 1,
                    "high": 2,
                    "low": 0,
                    "close": 1,
                    "volume": 10,
                }
            ]

    repository = _MonthlyRepository()
    monkeypatch.setattr(repair_interface, "RepairCandlesRepository", lambda: repository)
    monkeypatch.setattr(
        repair_interface,
        "build_market_data_adapter",
        lambda config: {"config": config},
    )
    monkeypatch.setattr(
        repair_interface,
        "_MarketDataPortAdapter",
        lambda adapter: FakeMarketDataContext(_FakeMarketPort()),
    )
    monkeypatch.setattr(
        repair_interface,
        "datetime",
        type(
            "_DateTimeModule",
            (),
            {
                "now": staticmethod(
                    lambda tz=None: datetime(2026, 4, 8, 12, 0, tzinfo=tz)
                ),
                "fromisoformat": staticmethod(datetime.fromisoformat),
            },
        )(),
    )

    summary = await repair_interface.run_swap_repair_auto_apply(
        symbol="BTC-USDT-SWAP",
        timeframe="1M",
        strategy=RepairStrategy.GAP_REPAIR,
        max_gap_tasks_per_run=10,
        max_requested_bars_per_run=100,
        max_range_days=7,
        max_fail_ratio=0.2,
        padding_bars=0,
    )

    assert summary["timeframe"] == "1M"
    assert summary["rows_written"] == 1
    assert summary["outcome"] == "success"


@pytest.mark.asyncio
async def test_plan_swap_repair_delegates_preview_with_anchor_strategy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _fake_preview_repair_timeframe(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return type(
            "FakePreview",
            (),
            {
                "to_dict": lambda self: {
                    "requested_mode": "apply",
                    "strategy": "gap-repair",
                    "symbol": kwargs["symbol"],
                    "timeframe": kwargs["timeframe"],
                    "window": {"start_ts_ms": 10, "end_ts_ms": 100},
                    "auto_apply_window": kwargs["auto_apply_window"],
                    "gap_tasks": 2,
                    "requested_bars": 20,
                    "expected_iteration_count": 2,
                    "guardrail_risk": "high",
                    "guardrail_violations": ["max_range_days"],
                }
            },
        )()

    monkeypatch.setattr(repair_interface, "RepairCandlesRepository", FakeRepository)
    monkeypatch.setattr(
        repair_interface, "preview_repair_timeframe", _fake_preview_repair_timeframe
    )
    monkeypatch.setattr(
        repair_interface,
        "datetime",
        type(
            "_DateTimeModule",
            (),
            {
                "now": staticmethod(
                    lambda tz=None: datetime(2026, 4, 11, 12, 34, tzinfo=tz)
                ),
                "fromisoformat": staticmethod(datetime.fromisoformat),
            },
        )(),
    )

    preview = await repair_interface.plan_swap_repair(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=None,
        end_ts_ms=None,
        mode=RepairExecutionMode.APPLY,
        strategy=RepairStrategy.GAP_REPAIR,
        auto_apply_window=True,
        max_gap_tasks_per_run=10,
        max_requested_bars_per_run=100,
        max_range_days=7,
        max_fail_ratio=0.2,
        padding_bars=0,
        anchor_ts_ms=1_775_001_600_000,
        auto_apply_anchor_strategy="explicit",
    )

    assert calls[0]["mode"] is RepairExecutionMode.APPLY
    assert calls[0]["auto_apply_window"] is True
    assert calls[0]["anchor_ts_ms"] == 1_775_001_600_000
    assert calls[0]["anchor_strategy"] == "explicit"
    assert preview["expected_iteration_count"] == 2
