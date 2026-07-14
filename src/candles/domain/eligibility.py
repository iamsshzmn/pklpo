from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EligibilityState(StrEnum):
    ELIGIBLE = "eligible"
    INSUFFICIENT_HISTORY = "insufficient_history"
    INCOMPLETE_HISTORY = "incomplete_history"
    INVALID_HISTORY = "invalid_history"
    INFORMATIONAL_ONLY = "informational_only"
    DISABLED = "disabled"


class ReasonFlag(StrEnum):
    LOW_FILL = "LOW_FILL"
    HIGH_GAPS = "HIGH_GAPS"
    INSUFFICIENT_WARMUP = "INSUFFICIENT_WARMUP"
    SHORT_HISTORY = "SHORT_HISTORY"
    STALE_DATA = "STALE_DATA"
    BELOW_RECOMMENDED = "BELOW_RECOMMENDED"
    INTEGRITY_VIOLATION = "INTEGRITY_VIOLATION"
    TF_INFORMATIONAL = "TF_INFORMATIONAL"
    OPERATOR_DISABLED = "OPERATOR_DISABLED"


class TimeframeRole(StrEnum):
    FULL = "full"
    CONTEXT = "context"
    INFORMATIONAL = "informational"
    INACTIVE = "inactive"


@dataclass(frozen=True)
class TimeframeEligibilityPolicy:
    role: TimeframeRole
    required_bars: int
    coverage_min_pct: float = 99.5


@dataclass(frozen=True)
class CoverageFacts:
    symbol: str
    timeframe: str
    actual_bars: int
    coverage_pct: float | None
    first_ts: int | None = None
    last_ts: int | None = None
    reason_flags: frozenset[ReasonFlag] = field(default_factory=frozenset)
    has_interior_gap: bool = False
    integrity_ok: bool = True
    disabled: bool = False
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EligibilityVerdict:
    symbol: str
    timeframe: str
    state: EligibilityState
    required_bars: int
    actual_bars: int
    coverage_pct: float | None
    reason_flags: frozenset[ReasonFlag]
    can_compute_features: bool
    can_score: bool
    can_train_ml: bool
    context_only: bool
    first_ts: int | None = None
    last_ts: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)


TIMEFRAME_POLICIES: dict[str, TimeframeEligibilityPolicy] = {
    "1H": TimeframeEligibilityPolicy(TimeframeRole.FULL, required_bars=500),
    "4H": TimeframeEligibilityPolicy(TimeframeRole.FULL, required_bars=500),
    "1D": TimeframeEligibilityPolicy(TimeframeRole.FULL, required_bars=500),
    "1W": TimeframeEligibilityPolicy(TimeframeRole.CONTEXT, required_bars=280),
    "1M": TimeframeEligibilityPolicy(TimeframeRole.INFORMATIONAL, required_bars=0),
}


def build_timeframe_policies(
    warmup_bars_by_timeframe: dict[str, int],
) -> dict[str, TimeframeEligibilityPolicy]:
    role_by_timeframe = {
        "1H": TimeframeRole.FULL,
        "4H": TimeframeRole.FULL,
        "1D": TimeframeRole.FULL,
        "1W": TimeframeRole.CONTEXT,
        "1M": TimeframeRole.INFORMATIONAL,
    }
    return {
        timeframe: TimeframeEligibilityPolicy(
            role=role_by_timeframe.get(timeframe, TimeframeRole.INACTIVE),
            required_bars=int(required_bars),
        )
        for timeframe, required_bars in warmup_bars_by_timeframe.items()
    }


def evaluate_feature_eligibility(
    facts: CoverageFacts,
    *,
    policies: dict[str, TimeframeEligibilityPolicy] | None = None,
) -> EligibilityVerdict:
    policy = (policies or TIMEFRAME_POLICIES).get(
        facts.timeframe,
        TimeframeEligibilityPolicy(TimeframeRole.INACTIVE, required_bars=0),
    )
    reason_flags = set(facts.reason_flags)
    state = _resolve_state(facts, policy, reason_flags)
    capabilities = _capabilities_for(state, policy.role)

    return EligibilityVerdict(
        symbol=facts.symbol,
        timeframe=facts.timeframe,
        state=state,
        required_bars=policy.required_bars,
        actual_bars=facts.actual_bars,
        coverage_pct=facts.coverage_pct,
        reason_flags=frozenset(reason_flags),
        can_compute_features=capabilities["can_compute_features"],
        can_score=capabilities["can_score"],
        can_train_ml=capabilities["can_train_ml"],
        context_only=capabilities["context_only"],
        first_ts=facts.first_ts,
        last_ts=facts.last_ts,
        detail=facts.detail,
    )


def _resolve_state(
    facts: CoverageFacts,
    policy: TimeframeEligibilityPolicy,
    reason_flags: set[ReasonFlag],
) -> EligibilityState:
    if facts.disabled or policy.role is TimeframeRole.INACTIVE:
        reason_flags.add(ReasonFlag.OPERATOR_DISABLED)
        return EligibilityState.DISABLED
    if policy.role is TimeframeRole.INFORMATIONAL:
        reason_flags.add(ReasonFlag.TF_INFORMATIONAL)
        return EligibilityState.INFORMATIONAL_ONLY
    if not facts.integrity_ok:
        reason_flags.add(ReasonFlag.INTEGRITY_VIOLATION)
        return EligibilityState.INVALID_HISTORY
    if facts.actual_bars < policy.required_bars:
        reason_flags.add(ReasonFlag.INSUFFICIENT_WARMUP)
        reason_flags.add(ReasonFlag.SHORT_HISTORY)
        if facts.actual_bars >= 280 and policy.required_bars >= 500:
            reason_flags.add(ReasonFlag.BELOW_RECOMMENDED)
        return EligibilityState.INSUFFICIENT_HISTORY
    if (
        facts.coverage_pct is not None and facts.coverage_pct < policy.coverage_min_pct
    ) or facts.has_interior_gap:
        reason_flags.add(ReasonFlag.HIGH_GAPS)
        if (
            facts.coverage_pct is not None
            and facts.coverage_pct < policy.coverage_min_pct
        ):
            reason_flags.add(ReasonFlag.LOW_FILL)
        return EligibilityState.INCOMPLETE_HISTORY
    return EligibilityState.ELIGIBLE


def _capabilities_for(
    state: EligibilityState,
    role: TimeframeRole,
) -> dict[str, bool]:
    if state is not EligibilityState.ELIGIBLE:
        return {
            "can_compute_features": False,
            "can_score": False,
            "can_train_ml": False,
            "context_only": False,
        }
    if role is TimeframeRole.CONTEXT:
        return {
            "can_compute_features": True,
            "can_score": False,
            "can_train_ml": False,
            "context_only": True,
        }
    return {
        "can_compute_features": True,
        "can_score": True,
        "can_train_ml": True,
        "context_only": False,
    }
