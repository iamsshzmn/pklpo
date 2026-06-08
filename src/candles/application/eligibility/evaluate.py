from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.candles.domain.eligibility import evaluate_feature_eligibility

if TYPE_CHECKING:
    from src.candles.application.eligibility.ports import (
        CoverageReader,
        EligibilityRepository,
    )
    from src.candles.domain.eligibility import TimeframeEligibilityPolicy


@dataclass(frozen=True)
class EligibilityRefreshSummary:
    evaluated: int
    transitions: int


@dataclass(frozen=True)
class RefreshEligibilityUseCase:
    coverage_reader: CoverageReader
    repository: EligibilityRepository
    policies: dict[str, TimeframeEligibilityPolicy] | None = None

    async def run(self, *, evaluator_run_id: str) -> EligibilityRefreshSummary:
        facts_rows = await self.coverage_reader.read_coverage_facts()
        transition_count = 0
        for facts in facts_rows:
            verdict = evaluate_feature_eligibility(facts, policies=self.policies)
            current = await self.repository.get_current(
                symbol=verdict.symbol,
                timeframe=verdict.timeframe,
            )
            previous_state = current.state if current is not None else None
            await self.repository.upsert_verdict(
                verdict,
                evaluator_run_id=evaluator_run_id,
            )
            if previous_state != verdict.state:
                await self.repository.append_transition(
                    verdict=verdict,
                    from_state=previous_state,
                    evaluator_run_id=evaluator_run_id,
                )
                transition_count += 1
        return EligibilityRefreshSummary(
            evaluated=len(facts_rows),
            transitions=transition_count,
        )
