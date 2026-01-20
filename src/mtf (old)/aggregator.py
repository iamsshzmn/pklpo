from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextResult:
    score_1d: float | None
    score_4h: float | None
    context_score: float | None
    bias: str  # long/short/neutral


def aggregate_context(score_1d: float | None, score_4h: float | None) -> ContextResult:
    if score_1d is None or score_4h is None:
        return ContextResult(score_1d, score_4h, None, "neutral")
    context_score = 0.6 * float(score_1d) + 0.4 * float(score_4h)
    bias = "neutral"
    if context_score >= 0.3:
        bias = "long"
    elif context_score <= -0.3:
        bias = "short"
    return ContextResult(score_1d, score_4h, context_score, bias)


def determine_bias_and_consensus(
    bias: str, p_up: float, p_down: float, threshold: float = 0.6
) -> int:
    """Return consensus: 1 (LONG), -1 (SHORT), 0 (FLAT) per rules.
    Conflicting case resolves to FLAT by construction of rules.
    """
    if bias == "long" and p_up >= threshold:
        return 1
    if bias == "short" and p_down >= threshold:
        return -1
    return 0
