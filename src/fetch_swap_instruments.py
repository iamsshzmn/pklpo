"""
Получение и заполнение SWAP данных в таблицу instruments.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text

from src.database import get_async_session
from src.okx.market import OKXMarket


async def fetch_and_update_swap_instruments():
    """Получает SWAP данные и обновляет таблицу instruments"""

    print("🔍 Получение SWAP данных из OKX API")
    print("=" * 80)

    # Инициализируем клиент OKX
    async with OKXMarket() as client:
        # Получаем список всех инструментов
        swap_instruments = await client.get_usdt_swap()

        if not swap_instruments:
            print("❌ Не удалось получить данные инструментов")
            return
        print(f"📊 Получено {len(swap_instruments)} SWAP инструментов")

        # Используем значения по умолчанию для комиссий и финансирования
        print("📊 Используем значения по умолчанию для комиссий и финансирования")

        async for session in get_async_session():
            try:
                updated_count = 0

                for instrument in swap_instruments:
                    symbol = instrument["instId"]

                    # Используем значения по умолчанию
                    maker_fee = 0.0001  # 0.01%
                    taker_fee = 0.0005  # 0.05%
                    funding_rate = 0.0

                    # Обновляем данные в базе
                    update_query = text(
                        """
                        UPDATE instruments
                        SET
                            margin_mode = :margin_mode,
                            tick_size = :tick_size,
                            lot_size = :lot_size,
                            maker_fee = :maker_fee,
                            taker_fee = :taker_fee,
                            maintenance_margin_rate = :maintenance_margin_rate,
                            max_leverage = :max_leverage,
                            funding_rate = :funding_rate
                        WHERE symbol = :symbol
                    """
                    )

                    await session.execute(
                        update_query,
                        {
                            "symbol": symbol,
                            "margin_mode": "isolated",  # По умолчанию
                            "tick_size": float(instrument.get("tickSz", "0.01")),
                            "lot_size": float(instrument.get("lotSz", "0.01")),
                            "maker_fee": maker_fee,
                            "taker_fee": taker_fee,
                            "maintenance_margin_rate": 0.005,  # 0.5% по умолчанию
                            "max_leverage": min(
                                int(instrument.get("maxLmtSz", "100")), 32767
                            ),  # Ограничиваем int16
                            "funding_rate": funding_rate,
                        },
                    )

                    updated_count += 1

                    if updated_count % 10 == 0:
                        print(f"✅ Обновлено {updated_count} инструментов...")

                await session.commit()
                print(f"✅ Всего обновлено {updated_count} SWAP инструментов")

            except Exception as e:
                print(f"❌ Ошибка при обновлении базы данных: {e}")
                await session.rollback()
            finally:
                break


if __name__ == "__main__":
    asyncio.run(fetch_and_update_swap_instruments())
