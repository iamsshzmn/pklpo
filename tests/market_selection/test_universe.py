"""
Тесты для universe manager.
"""

import pytest

from src.market_selection.application.config_projection import build_universe_config
from src.market_selection.config import MarketSelectionConfig
from src.market_selection.domain.regime import GlobalRegime, RegimeType
from src.market_selection.domain.scoring import FinalScore
from src.market_selection.domain.universe import (
    UniverseEntry,
    UniverseManager,
    UniverseStatus,
    UniverseVersion,
)


@pytest.fixture
def universe_manager():
    config = build_universe_config(MarketSelectionConfig())
    return UniverseManager(config)


@pytest.fixture
def sample_regime():
    return GlobalRegime(
        regime=RegimeType.TREND_UP,
        strength=0.8,
        confidence=0.9,
        stale=False,
    )


@pytest.fixture
def sample_final_scores():
    return [
        FinalScore("BTC-USDT", 0.9, rank=1, score_4h=0.85, score_1h=0.88),
        FinalScore("ETH-USDT", 0.8, rank=2, score_4h=0.78, score_1h=0.82),
        FinalScore("SOL-USDT", 0.7, rank=3, score_4h=0.68, score_1h=0.72),
    ]


def test_select_universe_basic(universe_manager, sample_final_scores, sample_regime):
    score_history = {
        "BTC-USDT": [0.9, 0.88, 0.91, 0.89, 0.9, 0.88, 0.92, 0.9],
        "ETH-USDT": [0.8, 0.82, 0.79, 0.81, 0.8, 0.82, 0.79, 0.81],
        "SOL-USDT": [0.7, 0.72, 0.69, 0.71, 0.7, 0.72, 0.69, 0.71],
    }

    universe, flags = universe_manager.select_universe(
        final_scores=sample_final_scores,
        score_history=score_history,
        previous_universe=set(),
        regime=sample_regime,
    )

    assert flags == []
    assert universe
    assert all(isinstance(entry, UniverseEntry) for entry in universe)
    assert universe[0].final_score >= universe[-1].final_score


def test_select_universe_respects_blacklist(
    universe_manager, sample_final_scores, sample_regime
):
    universe, _ = universe_manager.select_universe(
        final_scores=sample_final_scores,
        score_history={},
        previous_universe=set(),
        regime=sample_regime,
        blacklist={"ETH-USDT"},
    )

    assert "ETH-USDT" not in {entry.symbol for entry in universe}


def test_select_universe_respects_whitelist(
    universe_manager, sample_final_scores, sample_regime
):
    universe, _ = universe_manager.select_universe(
        final_scores=sample_final_scores,
        score_history={},
        previous_universe=set(),
        regime=sample_regime,
        whitelist={"SOL-USDT"},
    )

    assert "SOL-USDT" in {entry.symbol for entry in universe}


def test_select_universe_hysteresis(
    universe_manager, sample_final_scores, sample_regime
):
    universe, _ = universe_manager.select_universe(
        final_scores=sample_final_scores,
        score_history={},
        previous_universe={"SOL-USDT"},
        regime=sample_regime,
    )

    assert "SOL-USDT" in {entry.symbol for entry in universe}


def test_calculate_stability(universe_manager):
    stable = universe_manager._calculate_stability(
        [0.8, 0.81, 0.79, 0.82, 0.8, 0.81, 0.79],
        min_days=3,
    )
    unstable = universe_manager._calculate_stability(
        [0.8, 0.5, 0.9, 0.3, 0.85, 0.4, 0.9],
        min_days=3,
    )

    assert stable["std_7d"] is not None
    assert stable["std_7d"] < unstable["std_7d"]


def test_check_systemic_outage(universe_manager):
    assert not universe_manager.check_systemic_outage({"1H": 50, "4H": 48}, 50)
    assert universe_manager.check_systemic_outage({"1H": 10, "4H": 12}, 50)
    assert universe_manager.check_systemic_outage({}, 0)


def test_should_fallback(universe_manager):
    assert universe_manager.should_fallback(30) == (False, None)
    assert universe_manager.should_fallback(8)[0] is True
    assert universe_manager.should_fallback(3)[0] is True


def test_create_version(universe_manager, sample_regime):
    universe = [
        UniverseEntry("BTC-USDT", 0.9, 1, score_4h=0.85, score_1h=0.88),
        UniverseEntry("ETH-USDT", 0.8, 2, score_4h=0.78, score_1h=0.82),
    ]

    version = universe_manager.create_version(
        ts_version=1000000,
        ts_eval=1000000,
        universe=universe,
        eligible_counts={"5m": 50, "15m": 48, "1H": 45, "4H": 42},
        regime=sample_regime,
        config_hash="test_hash",
        execution_time=1.5,
    )

    assert isinstance(version, UniverseVersion)
    assert version.status == UniverseStatus.PUBLISHED
    assert version.universe_size == 2
    assert version.global_regime == sample_regime.regime.value


def test_create_entry(universe_manager, sample_regime):
    score = FinalScore(
        symbol="BTC-USDT",
        final_score=0.9,
        rank=1,
        score_4h=0.85,
        score_1h=0.88,
        best_tf="1H",
        worst_tf="5m",
    )

    entry = universe_manager._create_entry(
        score,
        {"std_7d": 0.05, "std_30d": 0.08, "days": 10},
        sample_regime,
    )

    assert isinstance(entry, UniverseEntry)
    assert entry.symbol == "BTC-USDT"
    assert entry.global_regime_at_time == sample_regime.regime.value
