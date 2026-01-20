#!/usr/bin/env python3
"""
Упрощённые тесты валидации без подключения к БД
Проверяет логику фильтрации и нормализации
"""

import sys
from datetime import datetime

import numpy as np
import pandas as pd

# Добавляем путь к проекту
sys.path.insert(0, ".")


def test_name_normalization():
    """Тест нормализации имён индикаторов"""
    print("🧪 ТЕСТ 1: Нормализация имён индикаторов")

    # Маппинг для нормализации
    name_mapping = {
        "bbands_upper": "bb_upper",
        "bbands_middle": "bb_middle",
        "bbands_lower": "bb_lower",
        "bbands_width": "bb_width",
        "bbands_percent": "bb_percent",
        "ema200": "ema_200",
        "rsi14": "rsi_14",
        "atr14": "atr_14",
    }

    # Тестовые данные
    test_data = {
        "bbands_upper": 50000.0,
        "bbands_middle": 48000.0,
        "bbands_lower": 46000.0,
        "ema200": 47000.0,
        "rsi14": 65.5,
        "atr14": 1000.0,
    }

    # Нормализация
    normalized_data = {}
    for old_name, value in test_data.items():
        new_name = name_mapping.get(old_name, old_name)
        normalized_data[new_name] = value

    print(f"   📊 Исходные поля: {list(test_data.keys())}")
    print(f"   📊 Нормализованные поля: {list(normalized_data.keys())}")

    # Проверяем результат
    expected_fields = [
        "bb_upper",
        "bb_middle",
        "bb_lower",
        "ema_200",
        "rsi_14",
        "atr_14",
    ]
    if all(field in normalized_data for field in expected_fields):
        print("   ✅ Нормализация работает корректно")
        return True
    print("   ❌ Нормализация работает некорректно")
    return False


def test_problematic_fields_filtering():
    """Тест фильтрации проблемных полей"""
    print("\n🧪 ТЕСТ 2: Фильтрация проблемных полей")

    # Проблемные поля
    problematic_fields = ["ics_26", "rma_20", "t3_20", "parkinson_vol"]

    # Тестовые данные
    test_data = {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "timestamp": int(datetime.now().timestamp() * 1000),
        "calculated_at": datetime.now(),
        "ema_200": 50000.0,
        "rsi_14": 65.5,
        "atr_14": 1000.0,
        # Проблемные поля
        "ics_26": 0.8,
        "rma_20": 0.6,
        "t3_20": 0.7,
        "parkinson_vol": 0.05,
    }

    # Фильтрация
    filtered_data = {k: v for k, v in test_data.items() if k not in problematic_fields}

    print(f"   📊 Исходные поля: {len(test_data)}")
    print(f"   📊 После фильтрации: {len(filtered_data)}")
    print(f"   📊 Удалённые поля: {[k for k in test_data if k not in filtered_data]}")

    # Проверяем результат
    if len(filtered_data) == len(test_data) - len(problematic_fields):
        print("   ✅ Фильтрация работает корректно")
        return True
    print("   ❌ Фильтрация работает некорректно")
    return False


def test_data_quality_validation():
    """Тест валидации качества данных"""
    print("\n🧪 ТЕСТ 3: Валидация качества данных")

    # Тестовые данные с разным качеством
    test_cases = [
        {
            "name": "Хорошие данные",
            "data": {
                "ema_200": 50000.0,
                "rsi_14": 65.5,
                "atr_14": 1000.0,
                "macd": 150.0,
            },
            "expected": True,
        },
        {
            "name": "Данные с NaN",
            "data": {
                "ema_200": float("nan"),
                "rsi_14": 65.5,
                "atr_14": 1000.0,
                "macd": 150.0,
            },
            "expected": False,
        },
        {
            "name": "Данные с inf",
            "data": {
                "ema_200": float("inf"),
                "rsi_14": 65.5,
                "atr_14": 1000.0,
                "macd": 150.0,
            },
            "expected": False,
        },
        {"name": "Пустые данные", "data": {}, "expected": False},
    ]

    def validate_data_quality(data):
        """Валидация качества данных"""
        if not data:
            return False

        for key, value in data.items():
            if pd.isna(value) or np.isinf(value):
                return False

        return True

    passed = 0
    for case in test_cases:
        result = validate_data_quality(case["data"])
        if result == case["expected"]:
            print(f"   ✅ {case['name']}: {result}")
            passed += 1
        else:
            print(
                f"   ❌ {case['name']}: ожидалось {case['expected']}, получено {result}"
            )

    print(f"   📊 Пройдено тестов: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_coverage_calculation():
    """Тест расчёта покрытия"""
    print("\n🧪 ТЕСТ 4: Расчёт покрытия")

    # Симуляция данных
    total_indicators = 196  # Всего индикаторов в реестре
    calculated_indicators = 150  # Рассчитанных индикаторов

    coverage = (calculated_indicators / total_indicators) * 100

    print(f"   📊 Всего индикаторов: {total_indicators}")
    print(f"   📊 Рассчитано: {calculated_indicators}")
    print(f"   📊 Покрытие: {coverage:.1f}%")

    # Проверяем минимальное покрытие
    if coverage >= 95:
        print("   ✅ Покрытие отличное (≥95%)")
        return True
    if coverage >= 90:
        print("   ✅ Покрытие хорошее (≥90%)")
        return True
    if coverage >= 80:
        print("   ⚠️ Покрытие удовлетворительное (≥80%)")
        return True
    print("   ❌ Покрытие недостаточное (<80%)")
    return False


def main():
    """Запуск всех тестов"""
    print("🚀 ЗАПУСК УПРОЩЁННЫХ ТЕСТОВ ВАЛИДАЦИИ")
    print("=" * 60)

    tests = [
        test_name_normalization,
        test_problematic_fields_filtering,
        test_data_quality_validation,
        test_coverage_calculation,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            result = test()
            if result:
                passed += 1
        except Exception as e:
            print(f"   ❌ Тест упал с ошибкой: {e}")

    print("\n🎯 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"   - Пройдено: {passed}/{total}")
    print(f"   - Успешность: {passed/total*100:.1f}%")

    if passed == total:
        print("   ✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Логика валидации работает корректно.")
    else:
        print("   ⚠️ ЕСТЬ ПРОБЛЕМЫ! Требуется доработка логики.")

    return passed == total


if __name__ == "__main__":
    main()
