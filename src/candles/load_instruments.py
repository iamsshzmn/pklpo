#!/usr/bin/env python3
"""
Автономный модуль для загрузки инструментов из OKX API.
"""

import asyncio
import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.market_meta.infrastructure.market import OKXMarket
from src.models import Instrument
from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


def extract_currencies_from_symbol(symbol):
    """
    Извлекает базовую и котируемую валюты из символа инструмента.
    Примеры: BTC-USDT-SWAP -> (BTC, USDT)
    """
    if not symbol:
        return None, None

    parts = symbol.split("-")
    if len(parts) >= 2:
        base_ccy = parts[0]
        quote_ccy = parts[1]
        return base_ccy, quote_ccy

    return None, None


async def save_instruments_to_db(instruments: list, inst_type: str) -> tuple[int, int]:
    """
    Сохраняет инструменты в базу данных.

    Args:
        instruments: Список инструментов от API
        inst_type: Тип инструментов

    Returns:
        Кортеж (новые, обновленные)
    """
    async with get_db_session() as session:
        new_count = 0
        updated_count = 0

        for item in instruments:
            # Извлекаем валюты из symbol, если API не предоставил их
            symbol = item.get("instId")
            base_ccy = item.get("baseCcy")
            quote_ccy = item.get("quoteCcy")

            # Если API не предоставил валюты, извлекаем из symbol
            if not base_ccy or not quote_ccy:
                extracted_base, extracted_quote = extract_currencies_from_symbol(symbol)
                base_ccy = base_ccy or extracted_base
                quote_ccy = quote_ccy or extracted_quote

            stmt = (
                pg_insert(Instrument)
                .values(
                    symbol=symbol,  # symbol = instId
                    inst_id=symbol,  # было instId
                    base_ccy=base_ccy,  # было baseCcy
                    quote_ccy=quote_ccy,  # было quoteCcy
                    inst_type=item.get("instType"),  # было instType
                    state=item.get("state"),
                    list_time=(
                        int(item.get("listTime", 0)) if item.get("listTime") else None
                    ),  # было listTime
                    # Новые поля для свопов
                    contract_val=(
                        float(item.get("ctVal", 0)) if item.get("ctVal") else None
                    ),  # было ctVal
                    settle_ccy=item.get("settleCcy"),
                    ct_type=item.get("ctType"),
                    min_sz=(
                        float(item.get("minSz", 0)) if item.get("minSz") else None
                    ),  # было minSz
                    max_sz=(
                        float(item.get("maxSz", 0)) if item.get("maxSz") else None
                    ),  # было maxSz
                    min_notional=(
                        float(item.get("minNotional", 0))
                        if item.get("minNotional")
                        else None
                    ),  # было minNotional
                )
                .on_conflict_do_update(
                    index_elements=[Instrument.inst_id],  # было instId
                    set_={
                        "base_ccy": base_ccy,  # было baseCcy
                        "quote_ccy": quote_ccy,  # было quoteCcy
                        "inst_type": item.get("instType"),  # было instType
                        "state": item.get("state"),
                        "list_time": (
                            int(item.get("listTime", 0))
                            if item.get("listTime")
                            else None
                        ),  # было listTime
                        # Обновляем новые поля для свопов
                        "contract_val": (
                            float(item.get("ctVal", 0)) if item.get("ctVal") else None
                        ),  # было ctVal
                        "settle_ccy": item.get("settleCcy"),
                        "ct_type": item.get("ctType"),
                        "min_sz": (
                            float(item.get("minSz", 0)) if item.get("minSz") else None
                        ),  # было minSz
                        "max_sz": (
                            float(item.get("maxSz", 0)) if item.get("maxSz") else None
                        ),  # было maxSz
                        "min_notional": (
                            float(item.get("minNotional", 0))
                            if item.get("minNotional")
                            else None
                        ),  # было minNotional
                    },
                )
            )
            result = await session.execute(stmt)
            if result.rowcount == 1:
                new_count += 1
            else:
                updated_count += 1

        await session.commit()
        return new_count, updated_count


async def load_instruments() -> None:
    """
    Загружает инструменты из OKX API в базу данных.
    """
    try:
        logger.info("🔄 Запуск загрузки инструментов из OKX API")

        # Загружаем инструменты через OKXMarket (прямой доступ к API)
        inst_types = ["SWAP"]  # Только SWAP инструменты
        total_new = 0
        total_updated = 0

        async with OKXMarket() as client:
            for inst_type in inst_types:
                try:
                    logger.info(f"🔄 Загружаем {inst_type} инструменты...")
                    instruments = await client.get_instruments(inst_type)

                    if instruments:
                        logger.info(
                            f"📊 Получено {len(instruments)} {inst_type} инструментов"
                        )

                        # Сохраняем в БД
                        new_count, updated_count = await save_instruments_to_db(
                            instruments, inst_type
                        )
                        total_new += new_count
                        total_updated += updated_count

                        logger.info(
                            f"💾 {inst_type}: {new_count} новых, {updated_count} обновлено"
                        )
                    else:
                        logger.warning(f"⚠️ Не получено {inst_type} инструментов")

                except Exception as e:
                    logger.error(
                        f"❌ Ошибка загрузки {inst_type} инструментов: {e}",
                        exc_info=True,
                    )
                    raise  # Re-raise для корректного exit code

        logger.info(
            f"✅ Загрузка завершена: {total_new} новых, {total_updated} обновлено"
        )
    except Exception as e:
        logger.error(
            f"❌ Критическая ошибка при загрузке инструментов: {e}", exc_info=True
        )
        raise  # Re-raise чтобы процесс завершился с кодом 1


def register(subparsers):
    """Регистрирует команду в CLI"""
    p = subparsers.add_parser(
        "load-instruments", help="Загрузить инструменты из OKX API"
    )
    p.add_argument(
        "--force", action="store_true", help="Принудительно обновить все инструменты"
    )
    p.set_defaults(_handler=handle)


async def handle(args):
    """Обработчик CLI команды"""
    await load_instruments()


async def main():
    """Основная функция для запуска модуля"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    logger.info("🚀 Запуск модуля загрузки инструментов")
    await load_instruments()
    logger.info("✅ Модуль завершен")


if __name__ == "__main__":
    asyncio.run(main())
