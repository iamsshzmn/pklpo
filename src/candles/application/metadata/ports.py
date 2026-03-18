from __future__ import annotations

from typing import Any, Protocol


class MetadataSourcePort(Protocol):
    async def load_metadata(self, *, extended: bool = False) -> dict[str, Any]: ...


class MetadataCachePort(Protocol):
    def is_valid(self) -> bool: ...

    def get_snapshot(self) -> dict[str, Any] | None: ...

    def store_snapshot(self, snapshot: dict[str, Any]) -> None: ...


class ValidationQueryPort(Protocol):
    def get_instrument_info(self, symbol: str) -> dict[str, Any] | None: ...
