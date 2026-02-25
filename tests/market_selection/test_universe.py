"""
Тесты для universe manager (управление вселенной торговых пар).
"""

import pytest

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
def config():
    """Фикстура конфигурации."""
    return MarketSelectionConfig()


@pytest.fixture
def universe_manager(config):
    """Фикстура universe manager."""
    return UniverseManager(config)


@pytest.fixture
def sample_regime():
    """Фикстура примера режима."""
    return GlobalRegime(
        regime=RegimeType.TREND_UP,
        strength=0.8,
        confidence=0.9,
        stale=False,
    )


@pytest.fixture
def sample_final_scores():
    """Фикстура примеров финальных оценок."""
    return [
        FinalScore(
            symbol="BTC-USDT",
            final_score=0.9,
            rank=1,
            score_4h=0.85,
            score_1h=0.88,
            score_15m=0.82,
            score_5m=0.80,
            best_tf="1H",
            worst_tf="5m",
        ),
        FinalScore(
            symbol="ETH-USDT",
            final_score=0.8,
            rank=2,
            score_4h=0.78,
            score_1h=0.82,
            score_15m=0.75,
            score_5m=0.73,
            best_tf="1H",
            worst_tf="5m",
        ),
        FinalScore(
            symbol="SOL-USDT",
            final_score=0.7,
            rank=3,
            score_4h=0.68,
            score_1h=0.72,
            score_15m=0.65,
            score_5m=0.63,
            best_tf="1H",
            worst_tf="5m",
        ),
    ]


def test_select_universe_basic(universe_manager, sample_final_scores, sample_regime):
    """Тест базового выбора вселенной."""
    # Добавляем историю для прохождения проверки стабильности
    score_history = {
        "BTC-USDT": [0.9, 0.88, 0.91, 0.89, 0.9, 0.88, 0.92, 0.9],  # 8 дней
        "ETH-USDT": [0.8, 0.82, 0.79, 0.81, 0.8, 0.82, 0.79, 0.81],  # 8 дней
        "SOL-USDT": [0.7, 0.72, 0.69, 0.71, 0.7, 0.72, 0.69, 0.71],  # 8 дней
    }

    universe, flags = universe_manager.select_universe(
        final_scores=sample_final_scores,
        score_history=score_history,
        previous_universe=set(),
        regime=sample_regime,
    )

    assert len(universe) > 0
    assert all(isinstance(entry, UniverseEntry) for entry in universe)
    # Символы должны быть отсортированы по final_score
    assert universe[0].final_score >= universe[-1].final_score


def test_select_universe_top_n(universe_manager, sample_final_scores, sample_regime):
    """Тест выбора top-N символов."""
    # Создаем больше символов
    extended_scores = sample_final_scores + [
        FinalScore(symbol=f"SYM-{i}", final_score=0.5 - i * 0.01, rank=4 + i)
        for i in range(50)
    ]

    universe, _ = universe_manager.select_universe(
        final_scores=extended_scores,
        score_history={},
        previous_universe=set(),
        regime=sample_regime,
    )

    # Должно быть выбрано top_n (30) символов
    assert (
        len(universe)
        <= universe_manager.universe_config.top_n
        + universe_manager.universe_config.buffer
    )


def test_select_universe_blacklist(
    universe_manager, sample_final_scores, sample_regime
):
    """Тест исключения символов из blacklist."""
    blacklist = {"ETH-USDT"}

    universe, _ = universe_manager.select_universe(
        final_scores=sample_final_scores,
        score_history={},
        previous_universe=set(),
        regime=sample_regime,
        blacklist=blacklist,
    )

    symbols = {entry.symbol for entry in universe}
    assert "ETH-USDT" not in symbols


def test_select_universe_whitelist(
    universe_manager, sample_final_scores, sample_regime
):
    """Тест приоритета символов из whitelist."""
    whitelist = {"SOL-USDT"}

    universe, _ = universe_manager.select_universe(
        final_scores=sample_final_scores,
        score_history={},
        previous_universe=set(),
        regime=sample_regime,
        whitelist=whitelist,
    )

    symbols = {entry.symbol for entry in universe}
    # Whitelist символ должен быть включен, если он eligible
    assert "SOL-USDT" in symbols


def test_select_universe_hysteresis(
    universe_manager, sample_final_scores, sample_regime
):
    """Тест гистерезиса (приоритет предыдущей вселенной)."""
    previous_universe = {"SOL-USDT"}

    universe, _ = universe_manager.select_universe(
        final_scores=sample_final_scores,
        score_history={},
        previous_universe=previous_universe,
        regime=sample_regime,
    )

    symbols = {entry.symbol for entry in universe}
    # SOL-USDT должен быть включен благодаря гистерезису
    assert "SOL-USDT" in symbols


def test_calculate_stability(universe_manager):
    """Тест расчета стабильности оценок."""
    # Стабильная история
    stable_history = [0.8, 0.81, 0.79, 0.82, 0.8, 0.81, 0.79]
    stability = universe_manager._calculate_stability(stable_history, min_days=3)

    assert stability["std_7d"] is not None
    assert stability["std_7d"] < 0.05  # Низкое стандартное отклонение

    # Нестабильная история
    unstable_history = [0.8, 0.5, 0.9, 0.3, 0.85, 0.4, 0.9]
    stability_unstable = universe_manager._calculate_stability(
        unstable_history, min_days=3
    )

    assert stability_unstable["std_7d"] is not None
    assert stability_unstable["std_7d"] > stability["std_7d"]


def test_check_systemic_outage(universe_manager):
    """Тест проверки системного сбоя старших таймфреймов."""
    # Нормальная ситуация
    eligible_counts_normal = {"1H": 50, "4H": 48}
    assert not universe_manager.check_systemic_outage(
        eligible_counts_normal, total_symbols=50
    )

    # Системный сбой (>30% отсутствуют)
    eligible_counts_outage = {"1H": 10, "4H": 12}  # 20/50 = 40% отсутствуют
    assert universe_manager.check_systemic_outage(
        eligible_counts_outage, total_symbols=50
    )


def test_should_fallback(universe_manager):
    """Тест проверки необходимости fallback."""
    # Нормальный размер
    should, reason = universe_manager.should_fallback(30)
    assert should is False
    assert reason is None

    # Мягкий минимум
    should, reason = universe_manager.should_fallback(8)
    assert should is True
    assert reason is not None

    # Жесткий минимум
    should, reason = universe_manager.should_fallback(3)
    assert should is True
    assert reason is not None


def test_create_version(universe_manager, sample_regime):
    """Тест создания версии вселенной."""
    universe = [
        UniverseEntry(
            symbol="BTC-USDT",
            final_score=0.9,
            rank=1,
            score_4h=0.85,
            score_1h=0.88,
        ),
        UniverseEntry(
            symbol="ETH-USDT",
            final_score=0.8,
            rank=2,
            score_4h=0.78,
            score_1h=0.82,
        ),
    ]

    eligible_counts = {"5m": 50, "15m": 48, "1H": 45, "4H": 42}

    version = universe_manager.create_version(
        ts_version=1000000,
        ts_eval=1000000,
        universe=universe,
        eligible_counts=eligible_counts,
        regime=sample_regime,
        config_hash="test_hash",
        execution_time=1.5,
    )

    assert isinstance(version, UniverseVersion)
    assert version.ts_version == 1000000
    assert version.universe_size == 2
    assert version.eligible_count == sum(eligible_counts.values())
    assert version.status == UniverseStatus.PUBLISHED
    assert version.global_regime == sample_regime.regime.value


def test_create_entry(universe_manager, sample_regime):
    """Тест создания записи вселенной."""
    final_score = FinalScore(
        symbol="BTC-USDT",
        final_score=0.9,
        rank=1,
        score_4h=0.85,
        score_1h=0.88,
        best_tf="1H",
        worst_tf="5m",
    )

    stability = {"std_7d": 0.05, "std_30d": 0.08, "days": 10}

    entry = universe_manager._create_entry(final_score, stability, sample_regime)

    assert isinstance(entry, UniverseEntry)
    assert entry.symbol == "BTC-USDT"
    assert entry.final_score == 0.9
    assert entry.score_std_7d == 0.05
    assert entry.global_regime_at_time == sample_regime.regime.value
