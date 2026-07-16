"""Shadow-mode comparison: raw passthrough vs facade (§12.11 steps 2-3).

Before any analytical consumer is cut over to the candles facade, the
migration procedure requires running the facade in shadow mode and comparing
its output against raw reads:

    trivial series: facade output must be byte-identical to raw
                    (0 discrepancies is the only acceptable result);
    composite series (ton_gram): facade output legitimately differs from a
                    naive "read the raw OHLCV table by symbol" query at the
                    succession boundary and across classified gaps — every
                    difference must be explained by segment/gap metadata,
                    not silently swallowed.

This module contains only the pure comparison logic (no I/O), so it can be
unit-tested with synthetic fixtures; a live run against the real database
wires `SqlOhlcvFacadeRepository` output and raw/segment/gap queries into
these functions (see `scripts/shadow_mode_compare_2026-07-03.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from src.identity.application.ohlcv_facade import OhlcvFacadeRow

_COMPARED_FIELDS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class RawBar:
    symbol: str
    timestamp: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class GapWindow:
    gap_start_ts: int
    gap_end_ts: int
    gap_type: str


@dataclass(frozen=True)
class SegmentWindow:
    source_symbol: str
    segment_start_ts: int
    segment_end_ts: int | None


@dataclass(frozen=True)
class RowMismatch:
    timestamp: int
    kind: str
    detail: str


@dataclass(frozen=True)
class ExplainedDiscrepancy:
    timestamp: int
    kind: str
    detail: str


@dataclass(frozen=True)
class TrivialShadowResult:
    series_id: str
    timeframe: str
    raw_count: int
    facade_count: int
    mismatches: tuple[RowMismatch, ...]

    @property
    def is_clean(self) -> bool:
        return not self.mismatches


@dataclass(frozen=True)
class CompositeShadowResult:
    series_id: str
    timeframe: str
    raw_symbol_counts: Mapping[str, int]
    facade_bar_count: int
    facade_gap_marker_count: int
    explained: tuple[ExplainedDiscrepancy, ...]
    unexplained: tuple[RowMismatch, ...]

    @property
    def is_clean(self) -> bool:
        return not self.unexplained


def compare_trivial_series(
    series_id: str,
    timeframe: str,
    raw_rows: Iterable[RawBar],
    facade_rows: Iterable[OhlcvFacadeRow],
) -> TrivialShadowResult:
    """0 mismatches is the only acceptable outcome for a trivial series."""
    raw_by_ts = {row.timestamp: row for row in raw_rows}
    facade_by_ts = {row.timestamp: row for row in facade_rows if not row.is_gap}

    mismatches: list[RowMismatch] = []

    for timestamp, raw in raw_by_ts.items():
        facade = facade_by_ts.get(timestamp)
        if facade is None:
            mismatches.append(
                RowMismatch(
                    timestamp, "missing_in_facade", "raw row absent from facade output"
                )
            )
            continue

        if facade.bar_kind != "native":
            mismatches.append(
                RowMismatch(
                    timestamp,
                    "bar_kind_mismatch",
                    f"expected native, got {facade.bar_kind}",
                )
            )
        if facade.adjustment_factor != Decimal("1"):
            mismatches.append(
                RowMismatch(
                    timestamp,
                    "adjustment_factor_mismatch",
                    f"expected 1, got {facade.adjustment_factor}",
                )
            )
        if facade.succession_id is not None:
            mismatches.append(
                RowMismatch(
                    timestamp,
                    "succession_id_mismatch",
                    f"expected None, got {facade.succession_id}",
                )
            )

        for field in _COMPARED_FIELDS:
            raw_value = getattr(raw, field)
            facade_value = getattr(facade, field)
            if raw_value != facade_value:
                mismatches.append(
                    RowMismatch(
                        timestamp,
                        "value_mismatch",
                        f"{field}: raw={raw_value} facade={facade_value}",
                    )
                )

    for timestamp in facade_by_ts:
        if timestamp not in raw_by_ts:
            mismatches.append(
                RowMismatch(timestamp, "missing_in_raw", "facade row absent from raw")
            )

    return TrivialShadowResult(
        series_id=series_id,
        timeframe=timeframe,
        raw_count=len(raw_by_ts),
        facade_count=len(facade_by_ts),
        mismatches=tuple(sorted(mismatches, key=lambda item: item.timestamp)),
    )


def _segment_for_timestamp(
    segments: list[SegmentWindow], timestamp: int
) -> SegmentWindow | None:
    for segment in segments:
        if segment.segment_start_ts <= timestamp and (
            segment.segment_end_ts is None or timestamp < segment.segment_end_ts
        ):
            return segment
    return None


def _gap_covering_timestamp(
    gap_ranges: list[GapWindow], timestamp: int
) -> GapWindow | None:
    for gap in gap_ranges:
        if gap.gap_start_ts <= timestamp < gap.gap_end_ts:
            return gap
    return None


def compare_composite_series(
    series_id: str,
    timeframe: str,
    raw_rows_by_symbol: Mapping[str, Iterable[RawBar]],
    facade_rows: Iterable[OhlcvFacadeRow],
    gap_ranges: Iterable[GapWindow],
    segments: Iterable[SegmentWindow],
) -> CompositeShadowResult:
    """Every facade/raw discrepancy for a composite series must be explained
    by segment metadata (succession boundary) or gap metadata (classified
    gap) — never silently accepted."""
    gap_ranges = list(gap_ranges)
    segments = list(segments)
    facade_rows = list(facade_rows)

    facade_bars_by_ts = {row.timestamp: row for row in facade_rows if not row.is_gap}
    facade_gap_by_ts = {row.timestamp: row for row in facade_rows if row.is_gap}

    raw_counts: dict[str, int] = {}
    raw_by_symbol_ts: dict[tuple[str, int], RawBar] = {}
    for symbol, rows in raw_rows_by_symbol.items():
        rows = list(rows)
        raw_counts[symbol] = len(rows)
        for row in rows:
            raw_by_symbol_ts[(symbol, row.timestamp)] = row

    explained: list[ExplainedDiscrepancy] = []
    unexplained: list[RowMismatch] = []
    timestamps_seen_in_raw: set[int] = set()

    for (symbol, timestamp), raw in raw_by_symbol_ts.items():
        timestamps_seen_in_raw.add(timestamp)
        facade = facade_bars_by_ts.get(timestamp)
        segment = _segment_for_timestamp(segments, timestamp)

        if facade is not None and facade.source_symbol == symbol:
            for field in _COMPARED_FIELDS:
                raw_value = getattr(raw, field)
                facade_value = getattr(facade, field)
                if raw_value != facade_value:
                    unexplained.append(
                        RowMismatch(
                            timestamp,
                            "value_mismatch",
                            f"{field}: raw={raw_value} facade={facade_value}",
                        )
                    )
            continue

        if facade is not None and facade.source_symbol != symbol:
            if segment is not None and segment.source_symbol != symbol:
                explained.append(
                    ExplainedDiscrepancy(
                        timestamp,
                        "segment_source_symbol_changed",
                        f"raw {symbol} bar superseded by segment "
                        f"source_symbol={segment.source_symbol}",
                    )
                )
                continue
            unexplained.append(
                RowMismatch(
                    timestamp,
                    "source_symbol_mismatch",
                    f"raw={symbol} facade={facade.source_symbol}, "
                    "no segment metadata explains it",
                )
            )
            continue

        gap = _gap_covering_timestamp(gap_ranges, timestamp)
        if gap is not None:
            explained.append(
                ExplainedDiscrepancy(
                    timestamp,
                    "known_gap",
                    f"raw {symbol} bar inside {gap.gap_type} "
                    f"[{gap.gap_start_ts}, {gap.gap_end_ts})",
                )
            )
            continue

        unexplained.append(
            RowMismatch(
                timestamp,
                "missing_in_facade",
                f"raw {symbol} bar absent from facade and not inside a known gap",
            )
        )

    for timestamp in facade_bars_by_ts:
        if timestamp not in timestamps_seen_in_raw:
            unexplained.append(
                RowMismatch(
                    timestamp,
                    "missing_in_raw",
                    "facade bar has no matching raw row in any known leg",
                )
            )

    for timestamp, gap_row in facade_gap_by_ts.items():
        explained.append(
            ExplainedDiscrepancy(
                timestamp,
                "gap_marker_output_only",
                f"output-only marker, type={gap_row.gap_type}",
            )
        )

    return CompositeShadowResult(
        series_id=series_id,
        timeframe=timeframe,
        raw_symbol_counts=raw_counts,
        facade_bar_count=len(facade_bars_by_ts),
        facade_gap_marker_count=len(facade_gap_by_ts),
        explained=tuple(
            sorted(explained, key=lambda item: (item.timestamp, item.kind))
        ),
        unexplained=tuple(sorted(unexplained, key=lambda item: item.timestamp)),
    )
