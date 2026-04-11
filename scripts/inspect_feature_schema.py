"""Inspect the effective feature schema produced by compute_features().

Usage examples:
    python scripts/inspect_feature_schema.py
    python scripts/inspect_feature_schema.py --rows 600 --compare-db
    python scripts/inspect_feature_schema.py --compare-db --output-json tmp/feature_schema.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.features.api import compute_features
from src.features.storage_contract import IndicatorStorageContract

OHLCV_COLUMNS = {"open", "high", "low", "close", "volume", "timestamp", "ts"}


def build_sample_ohlcv(rows: int) -> pd.DataFrame:
    """Build a deterministic OHLCV frame large enough for long-period indicators."""
    base_ts = 1_700_000_000_000
    data: list[dict[str, float | int]] = []

    for i in range(rows):
        trend = i * 0.12
        wave = math.sin(i / 12.0) * 4.0
        close = 100.0 + trend + wave
        open_ = close - math.cos(i / 9.0) * 0.8
        high = max(open_, close) + 0.9 + abs(math.sin(i / 7.0)) * 0.7
        low = min(open_, close) - 0.9 - abs(math.cos(i / 7.0)) * 0.7
        volume = 1_000.0 + (i % 50) * 23.0 + abs(math.sin(i / 5.0)) * 150.0
        data.append(
            {
                "timestamp": base_ts + i * 60_000,
                "open": round(open_, 6),
                "high": round(high, 6),
                "low": round(low, 6),
                "close": round(close, 6),
                "volume": round(volume, 6),
            }
        )

    return pd.DataFrame(data)


def extract_feature_columns(result_df: pd.DataFrame) -> list[str]:
    """Return computed feature columns only, excluding OHLCV/service fields."""
    excluded = OHLCV_COLUMNS | {
        "calculated_at",
        "data_status",
        "failed_groups",
    }
    return sorted(col for col in result_df.columns if col not in excluded)


async def load_db_columns(database_url: str, table_name: str) -> list[str]:
    """Read the live DB schema for the target table."""
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = :table_name
                    ORDER BY ordinal_position
                    """
                ),
                {"table_name": table_name},
            )
            return [row[0] for row in result.fetchall()]
    finally:
        await engine.dispose()


def build_report(
    computed_columns: list[str],
    db_columns: list[str] | None,
) -> dict[str, object]:
    """Build a serializable report."""
    report: dict[str, object] = {
        "table_name": IndicatorStorageContract.table_name,
        "computed_feature_count": len(computed_columns),
        "computed_feature_columns": computed_columns,
    }

    if db_columns is None:
        return report

    db_column_set = set(db_columns)
    missing_in_db = [col for col in computed_columns if col not in db_column_set]
    extra_in_db = [
        col
        for col in db_columns
        if col not in computed_columns and col not in IndicatorStorageContract.identity_fields
    ]

    report.update(
        {
            "db_column_count": len(db_columns),
            "db_columns": db_columns,
            "missing_in_db_count": len(missing_in_db),
            "missing_in_db": missing_in_db,
            "extra_in_db_count": len(extra_in_db),
            "extra_in_db": extra_in_db,
        }
    )
    return report


def print_report(report: dict[str, object]) -> None:
    """Print a readable report for terminal use."""
    print("=" * 80)
    print("FEATURE SCHEMA INSPECTION")
    print("=" * 80)
    print(f"Target table: {report['table_name']}")
    print(f"Computed feature columns: {report['computed_feature_count']}")

    sample = report["computed_feature_columns"][:20]
    if sample:
        print("Computed sample:", ", ".join(sample))

    if "db_column_count" not in report:
        return

    print(f"DB columns in table: {report['db_column_count']}")
    print(f"Missing in DB: {report['missing_in_db_count']}")
    missing = report["missing_in_db"]
    if missing:
        print("Missing sample:", ", ".join(missing[:30]))

    print(f"Extra DB columns: {report['extra_in_db_count']}")
    extra = report["extra_in_db"]
    if extra:
        print("Extra sample:", ", ".join(extra[:30]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate features on synthetic OHLCV and show which columns the "
            "live indicators_p table must contain."
        )
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=600,
        help="Synthetic OHLCV row count. Use >= 500 for long warmup indicators.",
    )
    parser.add_argument(
        "--compare-db",
        action="store_true",
        help="Compare computed columns against the live indicators_p schema.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Database URL for --compare-db. Defaults to DATABASE_URL env var.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional path to save the full report as JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    df = build_sample_ohlcv(args.rows)
    result_df = compute_features(
        df,
        specs=None,
        volatility_normalize=False,
        debug=False,
    )
    computed_columns = extract_feature_columns(result_df)

    db_columns: list[str] | None = None
    if args.compare_db:
        if not args.database_url:
            print("DATABASE_URL is required for --compare-db", file=sys.stderr)
            return 2
        db_columns = asyncio.run(
            load_db_columns(args.database_url, IndicatorStorageContract.table_name)
        )

    report = build_report(computed_columns, db_columns)
    print_report(report)

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Saved JSON report to {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
