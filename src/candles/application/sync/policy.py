from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class MarketDataFailureKind(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    TRANSIENT = "transient"
    FATAL = "fatal"


_TIMEOUT_CLASS_NAMES = {
    "TimeoutError",
    "RequestTimeout",
    "ClientTimeoutError",
    "ConnectTimeoutError",
    "ReadTimeout",
    "ServerTimeoutError",
    "TimeoutException",
}
_RATE_LIMIT_CLASS_NAMES = {
    "RateLimitExceeded",
    "DDoSProtection",
    "TooManyRequests",
}
_TIMEOUT_MESSAGE_MARKERS = (
    "timeout",
    "timed out",
    "request timed out",
    "connect timeout",
    "read timeout",
)
_RATE_LIMIT_MESSAGE_MARKERS = (
    "429",
    "too many requests",
    "50011",
    "rate limit",
    "rate limited",
)
_TRANSIENT_MESSAGE_MARKERS = (
    "5xx",
    "temporarily",
    "temporary",
    "connection reset",
    "connection refused",
)


def _iter_exception_chain(error: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return chain


def _message_matches(message: str, markers: tuple[str, ...]) -> bool:
    normalized = message.lower()
    return any(marker in normalized for marker in markers)


def classify_market_data_failure(error: BaseException) -> MarketDataFailureKind:
    """Classify market-data failures before the retry decision is made."""
    for current in _iter_exception_chain(error):
        name = type(current).__name__
        message = str(current)

        if name in _TIMEOUT_CLASS_NAMES or _message_matches(
            message, _TIMEOUT_MESSAGE_MARKERS
        ):
            return MarketDataFailureKind.TIMEOUT

        if name in _RATE_LIMIT_CLASS_NAMES or _message_matches(
            message, _RATE_LIMIT_MESSAGE_MARKERS
        ):
            return MarketDataFailureKind.RATE_LIMIT

        if _message_matches(message, _TRANSIENT_MESSAGE_MARKERS):
            return MarketDataFailureKind.TRANSIENT

    return MarketDataFailureKind.FATAL


@dataclass(frozen=True)
class SyncPolicyConfig:
    batch_size: int = 300
    max_retries: int = 5
    retry_delay: float = 1.5
    max_concurrent_symbols: int = 1
    extra_data: bool = False


@dataclass
class RetryPolicy:
    max_retries: int
    retry_delay: float
    batch_size: int
    min_delay: float = 0.5
    max_sleep: float = 60.0
    backoff_multiplier: float = 1.5
    jitter_min: float = 0.2
    jitter_max: float = 0.5
    random_uniform: Callable[[float, float], float] = random.uniform

    retriable_markers: tuple[str, ...] = (
        "timeout",
        "timed out",
        "request timed out",
        "429",
        "Too Many Requests",
        "50011",
        "5xx",
        "temporarily",
    )
    rate_limit_markers: tuple[str, ...] = ("429", "Too Many Requests", "50011")

    def initial_delay(self) -> float:
        return max(self.retry_delay, self.min_delay)

    def request_limit(self) -> int:
        return max(int(self.batch_size), 1)

    def is_retriable(self, message: str) -> bool:
        return any(marker in message for marker in self.retriable_markers)

    def is_rate_limited(self, message: str) -> bool:
        return any(marker in message for marker in self.rate_limit_markers)

    def is_retriable_failure(self, failure_kind: MarketDataFailureKind) -> bool:
        return failure_kind in {
            MarketDataFailureKind.TIMEOUT,
            MarketDataFailureKind.RATE_LIMIT,
            MarketDataFailureKind.TRANSIENT,
        }

    def is_rate_limited_failure(self, failure_kind: MarketDataFailureKind) -> bool:
        return failure_kind is MarketDataFailureKind.RATE_LIMIT

    def can_retry(self, attempts: int) -> bool:
        return attempts < self.max_retries

    def next_sleep(self, delay: float) -> float:
        return min(self.max_sleep, delay) + self.random_uniform(
            self.jitter_min, self.jitter_max
        )

    def bump_delay(self, delay: float) -> float:
        return delay * self.backoff_multiplier
