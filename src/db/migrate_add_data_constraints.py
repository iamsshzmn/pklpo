import asyncio
import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def create_timeframe_enum() -> None:
    """
    Создает ENUM для timeframe с валидными значениями.
    """
    logger.info("🔄 Создаем ENUM для timeframe...")

    async with get_db_session() as session:
        # Создаем ENUM для timeframe
        create_enum_q = text(
            """
            DO $$ BEGIN
                CREATE TYPE timeframe_enum AS ENUM (
                    '1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '1w', '1M',
                    '1Mutc', '1Dutc', '1Wutc'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """
        )

        await session.execute(create_enum_q)
        logger.info("✅ ENUM timeframe_enum создан/проверен")


async def create_inst_type_enum() -> None:
    """
    Создает ENUM для inst_type с валидными значениями.
    """
    logger.info("🔄 Создаем ENUM для inst_type...")

    async with get_db_session() as session:
        # Создаем ENUM для inst_type
        create_enum_q = text(
            """
            DO $$ BEGIN
                CREATE TYPE inst_type_enum AS ENUM (
                    'SPOT', 'MARGIN', 'SWAP', 'FUTURES', 'OPTION'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """
        )

        await session.execute(create_enum_q)
        logger.info("✅ ENUM inst_type_enum создан/проверен")


async def add_ohlcv_constraints() -> None:
    """
    Добавляет ограничения для таблицы ohlcv_p.
    """
    logger.info("🔄 Добавляем ограничения для ohlcv_p...")

    async with get_db_session() as session:
        # Добавляем PRIMARY KEY
        pk_q = text(
            """
            ALTER TABLE ohlcv_p
            ADD CONSTRAINT pk_ohlcv_p_symbol_timeframe_timestamp
            PRIMARY KEY (symbol, timeframe, timestamp);
        """
        )

        try:
            await session.execute(pk_q)
            logger.info("✅ PRIMARY KEY добавлен для ohlcv_p")
        except Exception as e:
            logger.warning(f"⚠️ PRIMARY KEY уже существует: {e}")

        # Добавляем CHECK ограничения
        check_volume_q = text(
            """
            ALTER TABLE ohlcv_p
            ADD CONSTRAINT chk_ohlcv_p_volume_positive
            CHECK (volume >= 0);
        """
        )

        try:
            await session.execute(check_volume_q)
            logger.info("✅ CHECK volume >= 0 добавлен")
        except Exception as e:
            logger.warning(f"⚠️ CHECK volume уже существует: {e}")

        check_prices_q = text(
            """
            ALTER TABLE ohlcv_p
            ADD CONSTRAINT chk_ohlcv_p_prices_positive
            CHECK (open > 0 AND high > 0 AND low > 0 AND close > 0);
        """
        )

        try:
            await session.execute(check_prices_q)
            logger.info("✅ CHECK prices > 0 добавлен")
        except Exception as e:
            logger.warning(f"⚠️ CHECK prices уже существует: {e}")

        check_high_low_q = text(
            """
            ALTER TABLE ohlcv_p
            ADD CONSTRAINT chk_ohlcv_p_high_low
            CHECK (high >= low);
        """
        )

        try:
            await session.execute(check_high_low_q)
            logger.info("✅ CHECK high >= low добавлен")
        except Exception as e:
            logger.warning(f"⚠️ CHECK high_low уже существует: {e}")

        await session.commit()


async def add_indicators_constraints() -> None:
    """
    Добавляет ограничения для таблицы indicators_p.
    """
    logger.info("🔄 Добавляем ограничения для indicators_p...")

    async with get_db_session() as session:
        # Добавляем PRIMARY KEY
        pk_q = text(
            """
            ALTER TABLE indicators_p
            ADD CONSTRAINT pk_indicators_p_symbol_timeframe_timestamp
            PRIMARY KEY (symbol, timeframe, timestamp);
        """
        )

        try:
            await session.execute(pk_q)
            logger.info("✅ PRIMARY KEY добавлен для indicators_p")
        except Exception as e:
            logger.warning(f"⚠️ PRIMARY KEY уже существует: {e}")

        await session.commit()


async def add_instruments_constraints() -> None:
    """
    Добавляет ограничения для таблицы instruments.
    """
    logger.info("🔄 Добавляем ограничения для instruments...")

    async with get_db_session() as session:
        # Добавляем UNIQUE constraint для symbol
        unique_symbol_q = text(
            """
            ALTER TABLE instruments
            ADD CONSTRAINT uk_instruments_symbol
            UNIQUE (symbol);
        """
        )

        try:
            await session.execute(unique_symbol_q)
            logger.info("✅ UNIQUE constraint для symbol добавлен")
        except Exception as e:
            logger.warning(f"⚠️ UNIQUE symbol уже существует: {e}")

        # Добавляем CHECK ограничения
        check_tick_size_q = text(
            """
            ALTER TABLE instruments
            ADD CONSTRAINT chk_instruments_tick_size_positive
            CHECK (tick_size > 0);
        """
        )

        try:
            await session.execute(check_tick_size_q)
            logger.info("✅ CHECK tick_size > 0 добавлен")
        except Exception as e:
            logger.warning(f"⚠️ CHECK tick_size уже существует: {e}")

        check_lot_size_q = text(
            """
            ALTER TABLE instruments
            ADD CONSTRAINT chk_instruments_lot_size_positive
            CHECK (lot_size > 0);
        """
        )

        try:
            await session.execute(check_lot_size_q)
            logger.info("✅ CHECK lot_size > 0 добавлен")
        except Exception as e:
            logger.warning(f"⚠️ CHECK lot_size уже существует: {e}")

        await session.commit()


async def add_partial_indexes() -> None:
    """
    Добавляет частичные индексы для полей с множеством NULL значений.
    """
    logger.info("🔄 Добавляем частичные индексы...")

    async with get_db_session() as session:
        # Частичный индекс для non-NULL maker_fee
        maker_fee_idx_q = text(
            """
            CREATE INDEX IF NOT EXISTS idx_instruments_maker_fee_not_null
            ON instruments(maker_fee)
            WHERE maker_fee IS NOT NULL;
        """
        )

        await session.execute(maker_fee_idx_q)
        logger.info("✅ Частичный индекс для maker_fee добавлен")

        # Частичный индекс для non-NULL taker_fee
        taker_fee_idx_q = text(
            """
            CREATE INDEX IF NOT EXISTS idx_instruments_taker_fee_not_null
            ON instruments(taker_fee)
            WHERE taker_fee IS NOT NULL;
        """
        )

        await session.execute(taker_fee_idx_q)
        logger.info("✅ Частичный индекс для taker_fee добавлен")

        # Частичный индекс для non-NULL funding_rate
        funding_rate_idx_q = text(
            """
            CREATE INDEX IF NOT EXISTS idx_instruments_funding_rate_not_null
            ON instruments(funding_rate)
            WHERE funding_rate IS NOT NULL;
        """
        )

        await session.execute(funding_rate_idx_q)
        logger.info("✅ Частичный индекс для funding_rate добавлен")

        await session.commit()


async def validate_data_quality() -> None:
    """
    Проверяет качество данных после добавления ограничений.
    """
    logger.info("🔍 Проверяем качество данных...")

    async with get_db_session() as session:
        # Проверяем дубликаты в ohlcv_p
        duplicates_ohlcv_q = text(
            """
            SELECT symbol, timeframe, timestamp, COUNT(*) as cnt
            FROM ohlcv_p
            GROUP BY symbol, timeframe, timestamp
            HAVING COUNT(*) > 1
            LIMIT 10;
        """
        )

        duplicates = await session.execute(duplicates_ohlcv_q)
        duplicate_rows = duplicates.fetchall()

        if duplicate_rows:
            logger.warning(
                f"⚠️ Найдены дубликаты в ohlcv_p: {len(duplicate_rows)} групп"
            )
            for row in duplicate_rows:
                logger.warning(f"   {row[0]}, {row[1]}, {row[2]}: {row[3]} записей")
        else:
            logger.info("✅ Дубликатов в ohlcv_p не найдено")

        # Проверяем отрицательные объемы
        negative_volume_q = text(
            """
            SELECT COUNT(*) as cnt
            FROM ohlcv_p
            WHERE volume < 0;
        """
        )

        negative_volume = await session.execute(negative_volume_q)
        negative_count = negative_volume.scalar()

        if negative_count > 0:
            logger.warning(
                f"⚠️ Найдено {negative_count} записей с отрицательным объемом"
            )
        else:
            logger.info("✅ Записей с отрицательным объемом не найдено")

        # Проверяем некорректные цены
        invalid_prices_q = text(
            """
            SELECT COUNT(*) as cnt
            FROM ohlcv_p
            WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0;
        """
        )

        invalid_prices = await session.execute(invalid_prices_q)
        invalid_count = invalid_prices.scalar()

        if invalid_count > 0:
            logger.warning(f"⚠️ Найдено {invalid_count} записей с некорректными ценами")
        else:
            logger.info("✅ Записей с некорректными ценами не найдено")

        # Проверяем high < low
        invalid_high_low_q = text(
            """
            SELECT COUNT(*) as cnt
            FROM ohlcv_p
            WHERE high < low;
        """
        )

        invalid_high_low = await session.execute(invalid_high_low_q)
        invalid_hl_count = invalid_high_low.scalar()

        if invalid_hl_count > 0:
            logger.warning(f"⚠️ Найдено {invalid_hl_count} записей где high < low")
        else:
            logger.info("✅ Записей где high < low не найдено")


async def run_data_constraints_migration() -> None:
    """
    Основная функция для выполнения миграции ограничений качества данных.
    """
    logger.info("🚀 Начинаем миграцию ограничений качества данных...")

    try:
        # Создаем ENUM типы
        await create_timeframe_enum()
        await create_inst_type_enum()

        # Добавляем ограничения
        await add_ohlcv_constraints()
        await add_indicators_constraints()
        await add_instruments_constraints()

        # Добавляем частичные индексы
        await add_partial_indexes()

        # Проверяем качество данных
        await validate_data_quality()

        logger.info("✅ Миграция ограничений качества данных завершена успешно!")

    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении миграции ограничений: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_data_constraints_migration())
