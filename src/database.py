import os
from collections.abc import AsyncGenerator
from typing import Any

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

try:
    from sqlalchemy.ext.asyncio import async_sessionmaker
except ImportError:
    # Fallback для старых версий SQLAlchemy (< 2.0)
    # mypy: ignore-errors
    from typing import Any as TypingAny

    from sqlalchemy.orm import sessionmaker

    class AsyncSessionMaker:
        """Fallback для async_sessionmaker в старых версиях SQLAlchemy"""

        def __init__(self, bind=None, **kwargs: TypingAny):
            self.bind = bind
            self.kwargs = kwargs
            self._sessionmaker = sessionmaker(bind=bind, class_=AsyncSession, **kwargs)

        def __call__(self, **local_kwargs: TypingAny):
            return self._sessionmaker(**local_kwargs)

    async_sessionmaker = AsyncSessionMaker  # type: ignore

from src.config.env_validator import check_required_env_vars, get_database_url

load_dotenv()

# Проверяем обязательные переменные окружения
missing_vars = check_required_env_vars()
if missing_vars:
    raise ValueError(
        f"Необходимо установить переменные окружения: {', '.join(missing_vars)}"
    )

# Получаем URL базы данных через валидатор
DATABASE_URL = get_database_url()

# Заменяем localhost на 127.0.0.1 для избежания проблем с IPv6 на Windows
if "localhost" in DATABASE_URL.lower() and "127.0.0.1" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("localhost", "127.0.0.1").replace(
        "LOCALHOST", "127.0.0.1"
    )

# Определяем, нужно ли использовать SSL
# Проверяем явную переменную окружения
database_ssl_env = os.getenv("DATABASE_SSL", "").lower()
if database_ssl_env in ("true", "1", "require", "yes"):
    use_ssl = True
elif database_ssl_env in ("false", "0", "disable", "no"):
    use_ssl = False
else:
    # По умолчанию: SSL только для внешних подключений
    # Для localhost и Docker-имен (без точки в имени хоста) SSL отключаем
    url_lower = DATABASE_URL.lower()
    is_localhost = "localhost" in url_lower or "127.0.0.1" in url_lower

    # Извлекаем хост из URL (часть между @ и :)
    try:
        host_part = url_lower.split("@")[-1].split(":")[0].split("/")[0]
        # Если хост содержит точку (кроме localhost), это внешний хост - нужен SSL
        # Docker-имена обычно без точек (например, pklpo_db)
        has_dot_in_host = "." in host_part and not is_localhost
        use_ssl = has_dot_in_host
    except Exception:
        # В случае ошибки парсинга отключаем SSL для безопасности
        use_ssl = False

# Настройка connection pooling с таймаутами для asyncpg
connect_args: dict[str, Any] = {
    "timeout": 30,  # Таймаут подключения (секунды)
    "command_timeout": 30,  # Таймаут выполнения команд (секунды)
    "server_settings": {
        "application_name": "pklpo",
    },
}

# Для asyncpg: 'disable' отключает SSL, 'require' включает
# Используем строку 'disable' вместо False для совместимости
if use_ssl:
    connect_args["ssl"] = "require"
else:
    connect_args["ssl"] = "disable"  # 'disable' отключает SSL

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_size=5,  # Уменьшаем размер пула для локальной разработки
    max_overflow=10,
    pool_pre_ping=False,  # Отключаем pre_ping на Windows для избежания проблем
    pool_recycle=3600,
    pool_timeout=15,  # Таймаут получения соединения из пула (секунды)
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,  # Disable auto-flush to avoid greenlet issues
    autocommit=False,  # Explicit control over commit
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Генератор для dependency injection в FastAPI"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_session() -> AsyncSession:
    """Создает новую сессию для прямого использования"""
    session: AsyncSession = AsyncSessionLocal()
    return session


def get_async_engine():
    """Возвращает async engine для использования в CLI."""
    return engine
