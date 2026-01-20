import asyncio
import json
import logging
import os

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.database import AsyncSessionLocal
from src.models import Instrument
from src.okx.market import OKXMarket


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


async def fetch_and_upsert_instruments():
    logging.info("Вызов OKX API (SWAP)...")
    async with OKXMarket() as client:
        instruments = await client.get_instruments("SWAP")
        if not instruments:
            logging.error("❌ Не удалось получить инструменты от OKX API")
            return
        # Фильтруем только свопы с settleCcy == 'USDT'
        instruments = [i for i in instruments if i.get("settleCcy") == "USDT"]
    logging.info(f"Получено SWAP инструментов с settleCcy=USDT: {len(instruments)}")

    async with AsyncSessionLocal() as session:
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
            elif result.rowcount == 0:
                updated_count += 1
        await session.commit()
        logging.info(f"Загружено новых: {new_count}, обновлено: {updated_count}")

        # Автоматически обновляем файл instruments_list.json если есть новые инструменты
        if new_count > 0:
            logging.info(
                f"🔄 Обновляем файл instruments_list.json (добавлено {new_count} новых инструментов)..."
            )
            await update_instruments_list_file()
            logging.info("✅ Файл instruments_list.json обновлен")


async def print_instruments_count():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Instrument))
        count = len(result.scalars().all())
        logging.info(f"Всего записей в таблице instruments: {count}")


def get_priority_sorted_instruments(
    instruments, priority=("BTC-USDT-SWAP", "ETH-USDT-SWAP")
):
    # Сначала приоритетные, потом остальные по алфавиту
    priority_list = [inst for inst in instruments if inst.symbol in priority]
    rest = sorted(
        [inst for inst in instruments if inst.symbol not in priority],
        key=lambda x: x.symbol,
    )
    return priority_list + rest


async def save_sorted_instruments_to_file(filename="instruments_list.json"):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Instrument).where(
                Instrument.settle_ccy == "USDT",
                Instrument.inst_type == "SWAP",  # было instType
            )
        )
        instruments = result.scalars().all()
        sorted_instruments = get_priority_sorted_instruments(instruments)
        symbols = [inst.symbol for inst in sorted_instruments]
        with open(
            os.path.join(os.path.dirname(__file__), "..", filename),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(symbols, f, ensure_ascii=False, indent=2)


async def update_instruments_list_file(filename="instruments_list.json"):
    import json
    import os

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Instrument).where(
                Instrument.settle_ccy == "USDT", Instrument.inst_type == "SWAP"
            )
        )
        instruments = result.scalars().all()
        symbols_db = {inst.symbol for inst in instruments}

    file_path = os.path.join(os.path.dirname(__file__), "..", filename)

    # Получаем все символы (из БД и файла)
    all_symbols = symbols_db
    if os.path.exists(file_path):
        with open(file_path, encoding="utf-8") as f:
            symbols_file = set(json.load(f))
        all_symbols = symbols_db | symbols_file

    # Сортируем с приоритетом
    priority_symbols = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    sorted_symbols = []

    # Сначала добавляем приоритетные
    for symbol in priority_symbols:
        if symbol in all_symbols:
            sorted_symbols.append(symbol)

    # Затем добавляем остальные по алфавиту
    for symbol in sorted(all_symbols):
        if symbol not in priority_symbols:
            sorted_symbols.append(symbol)

    # Сохраняем в файл
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(sorted_symbols, f, ensure_ascii=False, indent=2)

    logging.info(f"📊 Обновлен файл {filename}: {len(sorted_symbols)} символов")
    logging.info(
        f"📋 Приоритетные символы: {[s for s in sorted_symbols if s in priority_symbols]}"
    )


if __name__ == "__main__":
    asyncio.run(fetch_and_upsert_instruments())
    asyncio.run(print_instruments_count())
