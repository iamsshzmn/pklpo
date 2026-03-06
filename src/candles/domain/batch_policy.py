"""
Dynamic batch-size policy for candle sync.

Adjusts the number of candles requested per API call based on
observed API latency and CPU utilisation.
"""

from __future__ import annotations


class DynamicBatchPolicy:
    """Adjusts batch size at runtime based on load signals.

    Rules (evaluated in order):
    1. If cpu_pct >= cpu_threshold → return min_batch_size.
    2. If api_latency_ms >= latency_threshold → scale down by scale_down_factor.
    3. If both are below thresholds → allow gradual recovery toward default.
    """

    def __init__(
        self,
        default_batch_size: int = 300,
        min_batch_size: int = 50,
        latency_threshold_ms: float = 500.0,
        cpu_threshold_pct: float = 80.0,
        scale_down_factor: float = 0.8,
        recovery_factor: float = 1.1,
    ) -> None:
        self._default = default_batch_size
        self._min = min_batch_size
        self._latency_threshold = latency_threshold_ms
        self._cpu_threshold = cpu_threshold_pct
        self._scale_down = scale_down_factor
        self._recovery = recovery_factor
        self._current = float(default_batch_size)

    @property
    def current_batch_size(self) -> int:
        return max(self._min, min(self._default, int(self._current)))

    def get_batch_size(
        self,
        tf: str,
        api_latency_ms: float = 0.0,
        cpu_pct: float = 0.0,
    ) -> int:
        """Return batch size to use for the next request.

        Args:
            tf: Timeframe string (reserved for future per-TF tuning).
            api_latency_ms: Measured latency of the last API call in ms.
            cpu_pct: Current CPU utilisation percentage (0–100).

        Returns:
            Number of candles to request.
        """
        if cpu_pct >= self._cpu_threshold:
            self._current = float(self._min)
        elif api_latency_ms >= self._latency_threshold:
            self._current = max(self._min, self._current * self._scale_down)
        else:
            # Gradual recovery toward default
            self._current = min(self._default, self._current * self._recovery)

        return self.current_batch_size

    def reset(self) -> None:
        """Reset to default batch size."""
        self._current = float(self._default)
