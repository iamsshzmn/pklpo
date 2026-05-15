from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .dto import BootstrapResult


@dataclass(frozen=True)
class BootstrapSummary:
    total: int
    completed: int
    incomplete: int
    stuck: int
    failed: int
    skipped: int
    total_rows_written: int
    total_chunks_fetched: int
    total_expected_bars: int
    total_actual_bars: int
    total_missing_bars: int
    elapsed_seconds: float

    @property
    def overall_coverage_pct(self) -> float:
        if self.total_expected_bars == 0:
            return 100.0
        return self.total_actual_bars / self.total_expected_bars * 100.0

    def to_dict(self) -> dict[str, object]:
        return {
            "total": self.total,
            "completed": self.completed,
            "incomplete": self.incomplete,
            "stuck": self.stuck,
            "failed": self.failed,
            "skipped": self.skipped,
            "total_rows_written": self.total_rows_written,
            "total_chunks_fetched": self.total_chunks_fetched,
            "total_expected_bars": self.total_expected_bars,
            "total_actual_bars": self.total_actual_bars,
            "total_missing_bars": self.total_missing_bars,
            "overall_coverage_pct": round(self.overall_coverage_pct, 2),
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }


def merge_bootstrap_results(results: list[BootstrapResult]) -> BootstrapSummary:
    counts: dict[str, int] = {"completed": 0, "incomplete": 0, "stuck": 0, "failed": 0}
    skipped = 0
    rows_written = 0
    chunks_fetched = 0
    expected_bars = 0
    actual_bars = 0
    missing_bars = 0
    elapsed = 0.0

    for r in results:
        status = r.status
        if status in counts:
            counts[status] += 1
        else:
            # Any status not in the known counts (e.g. "skipped" early-exit) goes here
            skipped += 1
        rows_written += r.rows_written
        chunks_fetched += r.chunks_fetched
        expected_bars += r.expected_bars
        actual_bars += r.actual_bars
        missing_bars += r.missing_bars
        elapsed += r.elapsed_seconds

    return BootstrapSummary(
        total=len(results),
        completed=counts["completed"],
        incomplete=counts["incomplete"],
        stuck=counts["stuck"],
        failed=counts["failed"],
        skipped=skipped,
        total_rows_written=rows_written,
        total_chunks_fetched=chunks_fetched,
        total_expected_bars=expected_bars,
        total_actual_bars=actual_bars,
        total_missing_bars=missing_bars,
        elapsed_seconds=elapsed,
    )
