#!/usr/bin/env python3
"""
Check all stages (A, B, C, D, E) and identify missing columns in indicators table.
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
        # Get current columns
        result = c.execute(
            text(
                """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'indicators'
            ORDER BY column_name
        """
            )
        )
        existing_columns = {row[0] for row in result.fetchall()}

        print("Current columns in indicators table:")
        for col in sorted(existing_columns):
            print(f"  {col}")

        # Define all stages
        stages = {
            "Stage A - Overlap/Stats/Performance": [
                "stochrsi_k",
                "stochrsi_d",
                "ttm_squeeze_on",
                "ttm_squeeze_value",
                "ttm_squeeze_hist",
                "hl2",
                "hlc3",
                "ohlc4",
                "wcp",
                "midpoint",
                "midprice",
                "median_20",
                "mad_20",
                "stdev_20",
                "variance_20",
                "skew_20",
                "kurtosis_20",
                "zscore_20",
                "log_return",
                "percent_return",
                "trend_return_20",
                "drawdown",
            ],
            "Stage B - Trend": [
                "adx_14",
                "adx_neg_di",
                "adx_pos_di",
                "aroon_14",
                "aroon_down",
                "aroon_up",
                "cci_14",
                "dpo_20",
                "ema_13",
                "ema_21",
                "ema_34",
                "ema_55",
                "ema_89",
                "ema_144",
                "ema_233",
                "ichimoku_a",
                "ichimoku_b",
                "ichimoku_chikou",
                "ichimoku_senkou_a",
                "ichimoku_senkou_b",
                "kst",
                "macd",
                "macd_signal",
                "macd_histogram",
                "ppo",
                "ppo_signal",
                "ppo_histogram",
                "psar",
                "sma_20",
                "sma_50",
                "sma_200",
                "tema_20",
                "trix_14",
                "vortex_neg",
                "vortex_pos",
            ],
            "Stage C - Oscillators": [
                "ao",
                "apo",
                "bias",
                "bop",
                "brar",
                "cfo",
                "cg",
                "coppock",
                "er",
                "eri",
                "fisher",
                "inertia",
                "kdj_k",
                "kdj_d",
                "pgo",
                "psl",
                "pvo",
                "qqe",
                "rsx_14",
                "rvgi",
                "smi",
                "stoch_k",
                "stoch_d",
                "tsi",
                "uo",
                "williams_r",
            ],
            "Stage D - Volatility/Volume": [
                "aberration",
                "accbands_upper",
                "accbands_middle",
                "accbands_lower",
                "atr_14",
                "bb_upper",
                "bb_middle",
                "bb_lower",
                "bb_width",
                "bb_percent",
                "dc_upper",
                "dc_middle",
                "dc_lower",
                "kc_upper",
                "kc_middle",
                "kc_lower",
                "massi",
                "natr_14",
                "pdist",
                "rvi",
                "ui",
                "efi",
                "eom",
                "nvi",
                "pvi",
                "pvt",
                "obv",
                "vwap",
            ],
            "Stage E - Momentum/Trend": [
                "amat",
                "chop",
                "decay",
                "decreasing",
                "dpo",
                "increasing",
                "long_run",
                "short_run",
                "slope_20",
                "tsi",
                "uo",
                "ultimate_osc",
            ],
        }

        print(f"\n{'='*60}")
        print("STAGE ANALYSIS")
        print(f"{'='*60}")

        total_missing = 0
        for stage_name, features in stages.items():
            missing = [f for f in features if f not in existing_columns]
            present = [f for f in features if f in existing_columns]

            print(f"\n{stage_name}:")
            print(f"  Total features: {len(features)}")
            print(f"  Present: {len(present)}")
            print(f"  Missing: {len(missing)}")

            if missing:
                print("  Missing columns:")
                for col in missing:
                    print(f"    - {col}")
            else:
                print("  [OK] All columns present!")

            total_missing += len(missing)

        print(f"\n{'='*60}")
        print(f"SUMMARY: {total_missing} missing columns across all stages")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
