"""Distributed job-level lock via Redis.

Scope: orchestration boundary only. Protects against concurrent re-entry of
the same logical job (repair/sync). Does NOT replace Postgres advisory locks,
which guard write-critical DB sections inside a transaction.

Fail policy: fail-closed — if Redis is unavailable, lock acquisition raises
RedisLockError and the caller should abort rather than proceed unprotected.

Usage:
    async with job_lock("swap_repair", symbol="BTC-USDT-SWAP", timeframe="1h") as lock_id:
        await do_heavy_work()

Lock contention is logged as a structured event with error_type="lock_conflict".
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


class RedisLockError(RuntimeError):
    """Raised when a distributed lock cannot be acquired."""


class LockConflict(RedisLockError):
    """Another process holds the lock for this logical target."""


async def _acquire(
    key: str,
    lock_id: str,
    timeout_seconds: int,
    retry_delay_ms: int,
    retry_attempts: int,
) -> bool:
    """Try to SET NX EX on the lock key. Returns True if acquired."""
    from .redis_client import get_redis

    redis = await get_redis()
    for attempt in range(retry_attempts):
        acquired = await redis.set(key, lock_id, nx=True, ex=timeout_seconds)
        if acquired:
            return True
        if attempt < retry_attempts - 1:
            await asyncio.sleep(retry_delay_ms / 1000)
    return False


async def _release(key: str, lock_id: str) -> None:
    """Release the lock only if we still own it (Lua CAS)."""
    from .redis_client import get_redis

    redis = await get_redis()
    # Atomic check-and-delete
    lua = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """
    await redis.eval(lua, 1, key, lock_id)  # type: ignore[arg-type]


@asynccontextmanager
async def job_lock(
    job: str,
    *,
    symbol: str | None = None,
    timeframe: str | None = None,
    component: str | None = None,
) -> AsyncIterator[str]:
    """Async context manager that acquires a distributed job lock.

    Args:
        job: Logical job name, e.g. "swap_repair", "swap_sync".
        symbol: Trading symbol (used in lock key and log context).
        timeframe: Timeframe (used in lock key and log context).
        component: Component name for structured logging.

    Yields:
        lock_id: Unique identifier for this lock lease.

    Raises:
        LockConflict: Another process holds the lock and retries exhausted.
        RedisLockError: Redis unavailable (fail-closed).
    """
    from src.config.settings import get_settings

    from .redis_client import _key, get_redis  # noqa: F401 (trigger import check)

    settings = get_settings().redis

    parts = [job]
    if symbol:
        parts.append(symbol)
    if timeframe:
        parts.append(timeframe)
    lock_key = _key("lock", *parts)
    lock_id = uuid.uuid4().hex

    log_ctx = {
        "component": component or job,
        "symbol": symbol or "-",
        "timeframe": timeframe or "-",
    }

    try:
        acquired = await _acquire(
            lock_key,
            lock_id,
            timeout_seconds=settings.lock_timeout_seconds,
            retry_delay_ms=settings.lock_retry_delay_ms,
            retry_attempts=settings.lock_retry_attempts,
        )
    except Exception as exc:
        logger.error(
            "Redis unavailable — cannot acquire job lock key=%s error=%s",
            lock_key,
            exc,
            extra={**log_ctx, "error_type": type(exc).__name__},
        )
        raise RedisLockError(f"Redis unavailable: {exc}") from exc

    if not acquired:
        logger.warning(
            "Lock conflict — another process holds key=%s job=%s symbol=%s timeframe=%s",
            lock_key,
            job,
            symbol or "-",
            timeframe or "-",
            extra={**log_ctx, "error_type": "lock_conflict"},
        )
        raise LockConflict(
            f"Job '{job}' is already running for {symbol}/{timeframe}. "
            "Another process holds the distributed lock."
        )

    logger.info(
        "Acquired job lock key=%s lock_id=%s",
        lock_key,
        lock_id,
        extra=log_ctx,
    )
    try:
        yield lock_id
    finally:
        await _release(lock_key, lock_id)
        logger.debug(
            "Released job lock key=%s lock_id=%s",
            lock_key,
            lock_id,
            extra=log_ctx,
        )
