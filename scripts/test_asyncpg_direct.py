"""Прямой тест подключения через asyncpg."""

import asyncio
import sys

# На Windows используем WindowsSelectorEventLoopPolicy для asyncpg
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv

load_dotenv()

from src.config.env_validator import get_database_url


async def test_direct_connection():
    """Тест прямого подключения через asyncpg."""
    from urllib.parse import urlparse

    import asyncpg

    db_url = get_database_url()
    print(
        f"[INFO] Тестирую подключение: {db_url.split('@')[-1] if '@' in db_url else db_url[:50]}"
    )

    # Парсим URL
    parsed = urlparse(db_url.replace("postgresql+asyncpg://", "postgresql://"))

    # Пробуем разные варианты подключения
    hosts_to_try = [
        ("127.0.0.1", "IPv4 localhost"),
        ("localhost", "localhost name"),
    ]

    # Пробуем разные варианты SSL
    ssl_options = [
        ("disable", "SSL отключен"),
        (False, "SSL = False"),
        ("prefer", "SSL prefer"),
    ]

    for host, desc in hosts_to_try:
        for ssl_val, ssl_desc in ssl_options:
            print(f"\n[INFO] Пробую {desc}: {host}, {ssl_desc}")
            try:
                # Двойной таймаут: внутренний asyncpg и внешний asyncio.wait_for
                conn = await asyncio.wait_for(
                    asyncpg.connect(
                        host=host,
                        port=parsed.port or 5432,
                        user=parsed.username,
                        password=parsed.password,
                        database=parsed.path.lstrip("/"),
                        ssl=ssl_val,
                        timeout=5,  # Таймаут asyncpg
                    ),
                    timeout=8.0,  # Внешний таймаут asyncio
                )
                print(f"[OK] Подключение успешно через {desc}, {ssl_desc}!")
                result = await conn.fetchval("SELECT 1")
                print(f"[OK] Запрос выполнен: {result}")
                await conn.close()
                return True
            except TimeoutError:
                print(f"[ERROR] Timeout через {desc}, {ssl_desc}")
            except Exception as e:
                print(
                    f"[ERROR] Ошибка через {desc}, {ssl_desc}: {type(e).__name__}: {str(e)[:100]}"
                )
                if "CancelledError" not in str(type(e)) and "TimeoutError" not in str(
                    type(e)
                ):
                    import traceback

                    traceback.print_exc()

    return False


if __name__ == "__main__":
    asyncio.run(test_direct_connection())
