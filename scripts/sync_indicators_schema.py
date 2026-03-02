import os
import sys

from sqlalchemy import create_engine, text

STAGE_A_COLUMNS: dict[str, str] = {
    # candles / squeeze / stochrsi
    "stochrsi_k": "DOUBLE PRECISION",
    "stochrsi_d": "DOUBLE PRECISION",
    "ttm_squeeze_on": "INTEGER",
    "ttm_squeeze_hist": "DOUBLE PRECISION",
    "ttm_squeeze_value": "DOUBLE PRECISION",
    # overlap
    "hl2": "DOUBLE PRECISION",
    "hlc3": "DOUBLE PRECISION",
    "ohlc4": "DOUBLE PRECISION",
    "wcp": "DOUBLE PRECISION",
    "midpoint": "DOUBLE PRECISION",
    "midprice": "DOUBLE PRECISION",
    # statistics
    "median_20": "DOUBLE PRECISION",
    "mad_20": "DOUBLE PRECISION",
    "stdev_20": "DOUBLE PRECISION",
    "variance_20": "DOUBLE PRECISION",
    "skew_20": "DOUBLE PRECISION",
    "kurtosis_20": "DOUBLE PRECISION",
    "zscore_20": "DOUBLE PRECISION",
    # performance
    "log_return": "DOUBLE PRECISION",
    "percent_return": "DOUBLE PRECISION",
    "trend_return_20": "DOUBLE PRECISION",
    "drawdown": "DOUBLE PRECISION",
}


def get_existing_columns(engine) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'indicators'
            ORDER BY ordinal_position
            """
            )
        ).fetchall()
        return [r[0] for r in rows]


def sync_stage_a(engine):
    existing = set(get_existing_columns(engine))

    to_add = [
        (col, dtype) for col, dtype in STAGE_A_COLUMNS.items() if col not in existing
    ]
    to_drop = [
        col
        for col in STAGE_A_COLUMNS
        if col in existing
        and os.environ.get("DROP_UNUSED_STAGE_A", "0") == "1"
        and False
    ]
    # By default do not drop automatically to avoid accidental data loss. Enable with env var and logic if needed.

    if not to_add and not to_drop:
        print("[schema-sync] Stage A: nothing to change")
        return

    with engine.begin() as conn:
        for col, dtype in to_add:
            print(f"[schema-sync] ADD COLUMN {col} {dtype}")
            conn.execute(
                text(f"ALTER TABLE indicators ADD COLUMN IF NOT EXISTS {col} {dtype}")
            )

        for col in to_drop:
            print(f"[schema-sync] DROP COLUMN {col}")
            conn.execute(text(f"ALTER TABLE indicators DROP COLUMN IF EXISTS {col}"))


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL is not set", file=sys.stderr)
        sys.exit(2)
    engine = create_engine(db_url.replace("+asyncpg", "+psycopg2"))
    sync_stage_a(engine)
    print("[schema-sync] Done")


if __name__ == "__main__":
    main()
