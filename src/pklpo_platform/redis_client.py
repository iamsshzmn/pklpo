"""Redis client factory.

Single lazy-initialized async Redis connection shared across the process.
Callers must not bypass this module to create ad-hoc connections.

Fail policy:
- Connection errors are raised at get_redis() call time.
- Callers (locks, cache) decide whether to fail-closed or fail-open.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

_redis_client: "Redis | None" = None

logger = logging.getLogger(__name__)


async def get_redis() -> "Redis":
    """Return the shared async Redis client, creating it on first call.

    Raises:
        ImportError: if redis[asyncio] is not installed.
        redis.exceptions.ConnectionError: if Redis is unreachable.
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    try:
        from redis.asyncio import Redis  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "redis[asyncio] is required for distributed locks and cache. "
            "Install with: pip install 'redis[asyncio]'"
        ) from exc

    from src.config.settings import get_settings

    settings = get_settings()
    _redis_client = Redis.from_url(
        settings.redis.url,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
    )
    return _redis_client


async def close_redis() -> None:
    """Close the shared Redis connection (call on app shutdown)."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


def _key(prefix: str, *parts: str) -> str:
    """Build a namespaced Redis key."""
    from src.config.settings import get_settings

    ns = get_settings().redis.key_prefix
    segments = [ns, prefix, *parts]
    return ":".join(s for s in segments if s)
