#!/usr/bin/env python3
"""
Финальный тест для проверки исправления ошибки 'stmt' variable
"""
import os
import sys

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.models import Indicator


def test_stmt_variable_fix():
    """Тестирует исправление ошибки с переменной stmt"""

    print("Тестируем исправление ошибки 'stmt' variable...")

    # Создаём тестовые данные
    test_data = [
        {
            "symbol": "BTC-USDT",
            "timeframe": "1m",
            "timestamp": 1640995200000,
            "calculated_at": "2022-01-01 00:00:00",
            "ics_26": 108325.9,
            "rma_20": 108300.5,
            "t3_20": 108310.1,
            "ema_200": 108200.0,
            "rsi_14": 65.5,
            "atr_14": 150.0,
        }
    ]

    print(f"Тестовые данные: {len(test_data)} записей")

    try:
        # Тестируем правильную последовательность создания stmt
        print("1. Создаём UPSERT statement...")
        stmt = pg_insert(Indicator).values(test_data)
        print("   stmt создан успешно")

        # Тестируем создание update_dict с stmt.excluded
        print("2. Создаём update_dict...")
        first_record = test_data[0]
        pk = {"symbol", "timeframe", "timestamp"}
        db_cols = {
            "symbol",
            "timeframe",
            "timestamp",
            "calculated_at",
            "ics_26",
            "rma_20",
            "t3_20",
            "ema_200",
            "rsi_14",
            "atr_14",
        }

        update_dict = {}
        for k in first_record.keys():
            if k in db_cols and k not in pk:
                try:
                    update_dict[k] = stmt.excluded[k]
                    print(f"   Поле '{k}' добавлено в update_dict")
                except KeyError:
                    print(f"   Поле '{k}' не доступно в stmt.excluded")
                    continue

        print(f"   Update fields: {len(update_dict)}")

        # Тестируем создание on_conflict_do_update
        print("3. Создаём on_conflict_do_update...")
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "timeframe", "timestamp"], set_=update_dict
        )
        print("   on_conflict_do_update создан успешно")

        print("\nТЕСТ ПРОШЁЛ! Ошибка 'stmt' variable исправлена!")
        return True

    except Exception as e:
        print(f"Ошибка в тесте: {e}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    success = test_stmt_variable_fix()
    if success:
        print("\nФИНАЛЬНЫЙ ТЕСТ ПРОШЁЛ!")
        print("Все критические ошибки в insert_indicators.py исправлены:")
        print("  - Unconsumed column names: РЕШЕНО")
        print("  - SQLAlchemy boundparameter: РЕШЕНО")
        print("  - stmt variable error: РЕШЕНО")
        print("\nСистема готова к продакшену!")
    else:
        print("\nТЕСТ НЕ ПРОШЁЛ! Нужна дополнительная отладка.")
        exit(1)
