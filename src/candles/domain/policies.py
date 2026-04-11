"""Reliability policies: CircuitBreaker and retry_io universal wrapper."""

from __future__ import annotations

import asyncio
import enum
import logging
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Circuit breaker with Closed → Open → HalfOpen → Closed transitions.

    Args:
        name: Identifier for logging (e.g. "okx_api", "postgres").
        failure_threshold: Consecutive failures before opening.
        cooldown_sec: Seconds to wait in Open before probing.
        half_open_max_calls: How many probe calls allowed in HalfOpen.
    """

    name: str
    failure_threshold: int = 5
    cooldown_sec: float = 30.0
    half_open_max_calls: int = 1

    # Internal state (not constructor args)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False, repr=False)
    _consecutive_failures: int = field(default=0, init=False, repr=False)
    _opened_at: float = field(default=0.0, init=False, repr=False)
    _half_open_calls: int = field(default=0, init=False, repr=False)

    @property
    def state(self) -> CircuitState:
        if self._state is CircuitState.OPEN:
            if time.monotonic() - self._opened_at >= self.cooldown_sec:
                self._transition(CircuitState.HALF_OPEN)
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state is CircuitState.OPEN

    def record_success(self) -> None:
        if self._state in (CircuitState.HALF_OPEN, CircuitState.CLOSED):
            self._consecutive_failures = 0
            self._half_open_calls = 0
            if self._state is CircuitState.HALF_OPEN:
                self._transition(CircuitState.CLOSED)

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._state is CircuitState.HALF_OPEN or self._consecutive_failures >= self.failure_threshold:
            self._transition(CircuitState.OPEN)

    def _transition(self, new_state: CircuitState) -> None:
        old = self._state
        self._state = new_state
        if new_state is CircuitState.OPEN:
            self._opened_at = time.monotonic()
            self._half_open_calls = 0
        elif new_state is CircuitState.HALF_OPEN:
            self._half_open_calls = 0
        logger.info(
            "CircuitBreaker[%s] %s → %s (failures=%d)",
            self.name,
            old.value,
            new_state.value,
            self._consecutive_failures,
        )

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._half_open_calls = 0


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit is open."""

    def __init__(self, circuit_name: str) -> None:
        self.circuit_name = circuit_name
        super().__init__(f"Circuit breaker '{circuit_name}' is open")


# ---------------------------------------------------------------------------
# Retry I/O
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RetryIOPolicy:
    """Policy for retry_io wrapper.

    Uses full jitter: ``uniform(0, min(max_delay, base_delay * 2^attempt))``.
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    retriable_exceptions: tuple[type[Exception], ...] = (Exception,)

    def is_retriable(self, exc: Exception) -> bool:
        return isinstance(exc, self.retriable_exceptions)

    def delay_with_jitter(self, attempt: int) -> float:
        exp_delay = min(self.max_delay, self.base_delay * (2 ** attempt))
        return random.uniform(0, exp_delay)


async def retry_io(
    fn: Callable[..., Awaitable[T]],
    *args: object,
    policy: RetryIOPolicy,
    circuit_breaker: CircuitBreaker | None = None,
    **kwargs: object,
) -> T:
    """Retry any async I/O call with exponential backoff, jitter, and optional circuit breaker."""
    last_exc: Exception | None = None

    for attempt in range(policy.max_retries + 1):
        if circuit_breaker and circuit_breaker.is_open:
            raise CircuitOpenError(circuit_breaker.name)

        try:
            result = await fn(*args, **kwargs)
            if circuit_breaker:
                circuit_breaker.record_success()
            return result
        except Exception as exc:
            last_exc = exc
            if not policy.is_retriable(exc):
                raise

            if circuit_breaker:
                circuit_breaker.record_failure()

            if attempt == policy.max_retries:
                raise

            sleep_sec = policy.delay_with_jitter(attempt)
            logger.warning(
                "retry_io attempt %d/%d failed (%s), retrying in %.2fs",
                attempt + 1,
                policy.max_retries,
                exc,
                sleep_sec,
            )
            await asyncio.sleep(sleep_sec)

    # Should not reach here, but satisfy type checker
    assert last_exc is not None
    raise last_exc
