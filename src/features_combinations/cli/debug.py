#!/usr/bin/env python3
"""
Debug-скрипт для просмотра indicators и combination_features.

Выводит рядом indicators и combination_features для нескольких таймстемпов,
печатает содержимое features как dict с сортировкой по ключам.
"""

import argparse
import asyncio
import sys
from datetime import datetime

from sqlalchemy import text

from src.models import INDICATORS_TABLE_NAME
from src.utils.session_utils import get_db_session

from ..infrastructure.repository import PostgresCombinationRepository
from ..logging_config import get_combinations_logger, setup_combinations_logging

logger = get_combinations_logger("debug")


async def debug_combinations(
    symbol: str,
    timeframe: str,
    limit: int = 5,
    combination_id: str | None = None,
) -> None:
    """
    Вывести indicators и combination_features рядом для отладки.

    Args:
        symbol: Символ инструмента
        timeframe: Таймфрейм
        limit: Количество последних записей
        combination_id: Конкретная комбинация (если None, показываем все)
    """
    async with get_db_session() as session:
        # Загружаем indicators
        indicators_query = text(
            f"""
            SELECT timestamp, rsi14, macd, macd_signal, macd_histogram,
                   ema_12, ema_26, adx14, stoch_k, stoch_d, obv, cmf
            FROM {INDICATORS_TABLE_NAME}
            WHERE symbol = :symbol AND timeframe = :timeframe
            ORDER BY timestamp DESC
            LIMIT :limit
        """
        )

        result = await session.execute(
            indicators_query, {"symbol": symbol, "timeframe": timeframe, "limit": limit}
        )
        indicators_rows = result.fetchall()

        if not indicators_rows:
            logger.warning(f"No indicators found for {symbol}/{timeframe}")
            return

        # Загружаем combination_features
        repo = PostgresCombinationRepository(session)
        latest = await repo.load_latest(symbol, timeframe, limit=limit * 10)

        # Фильтруем по combination_id если указан
        if combination_id:
            latest = [r for r in latest if r.combination_id == combination_id]

        # Группируем по timestamp
        combos_by_ts: dict[int, list] = {}
        for combo in latest:
            ts_ms = (
                int(combo.timestamp.timestamp() * 1000)
                if isinstance(combo.timestamp, datetime)
                else combo.timestamp
            )
            if ts_ms not in combos_by_ts:
                combos_by_ts[ts_ms] = []
            combos_by_ts[ts_ms].append(combo)

        # Выводим результаты
        print("\n" + "=" * 100)
        print(f"DEBUG: {symbol} / {timeframe}")
        print("=" * 100)

        for idx, ind_row in enumerate(indicators_rows, 1):
            ts_ms = ind_row[0]  # timestamp
            ts_dt = datetime.fromtimestamp(ts_ms / 1000.0)

            print(f"\n[{idx}] Timestamp: {ts_ms} ({ts_dt.isoformat()})")
            print("-" * 100)

            # Indicators
            print("INDICATORS:")
            ind_dict = dict(ind_row._mapping)
            for key, value in sorted(ind_dict.items()):
                if key != "timestamp" and value is not None:
                    print(f"  {key:20s} = {value:12.6f}")

            # Combination features
            combos = combos_by_ts.get(ts_ms, [])
            if combos:
                print(f"\nCOMBINATION FEATURES ({len(combos)} комбинаций):")
                for combo in combos:
                    print(f"\n  [{combo.combination_id}]")
                    # Сортируем features по ключам
                    sorted_features = dict(sorted(combo.features.items()))
                    for key, value in sorted_features.items():
                        print(f"    {key:25s} = {value:12.6f}")
            else:
                print("\nCOMBINATION FEATURES: нет данных")

        print("\n" + "=" * 100)


def main() -> None:
    """Главная функция debug-скрипта."""
    setup_combinations_logging(level="INFO")

    parser = argparse.ArgumentParser(
        description="Debug-скрипт для просмотра indicators и combination_features"
    )
    parser.add_argument(
        "--symbol", required=True, help="Символ (например, BTC-USDT-SWAP)"
    )
    parser.add_argument("--timeframe", required=True, help="Таймфрейм (например, 1m)")
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Количество последних записей (по умолчанию 5)",
    )
    parser.add_argument(
        "--combination-id",
        type=str,
        help="Конкретная комбинация (если не указано, показываем все)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(
            debug_combinations(
                symbol=args.symbol,
                timeframe=args.timeframe,
                limit=args.limit,
                combination_id=args.combination_id,
            )
        )
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
