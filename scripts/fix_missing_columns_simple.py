#!/usr/bin/env python3
"""
Простой скрипт для добавления отсутствующих колонок без зависимостей от проекта
"""

import asyncio
import logging
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получаем URL базы данных из переменных окружения
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://pklpo_user:strongpassword@localhost:5432/pklpo",
)


async def check_and_fix_missing_columns():
    """Проверяет и добавляет отсутствующие колонки в таблицу indicators"""

    # Создаем engine
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with AsyncSession(engine) as session:
        try:
            logger.info("🔍 Проверяем текущую схему таблицы indicators...")

            # 1. Получаем текущие колонки
            result = await session.execute(
                text(
                    """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'indicators'
                AND table_schema = 'public'
                ORDER BY column_name
            """
                )
            )

            current_columns = {row[0]: row[1] for row in result.fetchall()}
            logger.info(f"📊 Текущие колонки в БД: {len(current_columns)}")

            # 2. Проверяем наличие проблемных колонок
            missing_columns = []
            required_columns = [
                "ics_26",
                "rma_20",
                "t3_20",
            ]  # Все колонки из логов ошибок

            for col in required_columns:
                if col not in current_columns:
                    missing_columns.append(col)
                    logger.warning(f"❌ Колонка {col} отсутствует в БД")
                else:
                    logger.info(
                        f"✅ Колонка {col} уже существует: {current_columns[col]}"
                    )

            # 3. Добавляем недостающие колонки
            if missing_columns:
                logger.info(f"🔧 Добавляем недостающие колонки: {missing_columns}")

                for col in missing_columns:
                    try:
                        alter_query = text(
                            f"""
                            ALTER TABLE indicators
                            ADD COLUMN {col} DECIMAL(20,8) NULL
                        """
                        )
                        await session.execute(alter_query)
                        logger.info(f"✅ Колонка {col} добавлена успешно")
                    except Exception as e:
                        if "duplicate column" in str(e).lower():
                            logger.info(
                                f"ℹ️ Колонка {col} уже существует (дублирование)"
                            )
                        else:
                            logger.error(f"❌ Ошибка при добавлении {col}: {e}")
                            raise

                await session.commit()
                logger.info("🎉 Все колонки добавлены успешно!")
            else:
                logger.info("✅ Все необходимые колонки уже существуют")

            # 4. Финальная проверка
            logger.info("🔍 Финальная проверка схемы...")
            result = await session.execute(
                text(
                    """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'indicators'
                AND table_schema = 'public'
                AND column_name IN ('ics_26', 'rma_20', 't3_20')
                ORDER BY column_name
            """
                )
            )

            final_columns = [row[0] for row in result.fetchall()]
            logger.info(f"📊 Финальные колонки: {final_columns}")

            if all(col in final_columns for col in required_columns):
                logger.info(
                    "🎉 ПРОБЛЕМА РЕШЕНА! Все необходимые колонки добавлены в БД"
                )
                return True
            missing_final = [
                col for col in required_columns if col not in final_columns
            ]
            logger.error(
                f"❌ Проблема не решена - отсутствуют колонки: {missing_final}"
            )
            return False

        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    success = asyncio.run(check_and_fix_missing_columns())
    if success:
        print("\nУСПЕХ! Проблема с отсутствующими колонками решена!")
        print("Теперь можно запускать features calculation без ошибок.")
    else:
        print("\nОШИБКА! Проблема не решена.")
        exit(1)
