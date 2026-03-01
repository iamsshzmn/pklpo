#!/usr/bin/env python3
"""
Add remaining Stage E columns that were missed.
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

    # Remaining Stage E columns
    missing_columns = [
        "amat",
        "chop",
        "decay",
        "decreasing",
        "dpo",
        "increasing",
        "long_run",
        "short_run",
        "slope_20",
    ]

    with eng.begin() as c:
        print("Adding remaining Stage E columns to indicators table...")

        for column in missing_columns:
            try:
                # Add column with DOUBLE PRECISION type
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

        print("\nRemaining Stage E migration completed!")


if __name__ == "__main__":
    main()
