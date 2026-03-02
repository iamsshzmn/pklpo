"""
Функции для работы с базой данных.
"""

import pandas as pd
from sqlalchemy import func, select, text

from src.models import OHLCV, Indicator


async def fetch_latest_ts(session, symbol: str, timeframe: str) -> int | None:
    """Вернуть последний timestamp в СЕКУНДАХ из таблицы indicators.

    В модели Indicator поле называется `timestamp` и хранится в миллисекундах.
    Здесь нормализуем к секундам для совместимости с остальным кодом.
    """
    q = (
        select(func.max(Indicator.timestamp))
        .where(Indicator.symbol == symbol)
        .where(Indicator.timeframe == timeframe)
    )
    res = await session.execute(q)
    latest_ms = res.scalar_one_or_none()
    return (latest_ms // 1000) if latest_ms else None


async def ensure_columns_exist(session, table: str, columns: list[str]) -> None:
    from src.db.db_schema_utils import ensure_columns  # локальный импорт, как раньше

    await ensure_columns(session, table, columns)


async def get_symbol_timeframes_to_update(session):
    """Получить пары (symbol, timeframe), для которых есть новые OHLCV-данные."""
    subq = (
        select(
            Indicator.symbol,
            Indicator.timeframe,
            func.max(Indicator.timestamp).label("max_ts_ms"),
        )
        .group_by(Indicator.symbol, Indicator.timeframe)
        .subquery()
    )

    q = (
        select(OHLCV.symbol, OHLCV.timeframe)
        .outerjoin(
            subq,
            (OHLCV.symbol == subq.c.symbol) & (OHLCV.timeframe == subq.c.timeframe),
        )
        .where(OHLCV.ts > func.coalesce(subq.c.max_ts_ms, 0))  # оба в мс
        .group_by(OHLCV.symbol, OHLCV.timeframe)
    )
    result = await session.execute(q)
    return result.all()


async def fetch_ohlcv_df(
    session, symbol: str, timeframe: str, since_ts: int | None = None, limit: int = 200
) -> pd.DataFrame | None:
    """Получить OHLCV для символа/таймфрейма с учетом since_ts (секунды)."""
    # 1) Основной источник: таблица ohlcv (ts в миллисекундах)
    q = (
        select(OHLCV)
        .where(OHLCV.symbol == symbol, OHLCV.timeframe == timeframe)
        .order_by(OHLCV.ts.desc())
    )
    if since_ts:
        # since_ts в секундах, ohlcv.ts в миллисекундах
        q = q.where(OHLCV.ts > since_ts * 1000)
    q = q.limit(limit)
    result = await session.execute(q)
    rows = result.scalars().all()
    if rows:
        df = pd.DataFrame(
            [
                {
                    "ts": r.ts // 1000,  # конвертируем миллисекунды в секунды
                    "open": float(r.open),
                    "high": float(r.high),
                    "low": float(r.low),
                    "close": float(r.close),
                    "volume": float(r.volume),
                }
                for r in reversed(rows)
            ]
        )

        df.name = symbol
        df.timeframe = timeframe
        return df

    # 2) Фоллбек: таблица swap_ohlcv_p (timestamp в миллисекундах)
    try:
        # Формируем запрос вручную, учитывая имена столбцов (LIMIT как литерал для совместимости)
        base_sql = (
            "SELECT symbol, timeframe, timestamp, open, high, low, close, volume "
            "FROM swap_ohlcv_p WHERE symbol=:symbol AND timeframe=:timeframe "
        )
        params = {"symbol": symbol, "timeframe": timeframe}
        if since_ts:
            base_sql += "AND timestamp > :since_ms "
            params["since_ms"] = since_ts * 1000  # INT, не строка!
        base_sql += f"ORDER BY timestamp DESC LIMIT {int(limit)}"

        res = await session.execute(text(base_sql), params)
        rows2 = res.fetchall()
        if not rows2:
            return None

        df2 = pd.DataFrame(
            [
                {
                    "ts": int(r[2]) // 1000,
                    "open": float(r[3]),
                    "high": float(r[4]),
                    "low": float(r[5]),
                    "close": float(r[6]),
                    "volume": float(r[7]) if r[7] is not None else 0.0,
                }
                for r in reversed(rows2)
            ]
        )
        df2.name = symbol
        df2.timeframe = timeframe
        return df2
    except Exception:
        return None
