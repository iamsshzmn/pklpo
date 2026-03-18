"""
Миграция для исправления имен колонок в таблице instruments
Переименовывает camelCase колонки в snake_case для совместимости с PostgreSQL
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import text

from src.database import create_session


async def run_migrations():
    """Выполняет миграции для исправления имен колонок"""

    print("🔄 Выполнение миграции для исправления имен колонок instruments...")

    async with await create_session() as session:
        try:
            # Проверяем, какие колонки нужно переименовать
            result = await session.execute(
                text(
                    """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'instruments'
                AND column_name IN ('instId', 'baseCcy', 'quoteCcy', 'instType', 'ctValCcy', 'ctVal', 'listTime', 'minSz', 'maxSz', 'minNotional')
            """
                )
            )

            existing_columns = [row[0] for row in result.fetchall()]

            if not existing_columns:
                print("✅ Все колонки уже имеют правильные имена (snake_case)")
                return

            print(f"📋 Найдены колонки для переименования: {existing_columns}")

            # Словарь соответствия старых и новых имен
            column_mapping = {
                "instId": "inst_id",
                "baseCcy": "base_ccy",
                "quoteCcy": "quote_ccy",
                "instType": "inst_type",
                "ctValCcy": "ct_val_ccy",
                "ctVal": "ct_val",
                "listTime": "list_time",
                "minSz": "min_sz",
                "maxSz": "max_sz",
                "minNotional": "min_notional",
            }

            # Переименовываем колонки
            for old_name, new_name in column_mapping.items():
                if old_name in existing_columns:
                    print(f"🔄 Переименовываем {old_name} -> {new_name}")

                    # Проверяем, не существует ли уже новая колонка
                    check_result = await session.execute(
                        text(
                            f"""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'instruments'
                        AND column_name = '{new_name}'
                    """
                        )
                    )

                    if check_result.fetchone():
                        print(
                            f"⚠️  Колонка {new_name} уже существует, удаляем старую {old_name}"
                        )
                        await session.execute(
                            text(
                                f'ALTER TABLE instruments DROP COLUMN IF EXISTS "{old_name}"'
                            )
                        )
                    else:
                        await session.execute(
                            text(
                                f'ALTER TABLE instruments RENAME COLUMN "{old_name}" TO "{new_name}"'
                            )
                        )

            await session.commit()
            print("✅ Миграция завершена успешно")

        except Exception as e:
            print(f"❌ Ошибка при выполнении миграции: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(run_migrations())
