"""
Unit tests for Market Selection Universe Manager.

Covers: select_universe (top-N, buffer, score_std_7d/30d, SHORT_HISTORY),
whitelist/blacklist, should_fallback (min_universe_hard/soft), check_systemic_outage.
"""

from __future__ import annotations

import pytest

from src.market_selection.domain.regime import GlobalRegime, RegimeType
from src.market_selection.domain.scoring import FinalScore
from src.market_selection.domain.universe import UniverseManager


def make_final_scores(symbols: list[str], base_score: float = 0.7) -> list[FinalScore]:
    """Build list of FinalScore with descending scores."""
    scores = []
    for i, sym in enumerate(symbols):
        s = FinalScore(
            symbol=sym,
            final_score=base_score - i * 0.01,
            rank=i + 1,
            score_4h=0.7,
            score_1h=0.7,
            score_15m=0.7,
            score_5m=0.7,
            best_tf="4H",
            worst_tf="5m",
            penalty_applied=0.0,
            reason_flags=[],
        )
        scores.append(s)
    return scores


def make_regime(regime: RegimeType = RegimeType.RANGE) -> GlobalRegime:
    """Minimal GlobalRegime for tests."""
    return GlobalRegime(
        regime=regime,
        strength=0.5,
        confidence=0.7,
        stale=False,
        tf_regimes={},
        basket_symbols=[],
        basket_size=0,
    )


class TestSelectUniverse:
    """Tests for UniverseManager.select_universe()."""

    def test_top_n_selection(
        self,
        universe_manager: UniverseManager,
    ) -> None:
        """Selects top-N by final_score when all meet stability."""
        symbols = [f"S{i}" for i in range(50)]
        scores = make_final_scores(symbols)
        score_history = {s: [0.7] * 10 for s in symbols}
        regime = make_regime()
        entries, flags = universe_manager.select_universe(
            final_scores=scores,
            score_history=score_history,
            previous_universe=set(),
            regime=regime,
            whitelist=set(),
            blacklist=set(),
        )
        assert (
            len(entries)
            <= universe_manager.config.top_n + universe_manager.config.buffer
        )
        if entries:
            assert entries[0].rank == 1
            assert entries[0].final_score >= (
                entries[-1].final_score if len(entries) > 1 else 0
            )

    def test_blacklist_excluded(
        self,
        universe_manager: UniverseManager,
    ) -> None:
        """Blacklisted symbols are not in universe."""
        symbols = ["A", "B", "C", "D", "E"]
        scores = make_final_scores(symbols)
        score_history = {s: [0.7] * 10 for s in symbols}
        regime = make_regime()
        entries, _ = universe_manager.select_universe(
            final_scores=scores,
            score_history=score_history,
            previous_universe=set(),
            regime=regime,
            whitelist=set(),
            blacklist={"B", "D"},
        )
        entry_symbols = {e.symbol for e in entries}
        assert "B" not in entry_symbols
        assert "D" not in entry_symbols

    def test_whitelist_included(
        self,
        universe_manager: UniverseManager,
    ) -> None:
        """Whitelisted symbol that meets stability is in primary_candidates and can be selected."""
        symbols = [f"S{i}" for i in range(25)]
        scores = make_final_scores(symbols, base_score=0.8)
        score_history = {s: [0.7] * 10 for s in symbols}
        regime = make_regime()
        whitelist = {"WHITE"}
        # WHITE с высоким score попадает в top-N (после сортировки по score desc)
        scores_plus = scores + [
            FinalScore(
                symbol="WHITE",
                final_score=0.82,
                rank=26,
                score_4h=0.8,
                score_1h=0.8,
                score_15m=0.8,
                score_5m=0.8,
                best_tf="4H",
                worst_tf="5m",
                penalty_applied=0.0,
                reason_flags=[],
            )
        ]
        scores_plus.sort(key=lambda s: s.final_score, reverse=True)
        entries, _ = universe_manager.select_universe(
            final_scores=scores_plus,
            score_history={**score_history, "WHITE": [0.8] * 10},
            previous_universe=set(),
            regime=regime,
            whitelist=whitelist,
            blacklist=set(),
        )
        entry_symbols = {e.symbol for e in entries}
        assert "WHITE" in entry_symbols


class TestShouldFallback:
    """Tests for UniverseManager.should_fallback()."""

    def test_fallback_when_below_soft_min(
        self,
        universe_manager: UniverseManager,
    ) -> None:
        """universe_size < min_universe_soft (10) -> should_fallback True."""
        should, reason = universe_manager.should_fallback(8)
        assert should is True
        assert reason is not None
        assert "soft_min" in reason or "10" in reason

    def test_fallback_when_below_hard_min(
        self,
        universe_manager: UniverseManager,
    ) -> None:
        """universe_size < min_universe_hard (5) -> should_fallback True."""
        should, reason = universe_manager.should_fallback(3)
        assert should is True
        assert reason is not None

    def test_no_fallback_when_above_soft_min(
        self,
        universe_manager: UniverseManager,
    ) -> None:
        """universe_size >= min_universe_soft -> should_fallback False."""
        should, reason = universe_manager.should_fallback(15)
        assert should is False
        assert reason is None


class TestCheckSystemicOutage:
    """Tests for UniverseManager.check_systemic_outage()."""

    def test_outage_when_many_missing_1h(
        self,
        universe_manager: UniverseManager,
    ) -> None:
        """>30% missing 1H -> systemic outage True."""
        eligible_counts = {"5m": 100, "15m": 95, "1H": 60, "4H": 90}
        total_symbols = 100
        assert (
            universe_manager.check_systemic_outage(eligible_counts, total_symbols)
            is True
        )

    def test_outage_when_many_missing_4h(
        self,
        universe_manager: UniverseManager,
    ) -> None:
        """>30% missing 4H -> systemic outage True."""
        eligible_counts = {"5m": 100, "15m": 95, "1H": 95, "4H": 65}
        total_symbols = 100
        assert (
            universe_manager.check_systemic_outage(eligible_counts, total_symbols)
            is True
        )

    def test_no_outage_when_senior_tf_ok(
        self,
        universe_manager: UniverseManager,
    ) -> None:
        """1H and 4H both >= 70% -> no systemic outage."""
        eligible_counts = {"5m": 100, "15m": 95, "1H": 80, "4H": 85}
        total_symbols = 100
        assert (
            universe_manager.check_systemic_outage(eligible_counts, total_symbols)
            is False
        )

    def test_outage_when_total_zero(
        self,
        universe_manager: UniverseManager,
    ) -> None:
        """total_symbols == 0 -> outage True."""
        assert universe_manager.check_systemic_outage({}, 0) is True


class TestCreateVersion:
    """Tests for UniverseManager.create_version()."""

    def test_create_version_metadata(
        self,
        universe_manager: UniverseManager,
    ) -> None:
        """create_version returns UniverseVersion with correct fields."""
        from src.market_selection.domain.universe import UniverseEntry

        universe = [
            UniverseEntry(symbol="A", final_score=0.8, rank=1),
            UniverseEntry(symbol="B", final_score=0.7, rank=2),
        ]
        eligible_counts = {"5m": 50, "15m": 48, "1H": 45, "4H": 45}
        regime = make_regime()
        version = universe_manager.create_version(
            ts_version=1000000,
            ts_eval=1000000,
            universe=universe,
            eligible_counts=eligible_counts,
            regime=regime,
            config_hash="abc123",
            execution_time=1.5,
        )
        assert version.ts_version == 1000000
        assert version.universe_size == 2
        assert version.eligible_5m == 50
        assert version.eligible_1h == 45
        assert version.eligible_4h == 45
        assert version.config_hash == "abc123"
        assert version.avg_quality_score == pytest.approx(0.75)
        assert version.min_final_score == 0.7
        assert version.max_final_score == 0.8
