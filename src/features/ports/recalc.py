from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.core.run_context import RunContext


@dataclass(frozen=True, slots=True)
class RecalcOutcome:
    rows_written: int
    run_id: str
    algo_version: str
    params_hash: str


class FeatureRecalcPort(Protocol):
    async def recalc_in_range(
        self,
        *,
        symbol: str,
        tf: str,
        start_ts_ms: int,
        end_ts_ms: int,
        run_context: RunContext,
    ) -> RecalcOutcome: ...
