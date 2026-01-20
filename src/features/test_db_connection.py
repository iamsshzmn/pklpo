"""
Скрипт для проверки подключения к базе данных.

Использование:
    python -m src.features.test_db_connection
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

from src.utils.session_utils import get_db_session


async def test_connection() -> bool:
    """Проверить подключение к базе данных."""
    try:
        print("[INFO] Попытка подключения к БД...")
        print("[INFO] Проверка переменных окружения...")

        from src.config.env_validator import check_required_env_vars, get_database_url

        missing_vars = check_required_env_vars()
        if missing_vars:
            print(
                f"[ERROR] Отсутствуют переменные окружения: {', '.join(missing_vars)}"
            )
            return False

        db_url = get_database_url()
        if db_url:
            # Маскируем пароль в URL для вывода
            safe_url = db_url.split("@")[-1] if "@" in db_url else db_url[:50]
            print(f"[INFO] DB URL: ...@{safe_url}")
        else:
            print("[ERROR] Не удалось получить DB URL")
            return False

        async with get_db_session() as session:
            # Простой запрос для проверки подключения
            result = await session.execute(text("SELECT 1 as test"))
            test_value = result.scalar()
            print(f"[OK] Подключение к БД успешно: test = {test_value}")

            # Проверяем наличие таблиц
            result = await session.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name IN ('swap_ohlcv_p', 'indicators')
                    ORDER BY table_name
                """
                )
            )
            tables = [row[0] for row in result.fetchall()]
            print(f"[OK] Найдено таблиц: {', '.join(tables) if tables else 'нет'}")

            # Проверяем наличие данных в swap_ohlcv_p
            if "swap_ohlcv_p" in tables:
                result = await session.execute(
                    text(
                        """
                        SELECT COUNT(*) as cnt,
                               COUNT(DISTINCT symbol) as symbols,
                               COUNT(DISTINCT timeframe) as timeframes
                        FROM swap_ohlcv_p
                    """
                    )
                )
                row = result.fetchone()
                if row:
                    print(
                        f"[OK] swap_ohlcv_p: {row[0]} строк, "
                        f"{row[1]} символов, {row[2]} таймфреймов"
                    )

            # Проверяем наличие данных в indicators
            if "indicators" in tables:
                result = await session.execute(
                    text(
                        """
                        SELECT COUNT(*) as cnt
                        FROM indicators
                    """
                    )
                )
                row = result.fetchone()
                if row:
                    print(f"[OK] indicators: {row[0]} строк")

            return True

    except Exception as e:
        print(f"[ERROR] Ошибка подключения к БД: {e}")
        import traceback

        print(f"Traceback:\n{traceback.format_exc()}")
        return False


async def test_ohlcv_query(
    symbol: str = "BTC-USDT-SWAP", timeframe: str = "1m"
) -> bool:
    """Проверить запрос OHLCV данных."""
    try:
        async with get_db_session() as session:
            query = text(
                """
                SELECT COUNT(*) as cnt
                FROM swap_ohlcv_p
                WHERE symbol = :symbol AND timeframe = :timeframe
            """
            )
            result = await session.execute(
                query, {"symbol": symbol, "timeframe": timeframe}
            )
            row = result.fetchone()
            if row:
                count = row[0]
                print(f"[OK] Данные для {symbol} {timeframe}: {count} строк")
                return count > 0
            return False

    except Exception as e:
        print(f"[ERROR] Ошибка запроса OHLCV: {e}")
        return False


async def main():
    """Основная функция проверки."""
    print("=" * 60)
    print("Проверка подключения к базе данных")
    print("=" * 60)

    # Проверка базового подключения
    print("\n1. Проверка подключения...")
    connection_ok = await test_connection()

    if not connection_ok:
        print("\n[ERROR] Не удалось подключиться к базе данных")
        print("\nПроверьте:")
        print("  - Запущен ли PostgreSQL")
        print("  - Правильность настроек в .env файле")
        print("  - Доступность хоста и порта")
        return 1

    # Проверка наличия данных
    print("\n2. Проверка наличия данных...")
    data_ok = await test_ohlcv_query()

    if not data_ok:
        print("\n[WARNING] Данные для BTC-USDT-SWAP 1m не найдены")
        print("   Это нормально, если данные ещё не загружены")

    print("\n" + "=" * 60)
    print("[OK] Проверка завершена")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
