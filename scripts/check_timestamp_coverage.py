"""Проверка покрытия timestamp по таймфреймам."""

import asyncio

from sqlalchemy import text

from src.utils.session_utils import get_db_session


async def check_timestamp():
    """Проверяет наличие данных для конкретного timestamp."""
    symbol = "BTC-USDT-SWAP"
    timestamp = 1763510400000
    timeframes = ["1m", "5m", "15m", "30m", "1H", "4H", "12H", "1D", "1W", "1M"]

    async with get_db_session() as session:
        print(f"\nChecking data for timestamp {timestamp} ({symbol})\n")
        print("=" * 100)
        print(
            f"{'Timeframe':<10} | {'OHLCV':<10} | {'Indicators':<12} | {'OHLCV ts':<20} | {'Indicators ts':<20}"
        )
        print("=" * 100)

        for tf in timeframes:
            # Проверяем OHLCV
            ohlcv_query = text(
                """
                SELECT timestamp, open, high, low, close, volume
                FROM swap_ohlcv_p
                WHERE symbol = :symbol
                  AND timeframe = :timeframe
                  AND timestamp = :timestamp
            """
            )
            ohlcv_result = await session.execute(
                ohlcv_query, {"symbol": symbol, "timeframe": tf, "timestamp": timestamp}
            )
            ohlcv_row = ohlcv_result.fetchone()

            # Проверяем Indicators
            ind_query = text(
                """
                SELECT timestamp, calculated_at,
                       COUNT(*) FILTER (WHERE obv IS NOT NULL) as obv_count,
                       COUNT(*) FILTER (WHERE rsi_14 IS NOT NULL) as rsi_count,
                       COUNT(*) FILTER (WHERE ema_8 IS NOT NULL) as ema_count
                FROM indicators
                WHERE symbol = :symbol
                  AND timeframe = :timeframe
                  AND timestamp = :timestamp
                GROUP BY timestamp, calculated_at
            """
            )
            ind_result = await session.execute(
                ind_query, {"symbol": symbol, "timeframe": tf, "timestamp": timestamp}
            )
            ind_row = ind_result.fetchone()

            ohlcv_status = "[OK] Yes" if ohlcv_row else "[NO] No"
            ind_status = "[OK] Yes" if ind_row else "[NO] No"
            ohlcv_ts = str(ohlcv_row.timestamp) if ohlcv_row else "-"
            ind_ts = str(ind_row.timestamp) if ind_row else "-"

            print(
                f"{tf:<10} | {ohlcv_status:<10} | {ind_status:<12} | "
                f"{ohlcv_ts:<20} | {ind_ts:<20}"
            )

            # Дополнительная диагностика для отсутствующих
            if not ohlcv_row:
                # Проверяем ближайшие timestamp
                nearby_query = text(
                    """
                    SELECT timestamp, ABS(timestamp - :target_ts) as diff
                    FROM swap_ohlcv_p
                    WHERE symbol = :symbol
                      AND timeframe = :timeframe
                    ORDER BY ABS(timestamp - :target_ts)
                    LIMIT 3
                """
                )
                nearby_result = await session.execute(
                    nearby_query,
                    {
                        "symbol": symbol,
                        "timeframe": tf,
                        "target_ts": timestamp,
                    },
                )
                nearby_rows = nearby_result.fetchall()
                if nearby_rows:
                    print(
                        f"  -> Nearest timestamps: "
                        f"{', '.join([str(r.timestamp) for r in nearby_rows])}"
                    )

        print("=" * 100)

        # Check timestamp range for each timeframe
        print("\nTimestamp range by timeframe:\n")
        print(f"{'Timeframe':<10} | {'Min timestamp':<20} | {'Max timestamp':<20}")
        print("-" * 60)

        for tf in timeframes:
            range_query = text(
                """
                SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts
                FROM swap_ohlcv_p
                WHERE symbol = :symbol AND timeframe = :timeframe
            """
            )
            range_result = await session.execute(
                range_query, {"symbol": symbol, "timeframe": tf}
            )
            range_row = range_result.fetchone()

            if range_row and range_row.min_ts:
                in_range = range_row.min_ts <= timestamp <= range_row.max_ts
                status = "[OK]" if in_range else "[NO]"
                print(
                    f"{tf:<10} | {range_row.min_ts:<20} | {range_row.max_ts:<20} {status}"
                )
            else:
                print(f"{tf:<10} | {'-':<20} | {'-':<20}")


if __name__ == "__main__":
    asyncio.run(check_timestamp())
