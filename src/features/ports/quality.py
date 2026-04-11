"""Quality pipeline ports for features application use cases."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager


@runtime_checkable
class QualityReportProtocol(Protocol):
    """Structural contract for quality reports returned by the pipeline."""

    def summary(self) -> dict[str, int]: ...


@runtime_checkable
class QualityConnectionProtocol(Protocol):
    """Minimal DB-connection contract used by the quality pipeline."""

    async def fetch(self, query: str, *args: Any) -> list[Any]: ...

    async def fetchval(self, query: str, *args: Any) -> Any: ...

    async def execute(self, query: str, *args: Any) -> str: ...

    async def executemany(
        self,
        query: str,
        seq_of_params: list[tuple[Any, ...]],
    ) -> None: ...


@runtime_checkable
class QualityPoolProtocol(Protocol):
    """Pool contract consumed by candles quality pipeline internals."""

    def acquire(self) -> AbstractAsyncContextManager[QualityConnectionProtocol]: ...


@runtime_checkable
class QualityEngineProtocol(Protocol):
    """Minimal SQLAlchemy-like engine contract accepted by features."""

    def begin(self) -> AbstractAsyncContextManager[Any]: ...


@runtime_checkable
class QualityPipelineRunner(Protocol):
    """Callable abstraction for running the quality pipeline."""

    async def __call__(
        self,
        engine: QualityEngineProtocol,
        *,
        send_alerts: bool = True,
        alert_cooldown_minutes: int = 30,
    ) -> tuple[QualityReportProtocol, dict[str, int]]: ...


__all__ = [
    "QualityConnectionProtocol",
    "QualityEngineProtocol",
    "QualityPipelineRunner",
    "QualityPoolProtocol",
    "QualityReportProtocol",
]
