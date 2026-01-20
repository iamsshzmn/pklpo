#!/usr/bin/env python3
"""
Check data statistics after DAG run.
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
        # Check total rows
        total = c.execute(text("SELECT COUNT(*) FROM indicators")).scalar()
        print(f"Total rows in indicators: {total}")

        # Check recent data (last 24 hours)
        recent = c.execute(
            text(
                "SELECT COUNT(*) FROM indicators WHERE calculated_at >= NOW() - INTERVAL '24 hours'"
            )
        ).scalar()
        print(f"Rows calculated in last 24h: {recent}")

        # Check some Stage A features
        stage_a_features = ["stochrsi_k", "hl2", "median_20", "log_return"]
        print("\nStage A features data check:")
        for feature in stage_a_features:
            count = c.execute(
                text(f"SELECT COUNT(*) FROM indicators WHERE {feature} IS NOT NULL")
            ).scalar()
            print(f"{feature}: {count} non-null values")

        # Check some Stage B features
        stage_b_features = ["aroon_14", "cci_14", "psar", "trix_14"]
        print("\nStage B features data check:")
        for feature in stage_b_features:
            count = c.execute(
                text(f"SELECT COUNT(*) FROM indicators WHERE {feature} IS NOT NULL")
            ).scalar()
            print(f"{feature}: {count} non-null values")


if __name__ == "__main__":
    main()
