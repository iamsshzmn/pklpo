#!/usr/bin/env python3
"""
Проверка null значений в таблице indicators.
Анализ проблемных индикаторов: hlc3, hl2, ohlc4 и других.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Проблемные индикаторы для проверки
PROBLEMATIC_INDICATORS = [
    "hlc3",
    "hl2",
    "ohlc4",
    "aberration",
    "accbands_lower",
    "accbands_middle",
    "accbands_upper",
    "aroon_14",
    "chop",
    "decay",
    "dpo",
    "dpo_20",
    "efi",
    "eom",
    "kst",
    "mom_10",
]


async def check_null_indicators(database_url: str) -> None:
    """Проверить null значения для проблемных индикаторов."""
    print("=" * 70)
    print("ПРОВЕРКА NULL ЗНАЧЕНИЙ В ТАБЛИЦЕ indicators")
    print("=" * 70)

    engine = create_async_engine(database_url, future=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Проверить наличие колонок
        result = await session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'indicators'
                ORDER BY column_name;
                """
            )
        )
        existing_columns = {row[0] for row in result.fetchall()}

        print(f"\nВсего колонок в БД: {len(existing_columns)}")

        # Проверить null значения для каждой проблемной колонки
        print("\n" + "=" * 70)
        print("АНАЛИЗ NULL ЗНАЧЕНИЙ:")
        print("-" * 70)

        for indicator in PROBLEMATIC_INDICATORS:
            if indicator not in existing_columns:
                print(f"\n[{indicator}]: КОЛОНКА ОТСУТСТВУЕТ В БД")
                continue

            # Подсчитать null и non-null
            result = await session.execute(
                text(
                    f"""
                    SELECT
                        COUNT(*) as total,
                        COUNT({indicator}) as non_null,
                        COUNT(*) - COUNT({indicator}) as null_count
                    FROM public.indicators
                    WHERE timestamp >= EXTRACT(EPOCH FROM NOW() - INTERVAL '24 hours') * 1000;
                    """
                )
            )
            row = result.fetchone()
            total, non_null, null_count = row

            if total == 0:
                print(f"\n[{indicator}]: Нет данных за последние 24 часа")
                continue

            fill_rate = (non_null / total * 100) if total > 0 else 0

            print(f"\n[{indicator}]:")
            print(f"  Всего строк (24h): {total}")
            print(f"  Non-null: {non_null} ({fill_rate:.1f}%)")
            print(f"  Null: {null_count} ({100-fill_rate:.1f}%)")

            # Если есть non-null, показать примеры
            if non_null > 0:
                result = await session.execute(
                    text(
                        f"""
                        SELECT {indicator}, timestamp
                        FROM public.indicators
                        WHERE {indicator} IS NOT NULL
                        AND timestamp >= EXTRACT(EPOCH FROM NOW() - INTERVAL '24 hours') * 1000
                        ORDER BY timestamp DESC
                        LIMIT 3;
                        """
                    )
                )
                samples = result.fetchall()
                print("  Примеры значений (последние 3):")
                for val, ts in samples:
                    print(f"    - {val} (ts: {ts})")

        # Проверить последнюю запись (как в JSON)
        print("\n" + "=" * 70)
        print("ПОСЛЕДНЯЯ ЗАПИСЬ (для сравнения с JSON):")
        print("-" * 70)

        result = await session.execute(
            text(
                """
                SELECT
                    symbol, timeframe, timestamp,
                    hlc3, hl2, ohlc4,
                    bb_upper, bb_middle, bb_lower,
                    kc_upper, kc_middle, kc_lower,
                    ichimoku_senkou_a, ichimoku_senkou_b, ichimoku_tenkan, ichimoku_kijun
                FROM public.indicators
                ORDER BY timestamp DESC
                LIMIT 1;
                """
            )
        )
        row = result.fetchone()
        if row:
            print(f"\nSymbol: {row[0]}, Timeframe: {row[1]}, Timestamp: {row[2]}")
            print("\nOverlap индикаторы:")
            print(f"  hlc3: {row[3]}")
            print(f"  hl2: {row[4]}")
            print(f"  ohlc4: {row[5]}")
            print("\nVolatility индикаторы:")
            print(f"  bb_upper: {row[6]}")
            print(f"  bb_middle: {row[7]}")
            print(f"  bb_lower: {row[8]}")
            print(f"  kc_upper: {row[9]}")
            print(f"  kc_middle: {row[10]}")
            print(f"  kc_lower: {row[11]}")
            print("\nIchimoku индикаторы:")
            print(f"  ichimoku_senkou_a: {row[12]}")
            print(f"  ichimoku_senkou_b: {row[13]}")
            print(f"  ichimoku_tenkan: {row[14]}")
            print(f"  ichimoku_kijun: {row[15]}")

    await engine.dispose()
    print("\n" + "=" * 70)
    print("[SUCCESS] Проверка завершена")
    print("=" * 70)


def main() -> int:
    """Основная функция."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://pklpo_user:strongpassword@localhost:5432/pklpo",
    )

    asyncio.run(check_null_indicators(database_url))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
