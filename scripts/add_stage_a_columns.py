#!/usr/bin/env python3
"""
Migration script to add missing Stage A columns to indicators table.
"""

import os

from sqlalchemy import create_engine, text


def main():
    # Get database URL
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "+psycopg2")
    eng = create_engine(url)

    # Missing Stage A columns
    missing_columns = [
        "midpoint",
        "midprice",
        "mad_20",
        "variance_20",
        "skew_20",
        "kurtosis_20",
        "trend_return_20",
    ]

    with eng.begin() as c:
        print("Adding missing Stage A columns to indicators table...")

        for column in missing_columns:
            try:
                # Add column with DOUBLE PRECISION type (same as other numeric columns)
                alter_sql = (
                    f"ALTER TABLE indicators ADD COLUMN {column} DOUBLE PRECISION"
                )
                c.execute(text(alter_sql))
                print(f"✅ Added column: {column}")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e):
                    print(f"⚠️ Column {column} already exists")
                else:
                    print(f"❌ Error adding column {column}: {e}")

        print("\nMigration completed!")

        # Verify the columns were added
        result = c.execute(
            text(
                """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'indicators'
            AND column_name IN ('midpoint', 'midprice', 'mad_20', 'variance_20', 'skew_20', 'kurtosis_20', 'trend_return_20')
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
