"""Thread-safe metrics collection with percentiles via reservoir sampling.

Replaces unbounded list accumulation with fixed-size reservoirs and
atomic counters protected by asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import random
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class ReservoirSampling:
    """Vitter's Algorithm R — fixed-memory random sampling.

    Maintains at most ``max_size`` samples, uniformly distributed
    over all values ever added.
    """

    max_size: int = 1000
    _samples: list[float] = field(default_factory=list, init=False, repr=False)
    _count: int = field(default=0, init=False, repr=False)

    def add(self, value: float) -> None:
        self._count += 1
        if len(self._samples) < self.max_size:
            self._samples.append(value)
        else:
            idx = random.randint(0, self._count - 1)
            if idx < self.max_size:
                self._samples[idx] = value

    def percentile(self, pct: float) -> float:
        """Return the ``pct``-th percentile (0-100). Returns 0.0 if empty."""
        if not self._samples:
            return 0.0
        ordered = sorted(self._samples)
        idx = round((len(ordered) - 1) * pct / 100.0)
        return ordered[min(idx, len(ordered) - 1)]

    @property
    def count(self) -> int:
        return self._count

    def mean(self) -> float:
        if not self._samples:
            return 0.0
        return sum(self._samples) / len(self._samples)

    def reset(self) -> None:
        self._samples.clear()
        self._count = 0


class MetricsCollector:
    """Async-safe metrics with counters and latency percentiles."""

    def __init__(self, reservoir_size: int = 1000) -> None:
        self._lock = asyncio.Lock()
        self._fetch_latencies = ReservoirSampling(max_size=reservoir_size)
        self._upsert_latencies = ReservoirSampling(max_size=reservoir_size)
        self._counters: dict[str, int] = defaultdict(int)

    async def record_fetch(self, latency_sec: float, status: str = "ok") -> None:
        async with self._lock:
            self._fetch_latencies.add(latency_sec)
            self._counters[f"fetch.{status}"] += 1

    async def record_upsert(self, latency_sec: float, batch_size: int = 0) -> None:
        async with self._lock:
            self._upsert_latencies.add(latency_sec)
            self._counters["upsert.ok"] += 1
            self._counters["upsert.rows"] += batch_size

    async def increment(self, key: str, value: int = 1) -> None:
        async with self._lock:
            self._counters[key] += value

    def summary(self) -> dict:
        """Return a snapshot of all metrics. Safe to call without await."""
        return {
            "fetch": {
                "count": self._fetch_latencies.count,
                "latency_avg_ms": round(self._fetch_latencies.mean() * 1000, 3),
                "latency_p50_ms": round(self._fetch_latencies.percentile(50) * 1000, 3),
                "latency_p95_ms": round(self._fetch_latencies.percentile(95) * 1000, 3),
                "latency_p99_ms": round(self._fetch_latencies.percentile(99) * 1000, 3),
                **{k: v for k, v in self._counters.items() if k.startswith("fetch.")},
            },
            "upsert": {
                "count": self._upsert_latencies.count,
                "latency_avg_ms": round(self._upsert_latencies.mean() * 1000, 3),
                "latency_p50_ms": round(
                    self._upsert_latencies.percentile(50) * 1000, 3
                ),
                "latency_p95_ms": round(
                    self._upsert_latencies.percentile(95) * 1000, 3
                ),
                "latency_p99_ms": round(
                    self._upsert_latencies.percentile(99) * 1000, 3
                ),
                **{k: v for k, v in self._counters.items() if k.startswith("upsert.")},
            },
            "counters": {
                k: v
                for k, v in self._counters.items()
                if not k.startswith(("fetch.", "upsert."))
            },
        }

    async def reset(self) -> None:
        async with self._lock:
            self._fetch_latencies.reset()
            self._upsert_latencies.reset()
            self._counters.clear()
