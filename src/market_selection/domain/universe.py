"""
Universe Manager for Market Selection

Manages the trading universe:
- Top-N selection with buffer for hysteresis
- Score stability checks (std over 7d/30d)
- Fallback to previous universe on failures
- White/black list handling
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from .quality_gate import ReasonFlag

if TYPE_CHECKING:
    from .config import UniverseConfig
    from .regime import GlobalRegime
    from .scoring import FinalScore


class UniverseStatus(StrEnum):
    """Status of a universe version."""

    BUILDING = "building"
    PUBLISHED = "published"
    FAILED = "failed"
    FALLBACK_PREV = "fallback_prev"


@dataclass
class UniverseVersion:
    """Metadata for a universe version."""

    ts_version: int  # milliseconds
    ts_eval: int  # milliseconds
    status: UniverseStatus
    universe_size: int
    eligible_count: int
    config_hash: str

    # Per-TF eligible counts
    eligible_5m: int = 0
    eligible_15m: int = 0
    eligible_1h: int = 0
    eligible_4h: int = 0

    # Regime at evaluation
    global_regime: str | None = None
    global_strength: float | None = None

    # Quality metrics
    avg_quality_score: float = 0.0
    min_final_score: float = 0.0
    max_final_score: float = 0.0

    # Fallback info
    source_version: int | None = None
    fallback_reason: str | None = None

    # Execution info
    execution_time_seconds: float = 0.0
    notes: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "ts_version": self.ts_version,
            "ts_eval": self.ts_eval,
            "status": self.status.value,
            "universe_size": self.universe_size,
            "eligible_count": self.eligible_count,
            "eligible_5m": self.eligible_5m,
            "eligible_15m": self.eligible_15m,
            "eligible_1h": self.eligible_1h,
            "eligible_4h": self.eligible_4h,
            "global_regime": self.global_regime,
            "global_strength": self.global_strength,
            "avg_quality_score": self.avg_quality_score,
            "min_final_score": self.min_final_score,
            "max_final_score": self.max_final_score,
            "source_version": self.source_version,
            "fallback_reason": self.fallback_reason,
            "config_hash": self.config_hash,
            "execution_time_seconds": self.execution_time_seconds,
            "notes": self.notes,
        }


@dataclass
class UniverseEntry:
    """A single symbol in the universe."""

    symbol: str
    final_score: float
    rank: int

    # Per-TF scores
    score_4h: float | None = None
    score_1h: float | None = None
    score_15m: float | None = None
    score_5m: float | None = None
    best_tf: str | None = None
    worst_tf: str | None = None

    # Stability
    score_std_7d: float | None = None
    score_std_30d: float | None = None
    days_in_universe: int = 0

    # Regime at time
    global_regime_at_time: str | None = None
    global_strength_at_time: float | None = None

    # Flags
    reason_flags: list[ReasonFlag] = field(default_factory=list)
    penalty_applied: float = 0.0

    # Versioning
    config_hash: str = ""
    source_version: int | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "symbol": self.symbol,
            "final_score": self.final_score,
            "rank": self.rank,
            "score_4h": self.score_4h,
            "score_1h": self.score_1h,
            "score_15m": self.score_15m,
            "score_5m": self.score_5m,
            "best_tf": self.best_tf,
            "worst_tf": self.worst_tf,
            "score_std_7d": self.score_std_7d,
            "score_std_30d": self.score_std_30d,
            "days_in_universe": self.days_in_universe,
            "global_regime_at_time": self.global_regime_at_time,
            "global_strength_at_time": self.global_strength_at_time,
            "reason_flags": [f.value for f in self.reason_flags],
            "penalty_applied": self.penalty_applied,
            "config_hash": self.config_hash,
            "source_version": self.source_version,
        }


class UniverseManager:
    """
    Manages trading universe selection and versioning.

    Features:
    - Top-N selection with buffer for smooth transitions
    - Score stability requirements (low std over time)
    - Hysteresis: symbols in previous universe get priority
    - Fallback to previous version on failures
    - White/black list support
    """

    def __init__(self, config: UniverseConfig):
        self.config = config

    def select_universe(
        self,
        final_scores: list[FinalScore],
        score_history: dict[str, list[float]],
        previous_universe: set[str],
        regime: GlobalRegime,
        whitelist: set[str] | None = None,
        blacklist: set[str] | None = None,
    ) -> tuple[list[UniverseEntry], list[ReasonFlag]]:
        """
        Select trading universe from scored symbols.

        Args:
            final_scores: List of FinalScore objects, sorted by score desc
            score_history: Dict[symbol -> list of historical scores]
            previous_universe: Symbols in previous universe version
            regime: Current global regime
            whitelist: Symbols to force-include (if eligible)
            blacklist: Symbols to force-exclude

        Returns:
            Tuple of (universe entries, global flags)
        """
        whitelist = whitelist or set()
        blacklist = blacklist or set()
        global_flags: list[ReasonFlag] = []

        top_n = self.config.top_n
        buffer = self.config.buffer
        std_7d_max = self.config.score_std_7d_max
        std_30d_max = self.config.score_std_30d_max
        min_history_days = self.config.min_history_days

        # Filter blacklisted
        candidates = [s for s in final_scores if s.symbol not in blacklist]

        # Calculate stability metrics
        stability_data: dict[str, dict] = {}
        for score in candidates:
            history = score_history.get(score.symbol, [])
            stability_data[score.symbol] = self._calculate_stability(
                history, min_history_days
            )

        # Categorize candidates
        primary_candidates = []  # Meet all criteria
        buffer_candidates = []  # In buffer zone or have flags

        for score in candidates:
            symbol = score.symbol
            stability = stability_data[symbol]

            # Check stability criteria
            meets_std_7d = (
                stability["std_7d"] is None or stability["std_7d"] <= std_7d_max
            )
            meets_std_30d = (
                stability["std_30d"] is None or stability["std_30d"] <= std_30d_max
            )
            has_history = stability["days"] >= min_history_days

            # Check for critical flags
            has_critical_flags = any(
                f in score.reason_flags
                for f in [ReasonFlag.MISSING_SENIOR_TF, ReasonFlag.STALE_DATA]
            )

            # Whitelist gets priority
            if symbol in whitelist:
                if not has_critical_flags:
                    primary_candidates.append((score, stability, True))
                continue

            # Primary: meets all criteria
            if meets_std_7d and meets_std_30d and not has_critical_flags:
                if has_history:
                    primary_candidates.append((score, stability, False))
                else:
                    # Short history - buffer only
                    buffer_candidates.append((score, stability, False))
                    score.reason_flags.append(ReasonFlag.SHORT_HISTORY)
            else:
                buffer_candidates.append((score, stability, False))

        # Select top-N from primary
        selected = []
        for score, stability, _is_whitelist in primary_candidates[:top_n]:
            entry = self._create_entry(score, stability, regime)
            selected.append(entry)

        # Hysteresis: if a symbol was in previous universe and is in buffer,
        # allow it to stay if within top-(N+buffer)
        remaining_slots = top_n - len(selected)
        buffer_added = 0

        if remaining_slots > 0:
            for score, stability, _ in buffer_candidates:
                if buffer_added >= buffer:
                    break

                # Hysteresis: previous universe members get priority
                if score.symbol in previous_universe:
                    entry = self._create_entry(score, stability, regime)
                    selected.append(entry)
                    buffer_added += 1

        # Fill remaining from primary if we have space
        if len(selected) < top_n:
            for score, stability, _ in primary_candidates[top_n:]:
                if len(selected) >= top_n + buffer:
                    break
                if score.symbol not in {s.symbol for s in selected}:
                    entry = self._create_entry(score, stability, regime)
                    selected.append(entry)

        # Re-sort and re-rank
        selected.sort(key=lambda x: x.final_score, reverse=True)
        for i, entry in enumerate(selected):
            entry.rank = i + 1

        return selected, global_flags

    def _calculate_stability(
        self,
        history: list[float],
        min_days: int,
    ) -> dict:
        """Calculate score stability metrics from history."""
        import numpy as np

        result = {
            "std_7d": None,
            "std_30d": None,
            "days": len(history),
        }

        if len(history) < 2:
            return result

        # Assume history is ordered newest-first
        # Take last 7 and 30 entries (approximating days)
        hist_7d = history[:7] if len(history) >= 7 else history
        hist_30d = history[:30] if len(history) >= 30 else history

        if len(hist_7d) >= 2:
            result["std_7d"] = float(np.std(hist_7d))

        if len(hist_30d) >= 2:
            result["std_30d"] = float(np.std(hist_30d))

        return result

    def _create_entry(
        self,
        score: FinalScore,
        stability: dict,
        regime: GlobalRegime,
    ) -> UniverseEntry:
        """Create a UniverseEntry from FinalScore and stability data."""
        return UniverseEntry(
            symbol=score.symbol,
            final_score=score.final_score,
            rank=score.rank,
            score_4h=score.score_4h,
            score_1h=score.score_1h,
            score_15m=score.score_15m,
            score_5m=score.score_5m,
            best_tf=score.best_tf,
            worst_tf=score.worst_tf,
            score_std_7d=stability.get("std_7d"),
            score_std_30d=stability.get("std_30d"),
            days_in_universe=0,  # Will be updated from history
            global_regime_at_time=regime.regime.value,
            global_strength_at_time=regime.strength,
            reason_flags=score.reason_flags.copy(),
            penalty_applied=score.penalty_applied,
        )

    def check_systemic_outage(
        self,
        eligible_counts: dict[str, int],
        total_symbols: int,
    ) -> bool:
        """
        Check if there's a systemic outage of senior TFs.

        Returns True if > 30% of symbols are missing 1H or 4H data.
        """
        threshold = self.config.systemic_senior_outage_threshold

        if total_symbols == 0:
            return True

        eligible_1h = eligible_counts.get("1H", 0)
        eligible_4h = eligible_counts.get("4H", 0)

        missing_1h_pct = 1.0 - (eligible_1h / total_symbols)
        missing_4h_pct = 1.0 - (eligible_4h / total_symbols)

        return bool(missing_1h_pct > threshold or missing_4h_pct > threshold)

    def should_fallback(
        self,
        universe_size: int,
    ) -> tuple[bool, str | None]:
        """
        Check if we should fallback to previous universe.

        Returns (should_fallback, reason)
        """
        hard_min = self.config.min_universe_hard
        soft_min = self.config.min_universe_soft

        if universe_size < hard_min:
            return True, f"universe_size ({universe_size}) < hard_min ({hard_min})"

        if universe_size < soft_min:
            return True, f"universe_size ({universe_size}) < soft_min ({soft_min})"

        return False, None

    def create_version(
        self,
        ts_version: int,
        ts_eval: int,
        universe: list[UniverseEntry],
        eligible_counts: dict[str, int],
        regime: GlobalRegime,
        config_hash: str,
        execution_time: float,
        status: UniverseStatus = UniverseStatus.PUBLISHED,
        source_version: int | None = None,
        fallback_reason: str | None = None,
    ) -> UniverseVersion:
        """Create a UniverseVersion metadata object."""
        scores = [e.final_score for e in universe]

        return UniverseVersion(
            ts_version=ts_version,
            ts_eval=ts_eval,
            status=status,
            universe_size=len(universe),
            eligible_count=sum(eligible_counts.values()),
            eligible_5m=eligible_counts.get("5m", 0),
            eligible_15m=eligible_counts.get("15m", 0),
            eligible_1h=eligible_counts.get("1H", 0),
            eligible_4h=eligible_counts.get("4H", 0),
            global_regime=regime.regime.value,
            global_strength=regime.strength,
            avg_quality_score=sum(scores) / len(scores) if scores else 0.0,
            min_final_score=min(scores) if scores else 0.0,
            max_final_score=max(scores) if scores else 0.0,
            source_version=source_version,
            fallback_reason=fallback_reason,
            config_hash=config_hash,
            execution_time_seconds=execution_time,
        )
