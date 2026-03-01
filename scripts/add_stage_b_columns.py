#!/usr/bin/env python3
"""
Migration script to add missing Stage B (Trend) columns to indicators table.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def main():
    # Load environment variables
    load_dotenv()

    # Get database URL and fix for local access
    url = (
        os.environ["DATABASE_URL"]
        .replace("+asyncpg", "+psycopg2")
        .replace("pklpo_db:5432", "localhost:5432")
    )
    eng = create_engine(url)

    # Missing Stage B columns
    missing_columns = [
        "aroon_14",
        "aroon_down",
        "aroon_up",
        "cci_14",
        "psar",
        "sma_20",
        "sma_50",
        "sma_200",
        "trix_14",
        "vortex_neg",
        "vortex_pos",
    ]

    with eng.begin() as c:
        print("Adding missing Stage B (Trend) columns to indicators table...")

        for column in missing_columns:
            try:
                # Add column with DOUBLE PRECISION type (same as other numeric columns)
                alter_sql = (
                    f"ALTER TABLE indicators ADD COLUMN {column} DOUBLE PRECISION"
                )
                c.execute(text(alter_sql))
                print(f"[OK] Added column: {column}")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e):
                    print(f"[WARN] Column {column} already exists")
                else:
                    print(f"[ERROR] Error adding column {column}: {e}")

        print("\nStage B migration completed!")

        # Verify the columns were added
        result = c.execute(
            text(
                """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'indicators'
            AND column_name IN ('aroon_14', 'aroon_down', 'aroon_up', 'cci_14', 'psar', 'sma_20', 'sma_50', 'sma_200', 'trix_14', 'vortex_neg', 'vortex_pos')
            ORDER BY column_name
        """
            )
        )
        added_columns = [row[0] for row in result.fetchall()]

        print(f"\nVerification - Added columns: {added_columns}")
        print(f"Expected: {missing_columns}")
        print(f"Success: {len(added_columns)}/{len(missing_columns)} columns added")


if __name__ == "__main__":
    main()
