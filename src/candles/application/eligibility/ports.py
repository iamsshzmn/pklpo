from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.candles.domain.eligibility import (
        CoverageFacts,
        EligibilityState,
        EligibilityVerdict,
    )


@dataclass(frozen=True)
class EligibilitySnapshot:
    symbol: str
    timeframe: str
    state: EligibilityState


class CoverageReader(Protocol):
    async def read_coverage_facts(self) -> list[CoverageFacts]: ...


class EligibilityRepository(Protocol):
    async def get_current(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> EligibilitySnapshot | None: ...

    async def upsert_verdict(
        self,
        verdict: EligibilityVerdict,
        *,
        evaluator_run_id: str,
    ) -> None: ...

    async def append_transition(
        self,
        *,
        verdict: EligibilityVerdict,
        from_state: EligibilityState | None,
        evaluator_run_id: str,
    ) -> None: ...
