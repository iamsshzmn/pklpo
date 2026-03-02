"""
CLI аудит-команда для сравнения FEATURE_SPECS vs колонки indicators.

Эта команда помогает выявить расхождения между определенными спецификациями
фичей и фактическими колонками в таблице indicators.
"""

import asyncio
import logging
import os
import sys
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_async_session
from features.name_mapping import get_available_indicators, validate_versions
from features.specs import FEATURE_SPECS, PHASE_2_REQUIRED_FEATURES

logger = logging.getLogger(__name__)


async def get_indicators_columns(session: AsyncSession) -> set[str]:
    """
    Получить список колонок из таблицы indicators.

    Args:
        session: Асинхронная сессия БД

    Returns:
        Множество имен колонок
    """
    try:
        # Получаем информацию о колонках таблицы indicators
        query = text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'indicators'
            AND table_schema = 'public'
            ORDER BY column_name
        """
        )

        result = await session.execute(query)
        columns = {row[0] for row in result.fetchall()}

        # Исключаем служебные колонки
        service_columns = {
            "symbol",
            "timeframe",
            "timestamp",
            "calculated_at",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "ts",
        }

        return columns - service_columns

    except Exception as e:
        logger.error(f"Ошибка при получении колонок indicators: {e}")
        return set()


def get_feature_specs_names() -> set[str]:
    """
    Получить имена фичей из FEATURE_SPECS.

    Returns:
        Множество имен фичей из спецификаций
    """
    return {spec.name for spec in FEATURE_SPECS}


def get_phase_2_required_names() -> set[str]:
    """
    Получить имена обязательных фичей Phase 2.

    Returns:
        Множество имен обязательных фичей
    """
    return set(PHASE_2_REQUIRED_FEATURES)


def analyze_differences(
    db_columns: set[str], spec_names: set[str], required_names: set[str]
) -> dict[str, Any]:
    """
    Анализировать различия между колонками БД и спецификациями.

    Args:
        db_columns: Колонки в БД
        spec_names: Имена из спецификаций
        required_names: Обязательные имена Phase 2

    Returns:
        Словарь с анализом различий
    """
    return {
        "missing_in_db": list(spec_names - db_columns),
        "extra_in_db": list(db_columns - spec_names),
        "missing_required": list(required_names - db_columns),
        "coverage": {
            "total_specs": len(spec_names),
            "in_db": len(spec_names & db_columns),
            "coverage_percent": (
                len(spec_names & db_columns) / len(spec_names) * 100
                if spec_names
                else 0
            ),
        },
        "required_coverage": {
            "total_required": len(required_names),
            "in_db": len(required_names & db_columns),
            "coverage_percent": (
                len(required_names & db_columns) / len(required_names) * 100
                if required_names
                else 0
            ),
        },
    }


def print_analysis_report(analysis: dict[str, Any]) -> None:
    """
    Вывести отчет об анализе.

    Args:
        analysis: Результат анализа различий
    """
    print("\n" + "=" * 80)
    print("📊 ОТЧЕТ АУДИТА FEATURE_SPECS vs INDICATORS")
    print("=" * 80)

    # Общая статистика
    coverage = analysis["coverage"]
    required_coverage = analysis["required_coverage"]

    print("\n📈 ОБЩАЯ СТАТИСТИКА:")
    print(f"   Всего спецификаций: {coverage['total_specs']}")
    print(f"   В БД: {coverage['in_db']}")
    print(f"   Покрытие: {coverage['coverage_percent']:.1f}%")

    print("\n🎯 PHASE 2 ОБЯЗАТЕЛЬНЫЕ:")
    print(f"   Всего обязательных: {required_coverage['total_required']}")
    print(f"   В БД: {required_coverage['in_db']}")
    print(f"   Покрытие: {required_coverage['coverage_percent']:.1f}%")

    # Отсутствующие в БД
    missing_in_db = analysis["missing_in_db"]
    if missing_in_db:
        print(f"\n❌ ОТСУТСТВУЮТ В БД ({len(missing_in_db)}):")
        for name in sorted(missing_in_db)[:20]:  # Показываем первые 20
            print(f"   - {name}")
        if len(missing_in_db) > 20:
            print(f"   ... и еще {len(missing_in_db) - 20}")

    # Лишние в БД
    extra_in_db = analysis["extra_in_db"]
    if extra_in_db:
        print(f"\n➕ ЛИШНИЕ В БД ({len(extra_in_db)}):")
        for name in sorted(extra_in_db)[:20]:  # Показываем первые 20
            print(f"   - {name}")
        if len(extra_in_db) > 20:
            print(f"   ... и еще {len(extra_in_db) - 20}")

    # Отсутствующие обязательные
    missing_required = analysis["missing_required"]
    if missing_required:
        print(f"\n🚨 ОТСУТСТВУЮТ ОБЯЗАТЕЛЬНЫЕ PHASE 2 ({len(missing_required)}):")
        for name in sorted(missing_required):
            print(f"   - {name}")

    print("\n" + "=" * 80)


async def audit_features():
    """
    Основная функция аудита.
    """
    print("🔍 Запуск аудита FEATURE_SPECS vs indicators...")

    # Проверяем версии
    print("\n📋 Проверка версий:")
    version_info = validate_versions()
    if not version_info:
        print("   ⚠️  Версии pandas_ta/pandas не соответствуют ожидаемым")
    else:
        print("   ✅ Версии соответствуют ожидаемым")

    # Получаем доступные индикаторы
    available_indicators = get_available_indicators()
    print(f"   📊 Доступно индикаторов pandas_ta: {len(available_indicators)}")

    # Получаем данные из БД
    async with get_async_session() as session:
        db_columns = await get_indicators_columns(session)
        print(f"   🗄️  Колонок в таблице indicators: {len(db_columns)}")

    # Получаем спецификации
    spec_names = get_feature_specs_names()
    required_names = get_phase_2_required_names()

    print(f"   📝 Спецификаций фичей: {len(spec_names)}")
    print(f"   🎯 Обязательных Phase 2: {len(required_names)}")

    # Анализируем различия
    analysis = analyze_differences(db_columns, spec_names, required_names)

    # Выводим отчет
    print_analysis_report(analysis)

    # Рекомендации
    print("\n💡 РЕКОМЕНДАЦИИ:")

    if analysis["missing_in_db"]:
        print("   1. Добавить отсутствующие фичи в БД или обновить спецификации")

    if analysis["extra_in_db"]:
        print("   2. Проверить лишние колонки в БД - возможно, устаревшие")

    if analysis["missing_required"]:
        print("   3. ⚠️  КРИТИЧНО: Добавить отсутствующие обязательные фичи Phase 2")

    if analysis["coverage"]["coverage_percent"] < 90:
        print("   4. Низкое покрытие спецификаций - требуется доработка")

    print("\n✅ Аудит завершен")


def main():
    """Точка входа для CLI."""
    asyncio.run(audit_features())


if __name__ == "__main__":
    main()
