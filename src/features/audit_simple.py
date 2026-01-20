"""
Упрощенная CLI аудит-команда для анализа FEATURE_SPECS.

Эта команда анализирует спецификации фичей без подключения к БД.
"""

import logging
import os
import sys
from typing import Any

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.name_mapping import (
    INDICATOR_NAME_MAPPING,
    get_available_indicators,
    validate_versions,
)
from features.specs import FEATURE_SPECS, PHASE_2_REQUIRED_FEATURES

logger = logging.getLogger(__name__)


def get_feature_specs_names() -> set[str]:
    """
    Получить имена фичей из FEATURE_SPECS.

    Returns:
        Множество имен фичей из спецификаций
    """
    names = set()
    for spec in FEATURE_SPECS:
        if hasattr(spec, "name"):
            names.add(spec.name)
        elif isinstance(spec, str):
            names.add(spec)
    return names


def get_phase_2_required_names() -> set[str]:
    """
    Получить имена обязательных фичей Phase 2.

    Returns:
        Множество имен обязательных фичей
    """
    return set(PHASE_2_REQUIRED_FEATURES)


def analyze_feature_specs() -> dict[str, Any]:
    """
    Анализировать спецификации фичей.

    Returns:
        Словарь с анализом спецификаций
    """
    spec_names = get_feature_specs_names()
    required_names = get_phase_2_required_names()
    available_indicators = get_available_indicators()

    # Анализ по типам
    type_analysis: dict[str, list[str]] = {}
    for spec in FEATURE_SPECS:
        if hasattr(spec, "type") and hasattr(spec, "name"):
            spec_type = spec.type
            if spec_type not in type_analysis:
                type_analysis[spec_type] = []
            type_analysis[spec_type].append(spec.name)
        elif isinstance(spec, str):
            # Для строковых спецификаций используем тип "unknown"
            if "unknown" not in type_analysis:
                type_analysis["unknown"] = []
            type_analysis["unknown"].append(spec)

    # Анализ покрытия pandas_ta
    mapped_indicators = set(INDICATOR_NAME_MAPPING.keys())
    coverage_analysis = {
        "total_mapped": len(mapped_indicators),
        "available": len(mapped_indicators & available_indicators),
        "coverage_percent": (
            len(mapped_indicators & available_indicators) / len(mapped_indicators) * 100
            if mapped_indicators
            else 0
        ),
    }

    return {
        "total_specs": len(FEATURE_SPECS),
        "spec_names": spec_names,
        "required_names": required_names,
        "type_analysis": type_analysis,
        "coverage_analysis": coverage_analysis,
        "available_indicators_count": len(available_indicators),
    }


def print_analysis_report(analysis: dict[str, Any]) -> None:
    """
    Вывести отчет об анализе.

    Args:
        analysis: Результат анализа спецификаций
    """
    print("\n" + "=" * 80)
    print("ОТЧЕТ АУДИТА FEATURE_SPECS")
    print("=" * 80)

    # Общая статистика
    print("\nОБЩАЯ СТАТИСТИКА:")
    print(f"   Всего спецификаций: {analysis['total_specs']}")
    print(f"   Уникальных имен: {len(analysis['spec_names'])}")
    print(f"   Обязательных Phase 2: {len(analysis['required_names'])}")
    print(
        f"   Доступно индикаторов pandas_ta: {analysis['available_indicators_count']}"
    )

    # Анализ по типам
    type_analysis = analysis["type_analysis"]
    print("\nАНАЛИЗ ПО ТИПАМ:")
    for spec_type, names in sorted(type_analysis.items()):
        print(f"   {spec_type}: {len(names)} фичей")
        # Показываем первые 5 примеров
        examples = sorted(names)[:5]
        print(f"      Примеры: {', '.join(examples)}")
        if len(names) > 5:
            print(f"      ... и еще {len(names) - 5}")

    # Покрытие pandas_ta
    coverage = analysis["coverage_analysis"]
    print("\nПОКРЫТИЕ PANDAS_TA:")
    print(f"   Всего маппингов: {coverage['total_mapped']}")
    print(f"   Доступно: {coverage['available']}")
    print(f"   Покрытие: {coverage['coverage_percent']:.1f}%")

    # Обязательные фичи
    required_names = analysis["required_names"]
    spec_names = analysis["spec_names"]
    missing_required = required_names - spec_names

    print("\nPHASE 2 ОБЯЗАТЕЛЬНЫЕ:")
    print(f"   Всего обязательных: {len(required_names)}")
    print(f"   В спецификациях: {len(required_names & spec_names)}")
    if missing_required:
        print(f"   ERROR: Отсутствуют в спецификациях ({len(missing_required)}):")
        for name in sorted(missing_required):
            print(f"      - {name}")
    else:
        print("   OK: Все обязательные фичи присутствуют в спецификациях")

    print("\n" + "=" * 80)


def audit_features():
    """
    Основная функция аудита.
    """
    print("Запуск аудита FEATURE_SPECS...")

    # Проверяем версии
    print("\nПроверка версий:")
    version_info = validate_versions()
    if not version_info:
        print("   WARNING: Версии pandas_ta/pandas не соответствуют ожидаемым")
    else:
        print("   OK: Версии соответствуют ожидаемым")

    # Анализируем спецификации
    analysis = analyze_feature_specs()

    # Выводим отчет
    print_analysis_report(analysis)

    # Рекомендации
    print("\nРЕКОМЕНДАЦИИ:")

    missing_required = analysis["required_names"] - analysis["spec_names"]
    if missing_required:
        print(
            "   1. КРИТИЧНО: Добавить отсутствующие обязательные фичи Phase 2 в спецификации"
        )

    if analysis["coverage_analysis"]["coverage_percent"] < 90:
        print("   2. Низкое покрытие pandas_ta - проверить доступность индикаторов")

    if len(analysis["spec_names"]) != analysis["total_specs"]:
        print("   3. Обнаружены дублирующиеся имена в спецификациях")

    print("\nАудит завершен")


def main():
    """Точка входа для CLI."""
    audit_features()


if __name__ == "__main__":
    main()
