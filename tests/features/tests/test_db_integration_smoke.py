import os

import pandas as pd
import pytest
from sqlalchemy import text

from src.database import get_async_session
from src.features.core import compute_features
from src.features.infrastructure.database import (
    ensure_columns_exist,
    fetch_ohlcv_df,
    insert_indicators,
)
from src.features.infrastructure.indicator_registry import AVAILABLE_INDICATORS

pytestmark = pytest.mark.asyncio


async def test_features_pipeline_smoke_btc_1d():
    """Smoke-проверка: читаем OHLCV из swap_ohlcv_p, считаем фичи и сохраняем 1 строку в indicators."""
    if not (os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN")):
        pytest.skip("DATABASE_URL is not set")

    symbol = "BTC-USDT-SWAP"
    timeframe = "1D"

    async for session in get_async_session():
        # 1) Берем историю (достаточно для индикаторов)
        df = await fetch_ohlcv_df(session, symbol, timeframe, since_ts=None, limit=200)
        if df is None or len(df) < 50:
            pytest.skip("Not enough OHLCV data in swap_ohlcv_p/ohlcv for BTC 1D")

        # 2) Считаем ограниченный набор индикаторов
        # Считаем базовый набор (если нет в реестре, возьмем все доступные)
        requested = {"sma_20", "ema_12", "rsi_14", "macd", "atr_14", "obv"}
        available = set(AVAILABLE_INDICATORS)
        to_calc = requested & available
        features = compute_features(
            df,
            available=to_calc if to_calc else available,
            volatility_normalize=False,
        )
        assert len(features) == len(df)

        # 3) Берем последнюю строку для записи
        last_row_ts = int(features["ts"].iloc[-1])
        one_row = features.tail(1)

        # 4) Гарантируем наличие колонок и пишем
        indicator_columns = [
            c
            for c in one_row.columns
            if c not in ("open", "high", "low", "close", "volume", "ts")
        ]
        await ensure_columns_exist(session, "indicators", indicator_columns)
        n = await insert_indicators(session, one_row, symbol, timeframe)
        assert n == 1

        # 5) Проверяем, что запись появилась
        # Определим индикаторные колонки с ненулевыми значениями на последнем баре
        non_null_cols = [c for c in indicator_columns if pd.notna(one_row[c].iloc[0])]
        assert non_null_cols, "No non-null indicators on the last row"

        # Проверим первую ненулевую колонку в БД
        check_col = non_null_cols[0]
        q = await session.execute(
            text(
                f"SELECT {check_col} FROM indicators WHERE symbol=:s AND timeframe=:t AND timestamp=:ts"
            ),
            {"s": symbol, "t": timeframe, "ts": last_row_ts * 1000},
        )
        row = q.first()
        assert (
            row is not None and row[0] is not None
        ), f"Column {check_col} is NULL in DB for last row"

        break


@pytest.mark.integration
async def test_upsert_full_pipeline_with_validation():
    """
    Расширенный smoke-тест: полный пайплайн до insert_indicators с валидацией типов.

    Проверяет:
    1. Загрузку OHLCV данных
    2. Расчёт индикаторов
    3. Валидацию типов перед UPSERT
    4. Успешное выполнение UPSERT без ошибок типов
    """
    if not (os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN")):
        pytest.skip("DATABASE_URL is not set")

    symbol = "BTC-USDT-SWAP"
    timeframe = "1m"
    limit = 10  # Небольшой набор для быстрого теста

    async for session in get_async_session():
        try:
            # 1. Загружаем OHLCV данные
            from sqlalchemy import text

            query = text(
                """
                SELECT open, high, low, close, volume, timestamp
                FROM swap_ohlcv_p
                WHERE symbol = :symbol AND timeframe = :timeframe
                ORDER BY timestamp DESC
                LIMIT :limit
            """
            )
            result = await session.execute(
                query, {"symbol": symbol, "timeframe": timeframe, "limit": limit}
            )
            rows = result.fetchall()

            if not rows:
                pytest.skip(f"No OHLCV data for {symbol} {timeframe}")

            # Преобразуем в DataFrame
            df_ohlcv = pd.DataFrame(
                [
                    {
                        "open": float(row.open),
                        "high": float(row.high),
                        "low": float(row.low),
                        "close": float(row.close),
                        "volume": float(row.volume),
                        "timestamp": row.timestamp,
                    }
                    for row in reversed(rows)
                ]
            )

            assert len(df_ohlcv) > 0, "No OHLCV data loaded"

            # 2. Вычисляем индикаторы
            features_df = compute_features(df_ohlcv, specs=None)
            assert (
                features_df is not None and len(features_df) > 0
            ), "No features computed"

            # 3. Вставка через новый inserter API
            from src.features.infrastructure.persistence.inserter import (
                insert_indicators,
            )
            from src.features.infrastructure.persistence.schema_checker import (
                reflect_indicators_table,
            )

            await reflect_indicators_table(session)
            saved_count = await insert_indicators(
                session=session,
                ind_df=features_df,
                symbol=symbol,
                timeframe=timeframe,
            )

            # 4. Проверяем, что данные сохранились
            assert saved_count > 0, f"Expected saved_count > 0, got {saved_count}"

            # 5. Проверяем, что нет ошибок типов в БД
            # Выбираем одну запись и проверяем типы критических полей
            check_query = text(
                """
                SELECT ultosc, stochrsi_k, cdl_doji, willr, rsi_14
                FROM indicators
                WHERE symbol = :symbol AND timeframe = :timeframe
                ORDER BY timestamp DESC
                LIMIT 1
            """
            )
            check_result = await session.execute(
                check_query, {"symbol": symbol, "timeframe": timeframe}
            )
            check_row = check_result.first()

            if check_row:
                # Проверяем, что значения не NULL (если они были вычислены)
                # и что они имеют правильные типы (не строки)
                # PostgreSQL возвращает Decimal для NUMERIC колонок
                from decimal import Decimal

                for i, col_name in enumerate(
                    ["ultosc", "stochrsi_k", "cdl_doji", "willr", "rsi_14"]
                ):
                    val = check_row[i]
                    if val is not None:
                        assert isinstance(
                            val, int | float | Decimal
                        ), f"Column {col_name} has wrong type: {type(val)}"

            break
        except Exception as e:
            import traceback

            print(f"Test failed with error: {e}")
            print(f"Full traceback:\n{traceback.format_exc()}")
            raise
