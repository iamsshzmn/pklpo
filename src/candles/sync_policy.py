from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class SwapSyncPolicy:
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

    def can_retry(self, attempts: int) -> bool:
        return attempts < self.max_retries

    def next_sleep(self, delay: float) -> float:
        return min(self.max_sleep, delay) + self.random_uniform(
            self.jitter_min, self.jitter_max
        )

    def bump_delay(self, delay: float) -> float:
        return delay * self.backoff_multiplier
