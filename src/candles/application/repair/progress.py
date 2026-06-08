from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.candles.domain.repair import NoProgressPolicy


@dataclass
class NoProgressTracker:
    policy: NoProgressPolicy
    timeframe: str
    _consecutive: int = field(default=0, init=False, repr=False)
    _blocked_consecutive: int = field(default=0, init=False, repr=False)

    def record(self, progress: int, *, blocked: bool = False) -> None:
        if blocked:
            self._consecutive = 0
            self._blocked_consecutive += 1
            return
        if progress <= 0:
            self._consecutive += 1
            self._blocked_consecutive = 0
            return
        self._consecutive = 0
        self._blocked_consecutive = 0

    def should_escalate(self) -> bool:
        return (
            self.policy.is_critical(self.timeframe)
            and self._consecutive >= self.policy.no_progress_threshold
        )

    def snapshot(self) -> dict[str, int | bool | str]:
        return {
            "timeframe": self.timeframe,
            "critical": self.policy.is_critical(self.timeframe),
            "consecutive_no_progress": self._consecutive,
            "consecutive_blocked": self._blocked_consecutive,
            "threshold": self.policy.no_progress_threshold,
        }
