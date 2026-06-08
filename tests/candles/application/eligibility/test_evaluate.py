from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from src.candles.application.eligibility.evaluate import RefreshEligibilityUseCase
from src.candles.application.eligibility.ports import EligibilitySnapshot
from src.candles.domain.eligibility import (
    CoverageFacts,
    EligibilityState,
    build_timeframe_policies,
)


@dataclass
class CoverageReaderStub:
    facts: list[CoverageFacts]

    async def read_coverage_facts(self) -> list[CoverageFacts]:
        return self.facts


@dataclass
class EligibilityRepositoryStub:
    records: dict[tuple[str, str], EligibilitySnapshot] = field(default_factory=dict)
    upserts: list[object] = field(default_factory=list)
    transitions: list[dict[str, object]] = field(default_factory=list)

    async def get_current(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> EligibilitySnapshot | None:
        return self.records.get((symbol, timeframe))

    async def upsert_verdict(self, verdict: object, *, evaluator_run_id: str) -> None:
        self.upserts.append(verdict)
        self.records[(verdict.symbol, verdict.timeframe)] = EligibilitySnapshot(
            symbol=verdict.symbol,
            timeframe=verdict.timeframe,
            state=verdict.state,
        )

    async def append_transition(
        self,
        *,
        verdict: object,
        from_state: EligibilityState | None,
        evaluator_run_id: str,
    ) -> None:
        self.transitions.append(
            {
                "symbol": verdict.symbol,
                "timeframe": verdict.timeframe,
                "from_state": from_state,
                "to_state": verdict.state,
                "evaluator_run_id": evaluator_run_id,
            }
        )


@pytest.mark.asyncio
async def test_refresh_eligibility_appends_transition_on_state_change() -> None:
    repo = EligibilityRepositoryStub(
        records={
            ("BTC-USDT-SWAP", "1H"): EligibilitySnapshot(
                symbol="BTC-USDT-SWAP",
                timeframe="1H",
                state=EligibilityState.INSUFFICIENT_HISTORY,
            )
        }
    )
    use_case = RefreshEligibilityUseCase(
        coverage_reader=CoverageReaderStub(
            [
                CoverageFacts(
                    symbol="BTC-USDT-SWAP",
                    timeframe="1H",
                    actual_bars=500,
                    coverage_pct=100.0,
                )
            ]
        ),
        repository=repo,
    )

    summary = await use_case.run(evaluator_run_id="elig-run")

    assert summary.evaluated == 1
    assert summary.transitions == 1
    assert len(repo.upserts) == 1
    assert repo.transitions == [
        {
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1H",
            "from_state": EligibilityState.INSUFFICIENT_HISTORY,
            "to_state": EligibilityState.ELIGIBLE,
            "evaluator_run_id": "elig-run",
        }
    ]


@pytest.mark.asyncio
async def test_refresh_eligibility_is_idempotent_for_unchanged_state() -> None:
    repo = EligibilityRepositoryStub(
        records={
            ("BTC-USDT-SWAP", "1H"): EligibilitySnapshot(
                symbol="BTC-USDT-SWAP",
                timeframe="1H",
                state=EligibilityState.ELIGIBLE,
            )
        }
    )
    facts = CoverageFacts(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        actual_bars=500,
        coverage_pct=100.0,
    )
    use_case = RefreshEligibilityUseCase(
        coverage_reader=CoverageReaderStub([facts]),
        repository=repo,
    )

    first = await use_case.run(evaluator_run_id="elig-run-1")
    second = await use_case.run(evaluator_run_id="elig-run-2")

    assert first.evaluated == 1
    assert second.evaluated == 1
    assert repo.transitions == []
    assert len(repo.upserts) == 2


@pytest.mark.asyncio
async def test_refresh_eligibility_uses_injected_timeframe_policies() -> None:
    repo = EligibilityRepositoryStub()
    use_case = RefreshEligibilityUseCase(
        coverage_reader=CoverageReaderStub(
            [
                CoverageFacts(
                    symbol="BTC-USDT-SWAP",
                    timeframe="1H",
                    actual_bars=3,
                    coverage_pct=100.0,
                )
            ]
        ),
        repository=repo,
        policies=build_timeframe_policies({"1H": 3}),
    )

    summary = await use_case.run(evaluator_run_id="elig-run")

    assert summary.evaluated == 1
    assert repo.upserts[0].state is EligibilityState.ELIGIBLE
    assert repo.upserts[0].required_bars == 3
