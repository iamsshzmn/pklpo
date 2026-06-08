from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BootstrapCommand:
    symbol: str
    timeframe: str
    lookback_days: int
    chunk_bars: int = 500
    circuit_break_after: int = 3
    dry_run: bool = False


@dataclass(frozen=True)
class BootstrapResult:
    symbol: str
    timeframe: str
    status: str
    chunks_fetched: int
    rows_written: int
    expected_bars: int
    actual_bars: int
    missing_bars: int
    coverage_pct: float
    elapsed_seconds: float
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "status": self.status,
            "chunks_fetched": self.chunks_fetched,
            "rows_written": self.rows_written,
            "expected_bars": self.expected_bars,
            "actual_bars": self.actual_bars,
            "missing_bars": self.missing_bars,
            "coverage_pct": self.coverage_pct,
            "elapsed_seconds": self.elapsed_seconds,
            "error": self.error,
        }


@dataclass(frozen=True)
class BootstrapProgress:
    symbol: str
    timeframe: str
    lookback_days: int
    target_start_ts: int
    target_end_ts: int
    checkpoint_ts: int | None
    current_min_ts: int | None
    current_max_ts: int | None
    expected_bars: int
    actual_bars: int | None
    missing_bars: int | None
    coverage_pct: float | None
    status: str
    bootstrap_completed: bool
    error_streak: int
    last_error: str | None
