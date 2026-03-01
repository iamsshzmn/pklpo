#!/usr/bin/env python3
"""
Скрипт для создания таблиц торговых рекомендаций
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.db.migrate_create_trade_recommendations import (
    migrate_create_trade_recommendations,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Создаёт таблицы для торговых рекомендаций"""
    logger.info("🚀 Создание таблиц торговых рекомендаций...")

    try:
        await migrate_create_trade_recommendations()
        logger.info("✅ Таблицы созданы успешно!")

        print("\n📊 Созданные таблицы:")
        print("  - trade_recommendations - торговые рекомендации")
        print("  - trade_positions - исполненные позиции")
        print("\n🔗 Связи:")
        print("  - trade_positions.recommendation_id -> trade_recommendations.id")

    except Exception as e:
        logger.error(f"❌ Ошибка при создании таблиц: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
