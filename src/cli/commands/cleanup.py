"""CLI command for policy-driven swap_ohlcv_p cleanup."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "cleanup",
        help="Run policy-driven swap_ohlcv_p cleanup",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show policy cutoffs and row counts without deleting data",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Deprecated; retention is now read from swap_ohlcv_retention_policy",
    )
    parser.add_argument("--stats", action="store_true", help="Show swap_ohlcv_p stats")
    parser.set_defaults(_handler=handle)


async def handle(args: Any) -> None:
    if args.days is not None:
        logger.warning("--days is deprecated; using swap_ohlcv_retention_policy")
    if args.stats:
        await show_stats()
    elif args.dry_run:
        await dry_run_cleanup()
    else:
        await perform_cleanup()


async def show_stats() -> None:
    async with get_db_session() as session:
        result = await session.execute(
            text(
                """
                SELECT
                    timeframe,
                    COUNT(*) AS rows,
                    MIN(timestamp) AS oldest_timestamp,
                    MAX(timestamp) AS newest_timestamp
                FROM swap_ohlcv_p
                GROUP BY timeframe
                ORDER BY timeframe
                """
            )
        )
        rows = result.fetchall()

    print("swap_ohlcv_p stats")
    for timeframe, count, oldest, newest in rows:
        print(
            f"  {timeframe}: rows={count:,}, oldest={oldest}, newest={newest}"
        )


async def dry_run_cleanup() -> None:
    async with get_db_session() as session:
        result = await session.execute(
            text(
                """
                SELECT
                    p.timeframe,
                    p.retention_days,
                    CASE
                        WHEN p.retention_days IS NULL THEN NULL
                        ELSE (
                            EXTRACT(EPOCH FROM NOW() - make_interval(days => p.retention_days)) * 1000
                        )::BIGINT
                    END AS cutoff_timestamp,
                    CASE
                        WHEN p.retention_days IS NULL THEN 0
                        ELSE (
                            SELECT COUNT(*)
                            FROM swap_ohlcv_p c
                            WHERE c.timeframe = p.timeframe
                              AND c.timestamp < (
                                  EXTRACT(EPOCH FROM NOW() - make_interval(days => p.retention_days)) * 1000
                              )::BIGINT
                        )
                    END AS count_to_delete
                FROM swap_ohlcv_retention_policy p
                ORDER BY p.timeframe
                """
            )
        )
        rows = result.fetchall()

    print("DRY RUN: policy-driven swap_ohlcv_p cleanup")
    for timeframe, retention_days, cutoff_timestamp, count_to_delete in rows:
        retention = "infinite" if retention_days is None else f"{retention_days} days"
        print(
            f"  {timeframe}: retention={retention}, cutoff={cutoff_timestamp}, "
            f"rows_to_delete={count_to_delete:,}"
        )


async def perform_cleanup() -> None:
    async with get_db_session() as session:
        try:
            result = await session.execute(
                text("SELECT * FROM cleanup_old_swap_data(:triggered_by)"),
                {"triggered_by": "cli"},
            )
            rows = result.fetchall()
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    deleted_total = sum(int(row[2]) for row in rows)
    print("policy-driven swap_ohlcv_p cleanup complete")
    for row in rows:
        timeframe, cutoff_timestamp, deleted_count, duration_ms, skipped_reason = row
        print(
            f"  {timeframe}: cutoff={cutoff_timestamp}, deleted={deleted_count}, "
            f"duration_ms={duration_ms}, skipped={skipped_reason}"
        )
    print(f"deleted_total={deleted_total}")
