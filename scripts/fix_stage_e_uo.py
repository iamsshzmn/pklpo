#!/usr/bin/env python3
"""
Fix missing 'uo' column in Stage E.
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

    with eng.begin() as c:
        print("Adding missing 'uo' column to indicators table...")

        try:
            # Add column with DOUBLE PRECISION type
            alter_sql = "ALTER TABLE indicators ADD COLUMN uo DOUBLE PRECISION"
            c.execute(text(alter_sql))
            print("[OK] Added column: uo")
        except Exception as e:
            if "already exists" in str(e) or "duplicate column" in str(e):
                print("[WARN] Column uo already exists")
            else:
                print(f"[ERROR] Error adding column uo: {e}")

        print("\nStage E fix completed!")


if __name__ == "__main__":
    main()
