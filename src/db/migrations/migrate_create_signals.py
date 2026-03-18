import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import BigInteger, Column, DateTime, Numeric, String, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.declarative import declarative_base

from src.database import DATABASE_URL

Base = declarative_base()


class Signal(Base):
    __tablename__ = "signals"
    symbol = Column(String, primary_key=True)
    timeframe = Column(String, primary_key=True)
    ts = Column(BigInteger, primary_key=True)  # timestamp в миллисекундах
    signal = Column(Numeric)  # -1 = sell, 0 = hold, 1 = buy
    reason = Column(String, nullable=True)  # JSON-строка: какие правила сработали
    created_at = Column(DateTime, nullable=True)  # Время создания сигнала


async def create_signals_table():
    """Создает таблицу signals в базе данных"""
    engine = create_async_engine(DATABASE_URL, echo=True)

    async with engine.begin() as conn:
        # Проверяем, существует ли таблица
        result = await conn.execute(
            text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'signals')"
            )
        )
        table_exists = result.scalar()

        if not table_exists:
            print("Создаем таблицу signals...")
            await conn.run_sync(Base.metadata.create_all, tables=[Signal.__table__])
            print("Таблица signals создана успешно!")
        else:
            print("Таблица signals уже существует.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_signals_table())
