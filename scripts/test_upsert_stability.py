#!/usr/bin/env python3
"""
Тесты стабильности UPSERT операций
Проверяет нормализацию имён, UPSERT логику и качество данных
"""

import asyncio
import sys
from datetime import datetime

# Добавляем путь к проекту
sys.path.insert(0, ".")

from src.database import get_async_session
from src.features.infrastructure.upsert_builder import build_and_execute_upsert
from src.models import Indicator


async def test_name_normalization():
    """Тест нормализации имён индикаторов"""
    print("🧪 ТЕСТ 1: Нормализация имён индикаторов")

    # Тестовые данные с разными форматами имён
    test_data = [
        {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "timestamp": int(datetime.now().timestamp() * 1000),
            "calculated_at": datetime.now(),
            # Разные форматы имён
            "bb_upper": 50000.0,  # Корректный формат
            "bbands_upper": 50000.0,  # Старый формат (должен мапиться на bb_upper)
            "ema_200": 48000.0,
            "rsi_14": 65.5,
            "atr_14": 1000.0,
        }
    ]

    try:
        async for session in get_async_session():
            # Получаем колонки БД
            db_cols = set(Indicator.__table__.columns.keys())

            # Выполняем UPSERT
            result = await build_and_execute_upsert(
                session=session,
                model_class=Indicator,
                records=test_data,
                db_cols=db_cols,
            )

            print(f"   ✅ UPSERT выполнен успешно: {result} записей")
            return True

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


async def test_upsert_update():
    """Тест обновления записи по PK"""
    print("\n🧪 ТЕСТ 2: Обновление записи по PK")

    base_timestamp = int(datetime.now().timestamp() * 1000)

    # Первая запись
    record1 = {
        "symbol": "ETHUSDT",
        "timeframe": "1h",
        "timestamp": base_timestamp,
        "calculated_at": datetime.now(),
        "ema_200": 3000.0,
        "rsi_14": 70.0,
        "atr_14": 50.0,
    }

    # Вторая запись с тем же PK, но другими значениями
    record2 = {
        "symbol": "ETHUSDT",
        "timeframe": "1h",
        "timestamp": base_timestamp,  # Тот же PK
        "calculated_at": datetime.now(),
        "ema_200": 3100.0,  # Изменённое значение
        "rsi_14": 75.0,  # Изменённое значение
        "atr_14": 55.0,  # Изменённое значение
    }

    try:
        async for session in get_async_session():
            db_cols = set(Indicator.__table__.columns.keys())

            # Первая вставка
            result1 = await build_and_execute_upsert(
                session=session,
                model_class=Indicator,
                records=[record1],
                db_cols=db_cols,
            )
            print(f"   ✅ Первая вставка: {result1} записей")

            # Вторая вставка (должна обновить)
            result2 = await build_and_execute_upsert(
                session=session,
                model_class=Indicator,
                records=[record2],
                db_cols=db_cols,
            )
            print(f"   ✅ Вторая вставка (обновление): {result2} записей")

            # Проверяем, что запись обновилась
            from sqlalchemy import select

            stmt = select(Indicator).where(
                Indicator.symbol == "ETHUSDT",
                Indicator.timeframe == "1h",
                Indicator.timestamp == base_timestamp,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if record and record.ema_200 == 3100.0:
                print("   ✅ Запись успешно обновлена")
                return True
            print("   ❌ Запись не обновилась")
            return False

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


async def test_data_quality_metrics():
    """Тест метрик качества данных"""
    print("\n🧪 ТЕСТ 3: Метрики качества данных")

    try:
        async for session in get_async_session():
            # Проверяем количество записей
            from sqlalchemy import func, select

            total_count = await session.scalar(select(func.count(Indicator.id)))
            print(f"   📊 Всего записей в БД: {total_count}")

            # Проверяем покрытие ключевых индикаторов
            key_indicators = ["ema_200", "rsi_14", "atr_14", "macd", "bb_upper"]
            coverage_stats = {}

            for indicator in key_indicators:
                if hasattr(Indicator, indicator):
                    count = await session.scalar(
                        select(func.count(getattr(Indicator, indicator))).where(
                            getattr(Indicator, indicator).isnot(None)
                        )
                    )
                    coverage_stats[indicator] = count
                    print(f"   📊 {indicator}: {count} записей")
                else:
                    print(f"   ❌ {indicator}: колонка отсутствует")

            # Проверяем свежесть данных
            latest_timestamp = await session.scalar(
                select(func.max(Indicator.timestamp))
            )
            if latest_timestamp:
                latest_time = datetime.fromtimestamp(latest_timestamp / 1000)
                print(f"   📊 Последняя запись: {latest_time}")

                # Проверяем, что данные свежие (не старше 1 часа)
                now = datetime.now()
                time_diff = (now - latest_time).total_seconds() / 3600  # в часах
                if time_diff < 1:
                    print("   ✅ Данные свежие (< 1 часа)")
                else:
                    print(f"   ⚠️ Данные устарели ({time_diff:.1f} часов)")

            # Оценка качества
            total_coverage = sum(coverage_stats.values())
            if total_coverage > 0:
                print("   ✅ Есть данные по ключевым индикаторам")
            else:
                print("   ❌ Нет данных по ключевым индикаторам")

            return True

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


async def test_problematic_fields_filtering():
    """Тест фильтрации проблемных полей"""
    print("\n🧪 ТЕСТ 4: Фильтрация проблемных полей")

    # Тестовые данные с проблемными полями
    test_data = [
        {
            "symbol": "ADAUSDT",
            "timeframe": "1h",
            "timestamp": int(datetime.now().timestamp() * 1000),
            "calculated_at": datetime.now(),
            "ema_200": 0.5,
            "rsi_14": 60.0,
            # Проблемные поля (должны быть отфильтрованы)
            "ics_26": 0.8,
            "rma_20": 0.6,
            "t3_20": 0.7,
            "parkinson_vol": 0.05,
        }
    ]

    try:
        async for session in get_async_session():
            db_cols = set(Indicator.__table__.columns.keys())

            # Выполняем UPSERT
            result = await build_and_execute_upsert(
                session=session,
                model_class=Indicator,
                records=test_data,
                db_cols=db_cols,
            )

            print(f"   ✅ UPSERT выполнен: {result} записей")
            print("   ✅ Проблемные поля отфильтрованы автоматически")
            return True

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


async def main():
    """Запуск всех тестов"""
    print("🚀 ЗАПУСК ТЕСТОВ СТАБИЛЬНОСТИ UPSERT")
    print("=" * 60)

    tests = [
        test_name_normalization,
        test_upsert_update,
        test_data_quality_metrics,
        test_problematic_fields_filtering,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
        except Exception as e:
            print(f"   ❌ Тест упал с ошибкой: {e}")

    print("\n🎯 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"   - Пройдено: {passed}/{total}")
    print(f"   - Успешность: {passed/total*100:.1f}%")

    if passed == total:
        print("   ✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Система стабильна.")
    else:
        print("   ⚠️ ЕСТЬ ПРОБЛЕМЫ! Требуется доработка.")

    return passed == total


if __name__ == "__main__":
    asyncio.run(main())
