"""
Утилиты для оптимизации запросов к базе данных
"""

import logging
from collections import defaultdict
from datetime import UTC

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def get_symbols_timeframes_optimized(
    session: AsyncSession, symbol: str | None = None, min_records: int = 100
) -> dict[str, list[str]]:
    """
    Получает символы и таймфреймы за один запрос с оптимизацией.

    Args:
        session: Сессия БД
        symbol: Конкретный символ (если None, обрабатываются все)
        min_records: Минимальное количество записей для символа

    Returns:
        dict: {symbol: [timeframes]}
    """
    try:
        if symbol:
            # Для конкретного символа
            query = text(
                """
                SELECT DISTINCT symbol, timeframe, COUNT(*) as record_count
                FROM indicators
                WHERE symbol = :symbol
                GROUP BY symbol, timeframe
                HAVING COUNT(*) >= :min_records
                ORDER BY symbol, timeframe
            """
            )
            result = await session.execute(
                query, {"symbol": symbol, "min_records": min_records}
            )
        else:
            # Для всех символов с фильтром по количеству записей
            query = text(
                """
                SELECT DISTINCT symbol, timeframe, COUNT(*) as record_count
                FROM indicators
                GROUP BY symbol, timeframe
                HAVING COUNT(*) >= :min_records
                ORDER BY symbol, timeframe
            """
            )
            result = await session.execute(query, {"min_records": min_records})

        mapping = defaultdict(list)
        total_symbols = 0
        total_timeframes = 0

        for row in result.fetchall():
            mapping[row[0]].append(row[1])
            total_timeframes += 1

        total_symbols = len(mapping)

        logger.info(
            f"📊 Найдено {total_symbols} символов с {total_timeframes} таймфреймами (мин. {min_records} записей)"
        )

        return dict(mapping)

    except Exception as e:
        logger.error(
            f"❌ Ошибка при получении символов/таймфреймов: {e}", exc_info=True
        )
        return {}


async def get_recent_symbols_timeframes(
    session: AsyncSession, symbol: str | None = None, hours_back: int = 24
) -> dict[str, list[str]]:
    """
    Получает символы и таймфреймы с данными за последние N часов.

    Args:
        session: Сессия БД
        symbol: Конкретный символ (если None, обрабатываются все)
        hours_back: Количество часов назад для фильтрации

    Returns:
        dict: {symbol: [timeframes]}
    """
    try:
        if symbol:
            query = text(
                """
                SELECT DISTINCT symbol, timeframe
                FROM indicators
                WHERE symbol = :symbol
                AND ts >= EXTRACT(EPOCH FROM NOW() - INTERVAL ':hours_back hours')
                ORDER BY symbol, timeframe
            """
            )
            result = await session.execute(
                query, {"symbol": symbol, "hours_back": hours_back}
            )
        else:
            query = text(
                """
                SELECT DISTINCT symbol, timeframe
                FROM indicators
                WHERE ts >= EXTRACT(EPOCH FROM NOW() - INTERVAL ':hours_back hours')
                ORDER BY symbol, timeframe
            """
            )
            result = await session.execute(query, {"hours_back": hours_back})

        mapping = defaultdict(list)
        for row in result.fetchall():
            mapping[row[0]].append(row[1])

        total_symbols = len(mapping)
        total_timeframes = sum(len(tfs) for tfs in mapping.values())

        logger.info(
            f"📊 Найдено {total_symbols} символов с {total_timeframes} таймфреймами за последние {hours_back}ч"
        )

        return dict(mapping)

    except Exception as e:
        logger.error(
            f"❌ Ошибка при получении недавних символов/таймфреймов: {e}", exc_info=True
        )
        return {}


async def validate_data_availability(
    session: AsyncSession, symbol: str | None = None, timeframe: str | None = None
) -> dict[str, any]:
    """
    Валидирует доступность данных для обработки.

    Args:
        session: Сессия БД
        symbol: Символ для проверки
        timeframe: Таймфрейм для проверки

    Returns:
        dict: Результат валидации
    """
    try:
        validation_result = {
            "is_valid": False,
            "symbols_count": 0,
            "timeframes_count": 0,
            "total_records": 0,
            "latest_timestamp": None,
            "missing_data": [],
            "warnings": [],
        }

        # Проверяем наличие данных в таблице indicators
        if symbol and timeframe:
            # Конкретный символ и таймфрейм
            query = text(
                """
                SELECT COUNT(*) as count, MAX(ts) as latest_ts
                FROM indicators
                WHERE symbol = :symbol AND timeframe = :timeframe
            """
            )
            result = await session.execute(
                query, {"symbol": symbol, "timeframe": timeframe}
            )
            row = result.fetchone()

            if row and row[0] > 0:
                validation_result.update(
                    {
                        "is_valid": True,
                        "symbols_count": 1,
                        "timeframes_count": 1,
                        "total_records": row[0],
                        "latest_timestamp": row[1],
                    }
                )
            else:
                validation_result["missing_data"].append(
                    f"Нет данных для {symbol} {timeframe}"
                )

        elif symbol:
            # Конкретный символ, все таймфреймы
            query = text(
                """
                SELECT timeframe, COUNT(*) as count, MAX(ts) as latest_ts
                FROM indicators
                WHERE symbol = :symbol
                GROUP BY timeframe
                ORDER BY timeframe
            """
            )
            result = await session.execute(query, {"symbol": symbol})
            rows = result.fetchall()

            if rows:
                validation_result.update(
                    {
                        "is_valid": True,
                        "symbols_count": 1,
                        "timeframes_count": len(rows),
                        "total_records": sum(row[1] for row in rows),
                        "latest_timestamp": max(row[2] for row in rows if row[2]),
                    }
                )
            else:
                validation_result["missing_data"].append(
                    f"Нет данных для символа {symbol}"
                )

        else:
            # Все символы и таймфреймы
            query = text(
                """
                SELECT COUNT(DISTINCT symbol) as symbols_count,
                       COUNT(DISTINCT timeframe) as timeframes_count,
                       COUNT(*) as total_records,
                       MAX(ts) as latest_ts
                FROM indicators
            """
            )
            result = await session.execute(query)
            row = result.fetchone()

            if row and row[2] > 0:
                validation_result.update(
                    {
                        "is_valid": True,
                        "symbols_count": row[0],
                        "timeframes_count": row[1],
                        "total_records": row[2],
                        "latest_timestamp": row[3],
                    }
                )
            else:
                validation_result["missing_data"].append(
                    "Нет данных в таблице indicators"
                )

        # Проверяем свежесть данных
        if validation_result["latest_timestamp"]:
            from datetime import datetime

            latest_dt = datetime.fromtimestamp(
                validation_result["latest_timestamp"], tz=UTC
            )
            now_dt = datetime.now(UTC)
            age_hours = (now_dt - latest_dt).total_seconds() / 3600

            if age_hours > 24:
                validation_result["warnings"].append(
                    f"Данные устарели на {age_hours:.1f} часов"
                )
            elif age_hours > 1:
                validation_result["warnings"].append(
                    f"Данные не очень свежие: {age_hours:.1f} часов"
                )

        return validation_result

    except Exception as e:
        # При ошибке делаем rollback транзакции
        try:
            await session.rollback()
        except:
            pass  # Игнорируем ошибки rollback

        logger.error(f"❌ Ошибка при валидации данных: {e}", exc_info=True)
        return {
            "is_valid": False,
            "error": str(e),
            "symbols_count": 0,
            "timeframes_count": 0,
            "total_records": 0,
            "latest_timestamp": None,
            "missing_data": [f"Ошибка валидации: {e}"],
            "warnings": [],
        }


async def get_processing_stats(
    session: AsyncSession, symbol: str | None = None
) -> dict[str, any]:
    """
    Получает статистику для планирования обработки.

    Args:
        session: Сессия БД
        symbol: Символ для статистики

    Returns:
        dict: Статистика обработки
    """
    try:
        if symbol:
            query = text(
                """
                SELECT
                    timeframe,
                    COUNT(*) as records_count,
                    MIN(ts) as earliest_ts,
                    MAX(ts) as latest_ts,
                    COUNT(DISTINCT DATE(to_timestamp(ts))) as days_count
                FROM indicators
                WHERE symbol = :symbol
                GROUP BY timeframe
                ORDER BY timeframe
            """
            )
            result = await session.execute(query, {"symbol": symbol})
        else:
            query = text(
                """
                SELECT
                    symbol,
                    timeframe,
                    COUNT(*) as records_count,
                    MIN(ts) as earliest_ts,
                    MAX(ts) as latest_ts,
                    COUNT(DISTINCT DATE(to_timestamp(ts))) as days_count
                FROM indicators
                GROUP BY symbol, timeframe
                ORDER BY symbol, timeframe
            """
            )
            result = await session.execute(query)

        rows = result.fetchall()

        stats = {
            "total_symbols": len({row[0] for row in rows}) if not symbol else 1,
            "total_timeframes": len({row[1] if not symbol else row[0] for row in rows}),
            "total_records": sum(row[2] if not symbol else row[1] for row in rows),
            "timeframes_detail": {},
        }

        for row in rows:
            if symbol:
                tf, records, earliest, latest, days = row
                stats["timeframes_detail"][tf] = {
                    "records_count": records,
                    "earliest_ts": earliest,
                    "latest_ts": latest,
                    "days_count": days,
                }
            else:
                sym, tf, records, earliest, latest, days = row
                if sym not in stats["timeframes_detail"]:
                    stats["timeframes_detail"][sym] = {}
                stats["timeframes_detail"][sym][tf] = {
                    "records_count": records,
                    "earliest_ts": earliest,
                    "latest_ts": latest,
                    "days_count": days,
                }

        return stats

    except Exception as e:
        logger.error(f"❌ Ошибка при получении статистики: {e}", exc_info=True)
        return {
            "error": str(e),
            "total_symbols": 0,
            "total_timeframes": 0,
            "total_records": 0,
            "timeframes_detail": {},
        }
