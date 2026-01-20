#!/usr/bin/env python3
"""
Автоматическое обновление списка инструментов для синхронизации.
Сохраняет BTC и ETH в начале списка, остальные добавляет по алфавиту.
"""

import asyncio
import json
import logging
from pathlib import Path

from sqlalchemy import select

from src.models import Instrument
from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def update_instruments_list() -> None:
    """
    Обновляет список инструментов в instruments_list.json.
    Сохраняет BTC и ETH в начале, остальные добавляет по алфавиту.
    """
    instruments_file = Path(__file__).parent / "instruments_list.json"

    # Загружаем текущий список
    current_symbols: list[str] = []
    if instruments_file.exists():
        try:
            with open(instruments_file, encoding="utf-8") as f:
                current_symbols = json.load(f)
            logger.info(f"📋 Загружен текущий список: {len(current_symbols)} символов")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки текущего списка: {e}")

    # Получаем все SWAP USDT символы из БД
    logger.info("🔄 Загружаем символы из базы данных...")
    async with get_db_session() as session:
        result = await session.execute(
            select(Instrument.symbol).where(
                Instrument.settle_ccy == "USDT",
                Instrument.inst_type == "SWAP",
            )
        )
        db_symbols = [row[0] for row in result.fetchall()]

    logger.info(f"📊 Найдено {len(db_symbols)} SWAP USDT символов в БД")

    # Определяем приоритетные символы (всегда в начале)
    priority_symbols = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]

    # Создаем новый список
    new_symbols = []

    # 1. Добавляем приоритетные символы (если есть в БД)
    for priority in priority_symbols:
        if priority in db_symbols:
            new_symbols.append(priority)
            logger.debug(f"➕ Добавлен приоритетный символ: {priority}")

    # 2. Добавляем остальные символы по алфавиту
    remaining_symbols = sorted([s for s in db_symbols if s not in priority_symbols])
    new_symbols.extend(remaining_symbols)

    logger.info(f"📝 Новый список содержит {len(new_symbols)} символов")

    # Проверяем изменения
    current_set = set(current_symbols)
    new_set = set(new_symbols)

    added = new_set - current_set
    removed = current_set - new_set

    if added:
        logger.info(f"➕ Добавлены новые символы: {sorted(added)}")
    if removed:
        logger.info(f"➖ Удалены символы: {sorted(removed)}")

    if not added and not removed:
        logger.info("✅ Список актуален, изменений не требуется")
        return

    # Сохраняем новый список
    try:
        with open(instruments_file, "w", encoding="utf-8") as f:
            json.dump(new_symbols, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Список обновлен и сохранен в {instruments_file}")

        # Показываем статистику
        logger.info("📊 СТАТИСТИКА ОБНОВЛЕНИЯ:")
        logger.info(f"   • Всего символов: {len(new_symbols)}")
        logger.info(
            f"   • Приоритетных: {len([s for s in new_symbols if s in priority_symbols])}"
        )
        logger.info(
            f"   • Обычных: {len([s for s in new_symbols if s not in priority_symbols])}"
        )
        if added:
            logger.info(f"   • Добавлено: {len(added)}")
        if removed:
            logger.info(f"   • Удалено: {len(removed)}")

    except Exception as e:
        logger.error(f"❌ Ошибка сохранения списка: {e}")
        raise


async def main():
    """Основная функция для запуска обновления"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    logger.info("🚀 Запуск автообновления списка инструментов")
    await update_instruments_list()
    logger.info("✅ Автообновление завершено")


if __name__ == "__main__":
    asyncio.run(main())
