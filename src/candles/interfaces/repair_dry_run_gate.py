from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import pairwise
from typing import Any, Protocol


class CandleCoveragePort(Protocol):
    async def list_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[int]: ...


class HistoricalCandlesPort(Protocol):
    async def get_history_candles(
        self,
        *,
        inst_id: str,
        bar: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class RepairDryRunGateRequest:
    symbol: str
    timeframe: str
    start_ts_ms: int
    end_ts_ms: int


@dataclass(frozen=True, slots=True)
class RepairDryRunGateReport:
    symbol: str
    timeframe: str
    window: dict[str, int]
    db_row_count: int
    okx_row_count: int
    db_duplicate_timestamps: int
    okx_duplicate_timestamps: int
    db_monotonic: bool
    okx_monotonic: bool
    discrepancies: list[dict[str, Any]]
    gate_passed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _timestamp_from_candle(candle: dict[str, Any]) -> int:
    if "ts" in candle:
        return int(candle["ts"])
    return int(candle["timestamp"])


def _duplicate_count(timestamps: list[int]) -> int:
    return len(timestamps) - len(set(timestamps))


def _is_strictly_monotonic(timestamps: list[int]) -> bool:
    return all(left < right for left, right in pairwise(timestamps))


def _sample(values: set[int]) -> list[int]:
    return sorted(values)[:10]


def _failing_discrepancy(discrepancy: dict[str, Any]) -> bool:
    return str(discrepancy["classification"]) in {
        "raw_integrity_violation",
        "requires_manual_review",
    }


async def run_repair_dry_run_gate(
    *,
    request: RepairDryRunGateRequest,
    coverage: CandleCoveragePort,
    history: HistoricalCandlesPort,
) -> RepairDryRunGateReport:
    db_timestamps = await coverage.list_timestamps(
        symbol=request.symbol,
        timeframe=request.timeframe,
        start_ts_ms=request.start_ts_ms,
        end_ts_ms=request.end_ts_ms,
    )
    okx_timestamps = [
        _timestamp_from_candle(candle)
        for candle in await history.get_history_candles(
            inst_id=request.symbol,
            bar=request.timeframe,
            start_ts_ms=request.start_ts_ms,
            end_ts_ms=request.end_ts_ms,
        )
    ]

    db_duplicates = _duplicate_count(db_timestamps)
    okx_duplicates = _duplicate_count(okx_timestamps)
    db_monotonic = _is_strictly_monotonic(db_timestamps)
    okx_monotonic = _is_strictly_monotonic(okx_timestamps)
    db_only = set(db_timestamps) - set(okx_timestamps)
    okx_only = set(okx_timestamps) - set(db_timestamps)

    discrepancies: list[dict[str, Any]] = []
    if db_duplicates:
        discrepancies.append(
            {
                "code": "db_duplicate_timestamps",
                "classification": "raw_integrity_violation",
                "count": db_duplicates,
            }
        )
    if okx_duplicates:
        discrepancies.append(
            {
                "code": "okx_duplicate_timestamps",
                "classification": "exchange_payload_duplicate",
                "count": okx_duplicates,
            }
        )
    if not db_monotonic:
        discrepancies.append(
            {
                "code": "db_non_monotonic_timestamps",
                "classification": "raw_integrity_violation",
            }
        )
    if not okx_monotonic:
        discrepancies.append(
            {
                "code": "okx_non_monotonic_timestamps",
                "classification": "exchange_payload_ordering",
            }
        )
    if okx_only:
        discrepancies.append(
            {
                "code": "db_missing_okx_timestamps",
                "classification": "repairable_raw_gap",
                "count": len(okx_only),
                "sample": _sample(okx_only),
            }
        )
    if db_only and not okx_timestamps:
        discrepancies.append(
            {
                "code": "okx_history_unavailable_for_db_timestamps",
                "classification": "retired_instrument_history_unavailable",
                "count": len(db_only),
                "sample": _sample(db_only),
            }
        )
    elif db_only:
        discrepancies.append(
            {
                "code": "db_extra_timestamps_not_in_okx",
                "classification": "requires_manual_review",
                "count": len(db_only),
                "sample": _sample(db_only),
            }
        )

    gate_passed = not any(_failing_discrepancy(item) for item in discrepancies)
    return RepairDryRunGateReport(
        symbol=request.symbol,
        timeframe=request.timeframe,
        window={
            "start_ts_ms": request.start_ts_ms,
            "end_ts_ms": request.end_ts_ms,
        },
        db_row_count=len(db_timestamps),
        okx_row_count=len(okx_timestamps),
        db_duplicate_timestamps=db_duplicates,
        okx_duplicate_timestamps=okx_duplicates,
        db_monotonic=db_monotonic,
        okx_monotonic=okx_monotonic,
        discrepancies=discrepancies,
        gate_passed=gate_passed,
    )
