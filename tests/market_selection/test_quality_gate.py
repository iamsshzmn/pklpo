"""
Тесты для quality gate (проверка качества данных).
"""

import pytest

from src.market_selection.config import MarketSelectionConfig
from src.market_selection.domain.quality_gate import (
    DataQualityGate,
    QualityResult,
    ReasonFlag,
)


@pytest.fixture
def config():
    """Фикстура конфигурации."""
    return MarketSelectionConfig()


@pytest.fixture
def quality_gate(config):
    """Фикстура quality gate."""
    return DataQualityGate(config)


def test_quality_gate_eligible_all_pass(quality_gate):
    """Тест: все проверки пройдены, символ eligible."""
    result = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=1000,
        expected_bars=1000,
        gaps_count=0,  # Нет пропусков для высокого quality_score
        data_lag_seconds=60,
        volume_present=True,
    )

    assert result.eligible is True
    assert result.fill_rate == pytest.approx(1.0)
    assert result.gap_rate == pytest.approx(0.0)
    assert result.quality_score > 0.9
    assert len(result.reason_flags) == 0


def test_quality_gate_low_fill(quality_gate):
    """Тест: низкий fill_rate приводит к исключению."""
    result = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=500,
        expected_bars=1000,  # fill_rate = 0.5 < 0.99
        gaps_count=0,
        data_lag_seconds=60,
        volume_present=True,
    )

    assert result.eligible is False
    assert result.fill_rate == pytest.approx(0.5)
    assert ReasonFlag.LOW_FILL in result.reason_flags


def test_quality_gate_high_gaps(quality_gate):
    """Тест: высокий gap_rate приводит к исключению."""
    result = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=1000,
        expected_bars=1000,
        gaps_count=20,  # gap_rate = 0.02 > 0.005
        data_lag_seconds=60,
        volume_present=True,
    )

    assert result.eligible is False
    assert ReasonFlag.HIGH_GAPS in result.reason_flags


def test_quality_gate_insufficient_warmup(quality_gate):
    """Тест: недостаточное количество баров для warmup."""
    result = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=100,  # < warmup_min_bars (280)
        expected_bars=1000,
        gaps_count=0,
        data_lag_seconds=60,
        volume_present=True,
    )

    assert result.eligible is False
    assert ReasonFlag.INSUFFICIENT_WARMUP in result.reason_flags


def test_quality_gate_no_volume(quality_gate):
    """Тест: отсутствие volume приводит к исключению."""
    result = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=1000,
        expected_bars=1000,
        gaps_count=0,
        data_lag_seconds=60,
        volume_present=False,
    )

    assert result.eligible is False
    assert ReasonFlag.NO_VOLUME in result.reason_flags


def test_quality_gate_stale_data(quality_gate):
    """Тест: устаревшие данные приводят к исключению."""
    result = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=1000,
        expected_bars=1000,
        gaps_count=0,
        data_lag_seconds=200 * 60,  # > lag_max_min (180 минут)
        volume_present=True,
    )

    assert result.eligible is False
    assert ReasonFlag.STALE_DATA in result.reason_flags


def test_quality_gate_quality_score_calculation(quality_gate):
    """Тест расчета quality_score."""
    # Идеальный случай
    result1 = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=1000,
        expected_bars=1000,
        gaps_count=0,
        data_lag_seconds=60,
        volume_present=True,
    )
    assert result1.quality_score == pytest.approx(1.0, abs=0.01)

    # Граничный случай: fill_rate на минимуме
    result2 = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=990,
        expected_bars=1000,  # fill_rate = 0.99 (минимум)
        gaps_count=0,
        data_lag_seconds=60,
        volume_present=True,
    )
    assert result2.quality_score == pytest.approx(0.0, abs=0.1)

    # Граничный случай: gap_rate на максимуме
    result3 = quality_gate.evaluate(
        symbol="BTC-USDT",
        timeframe="1H",
        valid_bars=1000,
        expected_bars=1000,
        gaps_count=5,  # gap_rate = 0.005 (максимум)
        data_lag_seconds=60,
        volume_present=True,
    )
    assert result3.quality_score == pytest.approx(0.0, abs=0.1)


def test_quality_gate_calculate_expected_bars(quality_gate):
    """Тест расчета ожидаемого количества баров."""
    expected = quality_gate.calculate_expected_bars("1H", 30)
    # 30 дней * 24 часа = 720 баров
    assert expected == 720

    expected_5m = quality_gate.calculate_expected_bars("5m", 1)
    # 1 день * 24 часа * 12 баров в час = 288 баров
    assert expected_5m == 288


def test_quality_gate_detect_gaps(quality_gate):
    """Тест обнаружения пропусков в данных."""
    # Нет пропусков (1m = 60000 мс, threshold = 60000 * 1.5 = 90000)
    timestamps1 = [1000, 61000, 121000, 181000]  # интервалы 60 секунд
    gaps1 = quality_gate.detect_gaps(timestamps1, "1m")
    assert gaps1 == 0

    # Есть пропуск (delta > threshold)
    # 1m = 60000 мс, threshold = 60000 * 1.5 = 90000 мс
    timestamps2 = [
        1000,
        61000,
        200000,
        261000,
    ]  # пропуск между 61000 и 200000 (139000 > 90000)
    gaps2 = quality_gate.detect_gaps(timestamps2, "1m")
    assert gaps2 >= 1

    # Пустой список
    gaps3 = quality_gate.detect_gaps([], "1m")
    assert gaps3 == 0

    # Один элемент
    gaps4 = quality_gate.detect_gaps([1000], "1m")
    assert gaps4 == 0


def test_quality_gate_batch_evaluate(quality_gate):
    """Тест пакетной оценки качества."""
    quality_data = [
        {
            "symbol": "BTC-USDT",
            "timeframe": "1H",
            "valid_bars": 1000,
            "expected_bars": 1000,
            "gaps_count": 0,
            "data_lag_seconds": 60,
            "volume_present": True,
        },
        {
            "symbol": "ETH-USDT",
            "timeframe": "1H",
            "valid_bars": 500,
            "expected_bars": 1000,
            "gaps_count": 0,
            "data_lag_seconds": 60,
            "volume_present": True,
        },
    ]

    results = quality_gate.batch_evaluate(quality_data)
    assert len(results) == 2
    assert results[0].eligible is True
    assert results[1].eligible is False


def test_quality_gate_summarize_results(quality_gate):
    """Тест сводной статистики результатов."""
    results = [
        QualityResult(
            symbol="BTC-USDT",
            timeframe="1H",
            fill_rate=1.0,
            gap_rate=0.0,
            data_lag_seconds=60,
            valid_bars=1000,
            expected_bars=1000,
            eligible=True,
            quality_score=1.0,
        ),
        QualityResult(
            symbol="ETH-USDT",
            timeframe="1H",
            fill_rate=0.5,
            gap_rate=0.0,
            data_lag_seconds=60,
            valid_bars=500,
            expected_bars=1000,
            eligible=False,
            quality_score=0.0,
            reason_flags=[ReasonFlag.LOW_FILL],
        ),
    ]

    summary = quality_gate.summarize_results(results)
    assert summary["total"] == 2
    assert summary["eligible"] == 1
    assert summary["ineligible"] == 1
    assert summary["avg_quality_score"] == pytest.approx(1.0)
    assert summary["reason_counts"]["LOW_FILL"] == 1

    # Пустой список
    empty_summary = quality_gate.summarize_results([])
    assert empty_summary["total"] == 0
    assert empty_summary["eligible"] == 0
