"""Application-layer state and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..domain.quality_gate import QualityResult, ReasonFlag
    from ..domain.regime import RegimeType
    from ..domain.universe import UniverseStatus


@dataclass
class PipelineResult:
    """Result of market selection pipeline run."""

    success: bool
    ts_version: int
    ts_eval: int
    universe_size: int
    status: UniverseStatus
    global_regime: RegimeType | None = None
    eligible_counts: dict[str, int] = field(default_factory=dict)
    total_symbols: int = 0
    execution_time_seconds: float = 0.0
    error_message: str | None = None
    reason_flags: list[ReasonFlag] = field(default_factory=list)
    config_hash: str = ""


@dataclass
class PipelineRunContext:
    """Mutable runtime state for a single pipeline execution."""

    start_time: float
    config_hash: str
    ts_eval: int = 0
    ts_version: int = 0

    def elapsed(self, now: float) -> float:
        """Return elapsed execution time."""
        return now - self.start_time


@dataclass
class TimeframeProcessingState:
    """Accumulated intermediate artifacts across selection timeframes."""

    tf_scores: dict[str, dict[str, float]] = field(default_factory=dict)
    eligible_counts: dict[str, int] = field(default_factory=dict)
    quality_results: dict[str, dict[str, QualityResult]] = field(default_factory=dict)
    metrics_raw: dict[str, dict[str, dict]] = field(default_factory=dict)
    total_symbols: int = 0
