from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .dto import BootstrapProgress


class BootstrapStatePort(Protocol):
    async def upsert_bootstrap_state(
        self,
        *,
        symbol: str,
        timeframe: str,
        lookback_days: int,
        target_start_ts: int,
        target_end_ts: int,
        expected_bars: int,
        status: str,
        checkpoint_ts: int | None = None,
        current_min_ts: int | None = None,
        current_max_ts: int | None = None,
        actual_bars: int | None = None,
        missing_bars: int | None = None,
        coverage_pct: float | None = None,
        bootstrap_completed: bool = False,
        completed_at_ms: int | None = None,
        last_run_id: str | None = None,
        last_error: str | None = None,
        error_streak: int = 0,
    ) -> None: ...

    async def get_bootstrap_state(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> BootstrapProgress | None: ...


__all__ = ["BootstrapStatePort"]
