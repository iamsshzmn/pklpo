import asyncio
import datetime
import json
import logging
from pathlib import Path

from aiolimiter import AsyncLimiter
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from tqdm import tqdm

from src.database import AsyncSessionLocal
from src.models import OHLCV, Instrument
from src.okx.market import OKXMarket

BARS = ["1m", "5m", "15m", "1H", "4H", "1Dutc", "1Wutc", "1Mutc"]

# Конфигурация
INSTRUMENTS_FILE = (
    Path(__file__).resolve().parent.parent.parent / "instruments_list.json"
)


async def sync_bar(inst, bar, client):
    """Синхронизация одного таймфрейма для одного инструмента."""
    symbol = inst.symbol
    async with AsyncSessionLocal() as session:
        before = None
        total = 0
        while True:
            try:
                async with client._public_limiter:
                    async with client.get_instrument_limiter(symbol):
                        candles = await client.get_candles(
                            inst_id=symbol,
                            bar=bar,
                            limit=300,
                            before=before,
                        )
            except RuntimeError as e:
                if "51000" in str(e) and "Parameter bar error" in str(e):
                    logging.warning(
                        f"{symbol}: Таймфрейм {bar} не поддерживается, "
                        "пропускаю только этот bar."
                    )
                    return
                logging.error(f"Ошибка при получении свечей {symbol} {bar}: {e}")
                raise

            if not candles:
                break

            for c in candles:
                # Извлекаем значения заранее для избежания дублирования
                vol_ccy = c.get("volCcy")
                vol_usd = c.get("volUsd")
                fetched_at = datetime.datetime.utcnow()

                # Базовые данные для вставки/обновления
                base_data = {
                    "symbol": symbol,
                    "timeframe": bar,
                    "ts": c["ts"],
                    "open": c["open"],
                    "high": c["high"],
                    "low": c["low"],
                    "close": c["close"],
                    "volume": c["volume"],
                    "volCcy": vol_ccy,
                    "volUsd": vol_usd,
                    "fetched_at": fetched_at,
                }

                stmt = (
                    pg_insert(OHLCV)
                    .values(**base_data)
                    .on_conflict_do_update(
                        index_elements=[
                            OHLCV.symbol,
                            OHLCV.timeframe,
                            OHLCV.ts,
                        ],
                        set_=base_data,
                    )
                )
                await session.execute(stmt)

            await session.commit()
            total += len(candles)
            tqdm.write(f"{symbol} {bar}: +{len(candles)} " f"(total {total})")

            if len(candles) < 300:
                break
            before = str(candles[-1]["ts"])


async def sync_symbol(inst, client):
    """Синхронизация всех таймфреймов для одного инструмента."""
    await asyncio.gather(*(sync_bar(inst, bar, client) for bar in BARS))


async def fetch_and_sync_candles(symbol=None):
    """Основная функция синхронизации свечей."""
    public_limiter = AsyncLimiter(90, 1)

    # Если указан конкретный символ, обрабатываем только его
    if symbol:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Instrument).where(Instrument.symbol == symbol)
            )
            instruments = result.scalars().all()

        if not instruments:
            logging.warning(f"Символ {symbol} не найден в базе данных")
            return

        logging.info(f"Синхронизация свечей только для символа: {symbol}")
    else:
        # Читаем список символов из файла, если есть
        if INSTRUMENTS_FILE.exists():
            with open(INSTRUMENTS_FILE, encoding="utf-8") as f:
                symbols = json.load(f)

            # Получаем объекты Instrument только для этих символов
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Instrument).where(Instrument.symbol.in_(symbols))
                )
                instruments = result.scalars().all()

            # Сортируем в том же порядке, что и в файле
            instruments = sorted(instruments, key=lambda x: symbols.index(x.symbol))
        else:
            async with AsyncSessionLocal() as session:
                instruments = (
                    (
                        await session.execute(
                            select(Instrument).where(
                                Instrument.settle_ccy == "USDT",
                                Instrument.instType == "SWAP",
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
            instruments = sorted(instruments, key=lambda x: x.symbol)

    with tqdm(total=len(instruments), desc="Инструменты", ncols=100) as pbar_inst:
        async with OKXMarket(public_limiter=public_limiter) as client:
            for inst in instruments:
                await sync_symbol(inst, client)
                pbar_inst.update(1)

    logging.info("Синхронизация завершена.")


if __name__ == "__main__":
    asyncio.run(fetch_and_sync_candles())
