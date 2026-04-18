import os
from collections.abc import AsyncGenerator
from typing import Any

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

try:
    from sqlalchemy.ext.asyncio import async_sessionmaker
except ImportError:
    # Fallback for older SQLAlchemy versions (< 2.0)
    # mypy: ignore-errors
    from typing import Any as TypingAny

    from sqlalchemy.orm import sessionmaker

    class AsyncSessionMaker:
        """Fallback for async_sessionmaker in older SQLAlchemy versions"""

        def __init__(self, bind=None, **kwargs: TypingAny):
            self.bind = bind
            self.kwargs = kwargs
            self._sessionmaker = sessionmaker(bind=bind, class_=AsyncSession, **kwargs)

        def __call__(self, **local_kwargs: TypingAny):
            return self._sessionmaker(**local_kwargs)

    async_sessionmaker = AsyncSessionMaker  # type: ignore

from src.config.settings import check_required_env_vars, get_database_url

load_dotenv()

# Check required environment variables
missing_vars = check_required_env_vars()
if missing_vars:
    raise ValueError(
        f"Required environment variables not set: {', '.join(missing_vars)}"
    )

# Get database URL via validator
DATABASE_URL = get_database_url()

# Replace localhost with 127.0.0.1 to avoid IPv6 issues on Windows
if "localhost" in DATABASE_URL.lower() and "127.0.0.1" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("localhost", "127.0.0.1").replace(
        "LOCALHOST", "127.0.0.1"
    )

# Determine whether to use SSL
# Check explicit environment variable
database_ssl_env = os.getenv("DATABASE_SSL", "").lower()
if database_ssl_env in ("true", "1", "require", "yes"):
    use_ssl = True
elif database_ssl_env in ("false", "0", "disable", "no"):
    use_ssl = False
else:
    # Default: SSL only for external connections
    # For localhost and Docker names (no dots in hostname) disable SSL
    url_lower = DATABASE_URL.lower()
    is_localhost = "localhost" in url_lower or "127.0.0.1" in url_lower

    # Extract host from URL (part between @ and :)
    try:
        host_part = url_lower.split("@")[-1].split(":")[0].split("/")[0]
        # If host contains a dot (except localhost), it's external - need SSL
        # Docker names usually have no dots (e.g. pklpo_db)
        has_dot_in_host = "." in host_part and not is_localhost
        use_ssl = has_dot_in_host
    except Exception:
        # On parse error, disable SSL for safety
        use_ssl = False

# Connection pooling with timeouts for asyncpg
connect_args: dict[str, Any] = {
    "timeout": 30,  # Connection timeout (seconds)
    "command_timeout": 30,  # Command execution timeout (seconds)
    "server_settings": {
        "application_name": "pklpo",
    },
}

# For asyncpg: 'disable' disables SSL, 'require' enables it
if use_ssl:
    connect_args["ssl"] = "require"
else:
    connect_args["ssl"] = "disable"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_timeout=15,  # Pool checkout timeout (seconds)
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,  # Disable auto-flush to avoid greenlet issues
    autocommit=False,  # Explicit control over commit
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async session generator for dependency injection."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_session() -> AsyncSession:
    """Create a new session for direct use."""
    session: AsyncSession = AsyncSessionLocal()
    return session


def get_async_engine():
    """Return the async engine for CLI usage."""
    return engine


async def reset_pool() -> None:
    """Dispose all pooled connections and force reconnect on next checkout.

    Call this when connection_invalidated is detected to ensure stale
    connections are purged from the pool before retry attempts.
    """
    await engine.dispose()
