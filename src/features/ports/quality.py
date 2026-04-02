"""Quality pipeline ports for features application use cases."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class QualityPipelineRunner(Protocol):
    """Callable abstraction for running the quality pipeline."""

    async def __call__(
        self,
        pool: Any,
        *,
        send_alerts: bool = True,
        alert_cooldown_minutes: int = 30,
    ) -> tuple[Any, dict[str, int]]: ...


__all__ = ["QualityPipelineRunner"]
