"""Bounded read-through cache facade.

Scope: three use-case groups only:
  1. exchange_metadata  — OKX instrument specs (contract size, tick size, etc.)
  2. instrument_list    — active tradeable universe
  3. last_timestamp     — last ingested candle timestamp per (symbol, timeframe)

Fail policy: fail-open — on Redis unavailability the loader is called directly
and the result is returned without caching. Correctness is never Redis-dependent.

Usage:
    value = await get_cached(
        CacheGroup.LAST_TIMESTAMP,
        key_parts=("BTC-USDT-SWAP", "1h"),
        loader=lambda: fetch_last_ts("BTC-USDT-SWAP", "1h"),
    )

    await invalidate(CacheGroup.INSTRUMENT_LIST)
"""

from __future__ import annotations

import json
import logging
from enum import StrEnum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# In-memory hit/miss counters (thread-safe for GIL-protected int increments).
# Read by push_cache_metrics() in src/pklpo_platform/metrics_cache.py.
# ---------------------------------------------------------------------------
_cache_hits: int = 0
_cache_misses: int = 0


def get_cache_stats() -> dict[str, int]:
    """Return a snapshot of accumulated cache hit/miss counts since process start."""
    return {"hits": _cache_hits, "misses": _cache_misses}


class CacheGroup(StrEnum):
    EXCHANGE_METADATA = "exchange_metadata"
    INSTRUMENT_LIST = "instrument_list"
    LAST_TIMESTAMP = "last_timestamp"


def _ttl_for(group: CacheGroup) -> int:
    from src.config.settings import get_settings

    s = get_settings().redis
    return {
        CacheGroup.EXCHANGE_METADATA: s.cache_ttl_exchange_metadata_seconds,
        CacheGroup.INSTRUMENT_LIST: s.cache_ttl_instrument_list_seconds,
        CacheGroup.LAST_TIMESTAMP: s.cache_ttl_last_timestamp_seconds,
    }[group]


async def get_cached(
    group: CacheGroup,
    key_parts: tuple[str, ...],
    loader: Any,  # Callable[[], Awaitable[T]] | Callable[[], T]
) -> Any:
    """Return cached value or call loader on miss/error.

    Args:
        group: Cache group (determines TTL).
        key_parts: Additional key segments after group prefix.
        loader: Async or sync callable with no args that returns the value.

    Returns:
        Cached or freshly loaded value.
    """
    import asyncio

    from .redis_client import _key, get_redis

    cache_key = _key("cache", group.value, *key_parts)

    # --- try cache ---
    try:
        redis = await get_redis()
        raw = await redis.get(cache_key)
        if raw is not None:
            global _cache_hits
            _cache_hits += 1
            logger.debug(
                "Cache hit key=%s group=%s",
                cache_key,
                group.value,
                extra={"component": "cache", "error_type": "-"},
            )
            return json.loads(raw)
    except Exception as exc:
        logger.warning(
            "Cache read failed — falling through to loader key=%s error=%s",
            cache_key,
            exc,
            extra={"component": "cache", "error_type": type(exc).__name__},
        )

    # --- cache miss or error: call loader ---
    global _cache_misses
    _cache_misses += 1
    logger.debug(
        "Cache miss key=%s group=%s",
        cache_key,
        group.value,
        extra={"component": "cache", "error_type": "-"},
    )
    if asyncio.iscoroutinefunction(loader):
        value = await loader()
    else:
        value = loader()

    # --- try to store result ---
    try:
        redis = await get_redis()
        ttl = _ttl_for(group)
        await redis.set(cache_key, json.dumps(value), ex=ttl)
    except Exception as exc:
        logger.warning(
            "Cache write failed — result returned without caching key=%s error=%s",
            cache_key,
            exc,
            extra={"component": "cache", "error_type": type(exc).__name__},
        )

    return value


async def invalidate(group: CacheGroup, *key_parts: str) -> None:
    """Delete cached entries for a group (optionally scoped to key_parts).

    If key_parts is empty, scans and deletes all keys for the group.
    """
    from .redis_client import _key, get_redis

    try:
        redis = await get_redis()
        if key_parts:
            cache_key = _key("cache", group.value, *key_parts)
            await redis.delete(cache_key)
            logger.debug("Cache invalidated key=%s", cache_key, extra={"component": "cache"})
        else:
            pattern = _key("cache", group.value, "*")
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=pattern, count=100)
                if keys:
                    await redis.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            logger.info(
                "Cache invalidated group=%s keys_deleted=%d",
                group.value,
                deleted,
                extra={"component": "cache"},
            )
    except Exception as exc:
        logger.warning(
            "Cache invalidation failed group=%s error=%s",
            group.value,
            exc,
            extra={"component": "cache", "error_type": type(exc).__name__},
        )
