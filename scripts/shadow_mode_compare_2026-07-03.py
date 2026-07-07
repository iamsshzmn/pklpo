"""
Shadow-mode comparison: raw passthrough vs facade (§12.11 steps 2-3, Task 4.5).

Usage (requires a reachable Postgres per .env / DATABASE_URL):
    python scripts/shadow_mode_compare_2026-07-03.py
    python scripts/shadow_mode_compare_2026-07-03.py --since-days 30

What it does:
1. Enumerates every trivial series (distinct `swap_ohlcv_p.symbol` not registered
   as `composite` in `core.series_registry`, and not a `core.series_alias`
   `old_series_id` that would resolve to a composite series through the
   facade) x distinct timeframe present for it, and compares raw rows against
   `OhlcvFacade` output. 0 mismatches is the only acceptable result per
   series/timeframe.
2. For every composite series in `core.series_registry` (currently just
   `TON-USDT-SWAP` / label `ton_gram`) x each of its `core.series_segments`
   timeframes, compares raw rows (split by source_symbol leg) against the
   facade's continuous output (with `include_gap_markers=True`), classifying
   every discrepancy against `core.series_gap_ranges` / `core.series_segments`.
   Any *unexplained* discrepancy is a failure. The comparison window is capped
   at the series/timeframe's continuous-build watermark (`MAX(timestamp)` in
   `core.continuous_ohlcv_p`), not wall-clock "now" — raw ingestion runs ahead
   of the periodic continuous build job, and bars newer than the last
   successful build are "not yet due" rather than a facade discrepancy.
3. Prints a per-series/timeframe summary and a final PASS/FAIL line.

Exit codes: 0 = all series clean (trivial: 0 mismatches; composite: 0
unexplained discrepancies), 1 = at least one series failed shadow-mode
(per §12.11: cutover to that series/consumer stays blocked).

NOTE: This is an operational verification script (owner: test-runner in the
implementation plan), not part of the unit test suite. The pure comparison
logic it calls (`src.identity.application.shadow_mode_compare`) is unit
tested with synthetic fixtures in
`tests/identity/test_shadow_mode_compare.py`; this script only wires that
logic to real repositories for a live run.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from src.identity.application.ohlcv_facade import OhlcvFacade
from src.identity.application.shadow_mode_compare import (
    GapWindow,
    RawBar,
    SegmentWindow,
    compare_composite_series,
    compare_trivial_series,
)
from src.identity.infrastructure.ohlcv_facade_repository import (
    SqlOhlcvFacadeRepository,
)
from src.utils.session_utils import get_db_session

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_SINCE_DAYS = 90

TRIVIAL_CANDIDATES_SQL = """
SELECT DISTINCT o.symbol, o.timeframe
FROM public.swap_ohlcv_p o
WHERE NOT EXISTS (
    SELECT 1 FROM core.series_registry r
    WHERE r.series_id = o.symbol AND r.series_kind = 'composite'
)
AND NOT EXISTS (
    -- an aliased symbol resolves through the facade to its canonical
    -- (composite) series_id, so it is not a standalone trivial passthrough.
    SELECT 1 FROM core.series_alias a WHERE a.old_series_id = o.symbol
)
AND o.timestamp >= :since_ms
ORDER BY 1, 2
""".strip()

COMPOSITE_SERIES_SQL = """
SELECT series_id FROM core.series_registry WHERE series_kind = 'composite'
""".strip()

COMPOSITE_TIMEFRAMES_SQL = """
SELECT DISTINCT timeframe FROM core.series_segments WHERE series_id = :series_id
""".strip()

COMPOSITE_MEMBER_SYMBOLS_SQL = """
SELECT DISTINCT source_symbol FROM core.series_members WHERE series_id = :series_id
""".strip()

COMPOSITE_WATERMARK_SQL = """
SELECT MAX(timestamp) FROM core.continuous_ohlcv_p
WHERE series_id = :series_id AND timeframe = :timeframe
""".strip()

RAW_ROWS_SQL = """
SELECT timestamp, open, high, low, close, volume
FROM public.swap_ohlcv_p
WHERE symbol = :symbol AND timeframe = :timeframe
  AND timestamp >= :since_ms AND timestamp < :end_ms
ORDER BY timestamp
""".strip()

GAP_RANGES_SQL = """
SELECT gap_start_ts, gap_end_ts, gap_type
FROM core.series_gap_ranges
WHERE series_id = :series_id AND (timeframe = :timeframe OR timeframe = '*')
  AND known_from <= :as_of AND (known_to IS NULL OR known_to > :as_of)
""".strip()

SEGMENTS_SQL = """
SELECT source_symbol, segment_start_ts, segment_end_ts
FROM core.series_segments
WHERE series_id = :series_id AND timeframe = :timeframe
  AND known_from <= :as_of AND (known_to IS NULL OR known_to > :as_of)
ORDER BY segment_order
""".strip()


@dataclass
class _Report:
    clean_series: list[str]
    failing_series: list[str]

    @property
    def passed(self) -> bool:
        return not self.failing_series


async def _load_raw_bars(
    symbol: str, timeframe: str, since_ms: int, end_ms: int
) -> list[RawBar]:
    async with get_db_session() as session:
        rows = (
            await session.execute(
                text(RAW_ROWS_SQL),
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "since_ms": since_ms,
                    "end_ms": end_ms,
                },
            )
        ).fetchall()
    return [
        RawBar(
            symbol=symbol,
            timestamp=int(row[0]),
            open=Decimal(str(row[1])),
            high=Decimal(str(row[2])),
            low=Decimal(str(row[3])),
            close=Decimal(str(row[4])),
            volume=Decimal(str(row[5])),
        )
        for row in rows
    ]


async def _run_trivial(facade: OhlcvFacade, since_ms: int, as_of: datetime) -> _Report:
    async with get_db_session() as session:
        candidates = (
            await session.execute(text(TRIVIAL_CANDIDATES_SQL), {"since_ms": since_ms})
        ).fetchall()

    end_ts = int(datetime.now(tz=UTC).timestamp() * 1000) + 1

    clean: list[str] = []
    failing: list[str] = []
    for symbol, timeframe in candidates:
        raw_rows = await _load_raw_bars(symbol, timeframe, since_ms, end_ts)
        facade_rows = await facade.read_ohlcv(
            series_id=symbol,
            timeframe=timeframe,
            start_ts=since_ms,
            end_ts=end_ts,
            as_of=as_of,
        )
        result = compare_trivial_series(symbol, timeframe, raw_rows, facade_rows)
        label = f"{symbol} {timeframe} (raw={result.raw_count} facade={result.facade_count})"
        if result.is_clean:
            clean.append(label)
            logger.info("CLEAN  trivial %s", label)
        else:
            failing.append(label)
            logger.error(
                "MISMATCH trivial %s: %d mismatch(es), first=%s",
                label,
                len(result.mismatches),
                result.mismatches[0],
            )
    return _Report(clean_series=clean, failing_series=failing)


async def _run_composite(
    facade: OhlcvFacade, since_ms: int, as_of: datetime
) -> _Report:
    async with get_db_session() as session:
        series_ids = [
            row[0]
            for row in (await session.execute(text(COMPOSITE_SERIES_SQL))).fetchall()
        ]

    clean: list[str] = []
    failing: list[str] = []
    for series_id in series_ids:
        async with get_db_session() as session:
            timeframes = [
                row[0]
                for row in (
                    await session.execute(
                        text(COMPOSITE_TIMEFRAMES_SQL), {"series_id": series_id}
                    )
                ).fetchall()
            ]
            member_symbols = [
                row[0]
                for row in (
                    await session.execute(
                        text(COMPOSITE_MEMBER_SYMBOLS_SQL), {"series_id": series_id}
                    )
                ).fetchall()
            ]

        for timeframe in timeframes:
            async with get_db_session() as session:
                watermark = (
                    await session.execute(
                        text(COMPOSITE_WATERMARK_SQL),
                        {"series_id": series_id, "timeframe": timeframe},
                    )
                ).scalar_one_or_none()

            if watermark is None:
                logger.warning(
                    "SKIP composite %s %s: no continuous_ohlcv_p rows yet",
                    series_id,
                    timeframe,
                )
                continue

            # Cap the comparison window at the continuous build's watermark:
            # raw ingestion runs ahead of the periodic build job, so bars
            # newer than the last successful build are "not yet due" rather
            # than a facade discrepancy.
            end_ts = int(watermark) + 1

            raw_rows_by_symbol = {
                symbol: await _load_raw_bars(symbol, timeframe, since_ms, end_ts)
                for symbol in member_symbols
            }
            facade_rows = await facade.read_ohlcv(
                series_id=series_id,
                timeframe=timeframe,
                start_ts=since_ms,
                end_ts=end_ts,
                as_of=as_of,
                include_gap_markers=True,
            )
            async with get_db_session() as session:
                gap_rows = (
                    await session.execute(
                        text(GAP_RANGES_SQL),
                        {
                            "series_id": series_id,
                            "timeframe": timeframe,
                            "as_of": as_of,
                        },
                    )
                ).fetchall()
                segment_rows = (
                    await session.execute(
                        text(SEGMENTS_SQL),
                        {
                            "series_id": series_id,
                            "timeframe": timeframe,
                            "as_of": as_of,
                        },
                    )
                ).fetchall()

            gap_ranges = [
                GapWindow(
                    gap_start_ts=int(r[0]), gap_end_ts=int(r[1]), gap_type=str(r[2])
                )
                for r in gap_rows
            ]
            segments = [
                SegmentWindow(
                    source_symbol=str(r[0]),
                    segment_start_ts=int(r[1]),
                    segment_end_ts=None if r[2] is None else int(r[2]),
                )
                for r in segment_rows
            ]

            result = compare_composite_series(
                series_id,
                timeframe,
                raw_rows_by_symbol,
                facade_rows,
                gap_ranges,
                segments,
            )
            label = (
                f"{series_id} {timeframe} (raw={result.raw_symbol_counts} "
                f"facade_bars={result.facade_bar_count} "
                f"gap_markers={result.facade_gap_marker_count} "
                f"explained={len(result.explained)})"
            )
            if result.is_clean:
                clean.append(label)
                logger.info("CLEAN  composite %s", label)
            else:
                failing.append(label)
                logger.error(
                    "UNEXPLAINED composite %s: %d unexplained, first=%s",
                    label,
                    len(result.unexplained),
                    result.unexplained[0],
                )
    return _Report(clean_series=clean, failing_series=failing)


async def _main(since_days: int) -> int:
    since_ms = int(datetime.now(tz=UTC).timestamp() * 1000) - since_days * 86_400_000
    as_of = datetime.now(tz=UTC)
    facade = OhlcvFacade(SqlOhlcvFacadeRepository(), continuous_read_enabled=True)

    trivial_report = await _run_trivial(facade, since_ms, as_of)
    composite_report = await _run_composite(facade, since_ms, as_of)

    logger.info(
        "Trivial: %d clean, %d failing",
        len(trivial_report.clean_series),
        len(trivial_report.failing_series),
    )
    logger.info(
        "Composite: %d clean, %d failing",
        len(composite_report.clean_series),
        len(composite_report.failing_series),
    )

    passed = trivial_report.passed and composite_report.passed
    logger.info("SHADOW MODE %s", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since-days",
        type=int,
        default=DEFAULT_SINCE_DAYS,
        help=f"Compare only bars newer than N days ago (default {DEFAULT_SINCE_DAYS}).",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args.since_days)))
