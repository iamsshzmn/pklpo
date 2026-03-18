#!/usr/bin/env python3
"""
Миграция для очистки дублирующихся колонок и исправления данных в таблице instruments
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import text

from src.database import create_session


async def cleanup_duplicate_columns():
    """Удаляет дублирующиеся колонки и исправляет данные"""

    print("🧹 Очистка дублирующихся колонок в таблице instruments...")

    async with await create_session() as session:
        try:
            # 1. Проверяем существование дублирующихся колонок
            result = await session.execute(
                text(
                    """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'instruments'
                AND column_name IN ('min_sz', 'minSz', 'max_sz', 'maxSz', 'min_notional', 'minNotional')
                ORDER BY column_name
            """
                )
            )

            existing_columns = {row[0] for row in result.fetchall()}
            print(f"Найдены колонки: {existing_columns}")

            # 2. Копируем данные из старых колонок в новые (если нужно)
            if "minSz" in existing_columns and "min_sz" in existing_columns:
                print("🔄 Копируем данные из minSz в min_sz...")
                await session.execute(
                    text(
                        """
                    UPDATE instruments
                    SET min_sz = "minSz"
                    WHERE min_sz IS NULL AND "minSz" IS NOT NULL
                """
                    )
                )

            if "maxSz" in existing_columns and "max_sz" in existing_columns:
                print("🔄 Копируем данные из maxSz в max_sz...")
                await session.execute(
                    text(
                        """
                    UPDATE instruments
                    SET max_sz = "maxSz"
                    WHERE max_sz IS NULL AND "maxSz" IS NOT NULL
                """
                    )
                )

            if "minNotional" in existing_columns and "min_notional" in existing_columns:
                print("🔄 Копируем данные из minNotional в min_notional...")
                await session.execute(
                    text(
                        """
                    UPDATE instruments
                    SET min_notional = "minNotional"
                    WHERE min_notional IS NULL AND "minNotional" IS NOT NULL
                """
                    )
                )

            # 3. Удаляем старые колонки
            columns_to_drop = ["minSz", "maxSz", "minNotional"]

            for col in columns_to_drop:
                if col in existing_columns:
                    print(f"🗑️ Удаляем колонку {col}...")
                    await session.execute(
                        text(f'ALTER TABLE instruments DROP COLUMN IF EXISTS "{col}"')
                    )

            # 4. Исправляем пустые базовые поля
            print("🔧 Исправляем пустые базовые поля...")

            # Извлекаем base_ccy и quote_ccy из symbol
            await session.execute(
                text(
                    """
                UPDATE instruments
                SET
                    base_ccy = SPLIT_PART(symbol, '-', 1),
                    quote_ccy = SPLIT_PART(symbol, '-', 2)
                WHERE (base_ccy IS NULL OR base_ccy = '')
                AND (quote_ccy IS NULL OR quote_ccy = '')
                AND symbol LIKE '%-%-%'
            """
                )
            )

            # Для SWAP инструментов quote_ccy может быть третьей частью
            await session.execute(
                text(
                    """
                UPDATE instruments
                SET quote_ccy = SPLIT_PART(symbol, '-', 3)
                WHERE (quote_ccy IS NULL OR quote_ccy = '')
                AND symbol LIKE '%-%-SWAP'
            """
                )
            )

            await session.commit()
            print("✅ Очистка завершена успешно")

            # 5. Проверяем результат
            result = await session.execute(
                text(
                    """
                SELECT COUNT(*) as total,
                       COUNT(CASE WHEN base_ccy IS NOT NULL AND base_ccy != '' THEN 1 END) as with_base,
                       COUNT(CASE WHEN quote_ccy IS NOT NULL AND quote_ccy != '' THEN 1 END) as with_quote
                FROM instruments
            """
                )
            )

            stats = result.fetchone()
            print("\n📊 Результат:")
            print(f"  Всего записей: {stats[0]}")
            print(f"  С base_ccy: {stats[1]}")
            print(f"  С quote_ccy: {stats[2]}")

        except Exception as e:
            print(f"❌ Ошибка при очистке: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(cleanup_duplicate_columns())
