#!/usr/bin/env python3
"""
Простой тест для Scoring Engine
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.scoring_engine.compute import ScoringEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_normalization():
    """Тест нормализации значений"""
    engine = ScoringEngine()

    # Тест RSI
    rsi_50 = engine.normalize_value(50, "rsi14")
    rsi_0 = engine.normalize_value(0, "rsi14")
    rsi_100 = engine.normalize_value(100, "rsi14")

    logger.info(
        f"RSI нормализация: 50->{rsi_50:.4f}, 0->{rsi_0:.4f}, 100->{rsi_100:.4f}"
    )

    assert rsi_50 == 0.5, f"RSI(50) должен быть 0.5, получено: {rsi_50}"
    assert rsi_0 == 0.0, f"RSI(0) должен быть 0.0, получено: {rsi_0}"
    assert rsi_100 == 1.0, f"RSI(100) должен быть 1.0, получено: {rsi_100}"

    # Тест MACD
    macd_0 = engine.normalize_value(0, "macd_histogram")
    macd_neg = engine.normalize_value(-0.01, "macd_histogram")
    macd_pos = engine.normalize_value(0.01, "macd_histogram")

    logger.info(
        f"MACD нормализация: 0->{macd_0:.4f}, -0.01->{macd_neg:.4f}, 0.01->{macd_pos:.4f}"
    )

    assert macd_0 == 0.5, f"MACD(0) должен быть 0.5, получено: {macd_0}"
    assert macd_neg == 0.0, f"MACD(-0.01) должен быть 0.0, получено: {macd_neg}"
    assert macd_pos == 1.0, f"MACD(0.01) должен быть 1.0, получено: {macd_pos}"

    logger.info("✅ Тест нормализации пройден")


def test_indicator_value():
    """Тест извлечения значений индикаторов"""
    engine = ScoringEngine()

    # Тестовые данные
    indicator_data = {
        "rsi14": 70.0,
        "macd_histogram": 0.005,
        "close": 50000.0,
        "bb_upper": 51000.0,
        "kc_upper": 50500.0,
        "ema21": 49500.0,
        "vwap": 50200.0,
    }

    # Тест RSI
    rsi_value = engine.get_indicator_value(indicator_data, "rsi14")
    logger.info(f"RSI значение: {rsi_value:.4f} (ожидается ~0.7)")
    assert (
        0.6 < rsi_value < 0.8
    ), f"RSI должен быть в диапазоне (0.6, 0.8), получено: {rsi_value}"  # 70/100 = 0.7

    # Тест MACD
    macd_value = engine.get_indicator_value(indicator_data, "macd_histogram")
    logger.info(f"MACD значение: {macd_value:.4f} (ожидается ~0.75)")
    assert (
        0.7 < macd_value < 0.8
    ), (
        f"MACD должен быть в диапазоне (0.7, 0.8), получено: {macd_value}"
    )  # (0.005 + 0.01) / 0.02 = 0.75

    # Тест BB (отношение close/bb_upper)
    bb_value = engine.get_indicator_value(indicator_data, "bb_upper")
    expected_bb = 50000.0 / 51000.0  # ≈ 0.98
    logger.info(f"BB значение: {bb_value:.4f} (ожидается ~{expected_bb:.4f})")
    assert (
        0.95 < bb_value < 1.0
    ), f"BB должен быть в диапазоне (0.95, 1.0), получено: {bb_value}"

    logger.info("✅ Тест извлечения значений индикаторов пройден")


def test_score_computation():
    """Тест вычисления score"""
    engine = ScoringEngine()

    # Тестовые данные
    indicator_data = {
        "rsi14": 70.0,
        "macd_histogram": 0.005,
        "close": 50000.0,
        "bb_upper": 51000.0,
        "kc_upper": 50500.0,
        "adx14": 25.0,
        "obv": 1000000.0,
        "cmf": 0.3,
        "vwap": 50200.0,
        "ema21": 49500.0,
    }

    combination_data = {
        "bbands_kc_ttm": {"signal_strength": 0.8},
        "ichimoku_macd_rsi": {"signal_strength": 0.7},
        "macd_rsi_bbands": {"signal_strength": 0.6},
    }

    # Вычисляем score
    score_raw, reasons = engine.compute_score_raw(indicator_data, combination_data)

    # Логируем детали для отладки
    logger.info(f"Score raw: {score_raw:.4f}")
    logger.info(f"Количество причин: {len(reasons)}")
    if reasons:
        logger.info(f"Причины: {reasons}")

    # Проверяем, что score в диапазоне [0;1]
    assert (
        0.0 <= score_raw <= 1.0
    ), f"Score должен быть в диапазоне [0;1], получено: {score_raw}"

    # Проверяем, что нет причин отклонения (все данные есть)
    assert (
        len(reasons) == 0
    ), f"Не должно быть причин отклонения, но получено: {reasons}"

    logger.info(f"✅ Тест вычисления score пройден: score_raw = {score_raw:.4f}")


def test_metrics_calculation():
    """Тест вычисления метрик"""
    engine = ScoringEngine()

    # Тестовый score
    score_calibrated = 0.7

    # Вычисляем метрики
    p_win, edge_net, confidence = engine.calculate_metrics(score_calibrated)

    # Логируем детали для отладки
    logger.info(f"Входной score_calibrated: {score_calibrated}")
    logger.info(f"p_win: {p_win:.4f}")
    logger.info(f"edge_net: {edge_net:.4f}")
    logger.info(f"confidence: {confidence:.4f}")

    # Проверяем метрики
    assert p_win == 0.7, f"p_win должен быть 0.7, получено: {p_win}"
    assert (
        abs(confidence - 0.4) < 0.001
    ), f"confidence должен быть 0.4, получено: {confidence}"  # abs(0.7 - 0.5) * 2 = 0.4

    # edge_net = (0.7 - 0.5) * 2.0 - 0.003 = 0.397
    expected_edge = (0.7 - 0.5) * 2.0 - 0.003
    assert (
        abs(edge_net - expected_edge) < 0.001
    ), f"edge_net должен быть {expected_edge:.4f}, получено: {edge_net:.4f}"

    logger.info(
        f"✅ Тест вычисления метрик пройден: "
        f"p_win={p_win:.4f}, edge_net={edge_net:.4f}, confidence={confidence:.4f}"
    )


def test_missing_data():
    """Тест обработки отсутствующих данных"""
    engine = ScoringEngine()

    # Данные с отсутствующими индикаторами
    indicator_data = {
        "rsi14": 70.0,
        "macd_histogram": None,  # Отсутствует
        "close": 50000.0,
        "bb_upper": 51000.0,
        # Остальные отсутствуют
    }

    combination_data = {
        "bbands_kc_ttm": {"signal_strength": 0.8},
        # Остальные комбинации отсутствуют
    }

    # Вычисляем score
    score_raw, reasons = engine.compute_score_raw(indicator_data, combination_data)

    # Логируем детали для отладки
    logger.info(f"Score raw: {score_raw:.4f}")
    logger.info(f"Количество причин: {len(reasons)}")
    logger.info(f"Причины: {reasons}")

    # Проверяем, что есть причины отклонения
    assert len(reasons) > 0, f"Ожидались причины отклонения, но получено: {reasons}"

    # Проверяем наличие причин отсутствия индикаторов
    missing_indicators = [r for r in reasons if "Отсутствует индикатор" in r]
    assert (
        len(missing_indicators) > 0
    ), f"Ожидались отсутствующие индикаторы, но получено: {reasons}"

    # Проверяем наличие причин отсутствия комбинаций
    missing_combinations = [r for r in reasons if "Отсутствует комбинация" in r]
    assert (
        len(missing_combinations) >= 1
    ), f"Ожидались отсутствующие комбинации, но получено: {reasons}"

    logger.info(
        f"✅ Тест обработки отсутствующих данных пройден: {len(reasons)} причин отклонения"
    )
    logger.info(f"  - Отсутствующие индикаторы: {len(missing_indicators)}")
    logger.info(f"  - Отсутствующие комбинации: {len(missing_combinations)}")


async def main():
    """Запуск всех тестов"""
    logger.info("🧪 Запуск тестов Scoring Engine")

    tests = [
        ("Нормализация", test_normalization),
        ("Извлечение значений индикаторов", test_indicator_value),
        ("Вычисление score", test_score_computation),
        ("Вычисление метрик", test_metrics_calculation),
        ("Обработка отсутствующих данных", test_missing_data),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            logger.info(f"🔍 Запуск теста: {test_name}")
            test_func()
            logger.info(f"✅ Тест '{test_name}' пройден")
            passed += 1
        except Exception as e:
            logger.error(f"❌ Тест '{test_name}' провален: {e}")
            failed += 1
            # Продолжаем выполнение других тестов

    logger.info("📊 Результаты тестирования:")
    logger.info(f"  - Пройдено: {passed}")
    logger.info(f"  - Провалено: {failed}")
    logger.info(f"  - Всего: {passed + failed}")

    if failed > 0:
        logger.error(f"❌ {failed} тест(ов) провалено")
        sys.exit(1)
    else:
        logger.info("🎉 Все тесты пройдены успешно!")


if __name__ == "__main__":
    asyncio.run(main())
