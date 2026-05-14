"""
Схема базы данных для модуля market_meta.

Содержит таблицы для хранения метаданных инструментов,
валидаторов и кэша.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class MarketMetadata(Base):
    """Таблица метаданных рынка"""

    __tablename__ = "market_meta"

    id = Column(Integer, primary_key=True)
    symbol_id = Column(String(50), nullable=False, index=True)
    inst_id = Column(String(50), nullable=False)
    inst_type = Column(String(20), nullable=False)  # SPOT, SWAP, FUTURES, OPTIONS
    base_ccy = Column(String(10), nullable=False)
    quote_ccy = Column(String(10), nullable=False)
    settle_ccy = Column(String(10), nullable=True)

    # Размеры тика и лота
    tick_size_step = Column(Float, nullable=True)
    tick_size_min = Column(Float, nullable=True)
    tick_size_max = Column(Float, nullable=True)

    lot_size_step = Column(Float, nullable=True)
    lot_size_min = Column(Float, nullable=True)
    lot_size_max = Column(Float, nullable=True)

    # Номинальная стоимость и комиссии
    contract_val = Column(Float, nullable=True)
    fee_maker = Column(Float, nullable=True)  # Комиссия мейкера (в %)
    fee_taker = Column(Float, nullable=True)  # Комиссия тейкера (в %)

    # Плечо и маржа
    max_leverage = Column(Float, nullable=True)
    margin_mode = Column(String(20), nullable=True)  # ISOLATED, CROSS
    position_mode = Column(String(20), nullable=True)  # LONG_SHORT, NET
    maint_margin_rate = Column(Float, nullable=True)

    # Ставка финансирования
    funding_rate = Column(Float, nullable=True)
    next_funding_time = Column(DateTime, nullable=True)
    funding_interval_hours = Column(Integer, nullable=True)

    # Параметры ликвидности
    min_volume_24h = Column(Float, nullable=True)
    min_trades_24h = Column(Integer, nullable=True)
    spread_threshold = Column(Float, nullable=True)  # Максимальный спред в %

    # Статус и временные метки
    state = Column(
        String(20), nullable=False, default="live"
    )  # live, suspended, expired
    is_tradable = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Индексы
    __table_args__ = (
        Index("idx_market_meta_symbol_id", "symbol_id"),
        Index("idx_market_meta_inst_type", "inst_type"),
        Index("idx_market_meta_tradable", "is_tradable"),
        Index("idx_market_meta_updated", "updated_at"),
        UniqueConstraint("symbol_id", name="uq_market_meta_symbol_id"),
    )


class ValidationCache(Base):
    """Кэш результатов валидации"""

    __tablename__ = "validation_cache"

    id = Column(Integer, primary_key=True)
    symbol_id = Column(String(50), nullable=False, index=True)
    validation_type = Column(String(50), nullable=False)  # order, risk, liquidity
    params_hash = Column(String(64), nullable=False)  # Хеш параметров валидации
    result = Column(Text, nullable=False)  # JSON результат валидации
    is_valid = Column(Boolean, nullable=False)
    violations = Column(Text, nullable=True)  # JSON список нарушений
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)  # TTL для кэша

    # Индексы
    __table_args__ = (
        Index("idx_validation_cache_symbol_type", "symbol_id", "validation_type"),
        Index("idx_validation_cache_expires", "expires_at"),
        Index("idx_validation_cache_params", "params_hash"),
    )


class RiskLimits(Base):
    """Лимиты риска по инструментам"""

    __tablename__ = "risk_limits"

    id = Column(Integer, primary_key=True)
    symbol_id = Column(String(50), nullable=False, index=True)
    risk_level = Column(String(20), nullable=False)  # LOW, MEDIUM, HIGH

    # Лимиты позиций
    max_position_size = Column(Float, nullable=True)
    max_notional_value = Column(Float, nullable=True)
    max_position_size_pct = Column(Float, nullable=True)  # % от баланса

    # Лимиты экспозиции
    max_total_exposure_pct = Column(Float, nullable=True)
    max_daily_loss_pct = Column(Float, nullable=True)
    max_weekly_loss_pct = Column(Float, nullable=True)

    # Лимиты корреляции
    max_correlation = Column(Float, nullable=True)
    cooldown_hours = Column(Integer, nullable=True)

    # Временные метки
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Индексы
    __table_args__ = (
        Index("idx_risk_limits_symbol_risk", "symbol_id", "risk_level"),
        UniqueConstraint("symbol_id", "risk_level", name="uq_risk_limits_symbol_risk"),
    )


class ValidationLog(Base):
    """Лог валидаций для аудита"""

    __tablename__ = "validation_log"

    id = Column(Integer, primary_key=True)
    run_id = Column(String(50), nullable=False, index=True)
    symbol_id = Column(String(50), nullable=False, index=True)
    validation_type = Column(String(50), nullable=False)

    # Параметры валидации
    price = Column(Float, nullable=True)
    qty = Column(Float, nullable=True)
    leverage = Column(Float, nullable=True)
    margin_mode = Column(String(20), nullable=True)

    # Результат
    is_valid = Column(Boolean, nullable=False)
    violations = Column(Text, nullable=True)  # JSON список нарушений
    processing_time_ms = Column(Integer, nullable=True)

    # Метаданные
    algo_version = Column(String(50), nullable=True)
    params_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Индексы
    __table_args__ = (
        Index("idx_validation_log_run_id", "run_id"),
        Index("idx_validation_log_symbol_time", "symbol_id", "created_at"),
        Index("idx_validation_log_type_time", "validation_type", "created_at"),
    )


class MarketDataExt(Base):  # НОВАЯ модель
    """Модель расширенных рыночных данных (временные ряды)"""

    __tablename__ = "market_data_ext"

    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(50), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)

    # Open Interest
    open_interest = Column(Numeric(20, 8))
    oi_change_24h = Column(Numeric(20, 8))
    oi_change_pct_24h = Column(Numeric(10, 6))

    # Funding Rates
    funding_rate = Column(Numeric(10, 8))
    next_funding_time = Column(DateTime(timezone=True))
    funding_interval_hours = Column(Integer)

    # L2 Order Book (v1: только базовые метрики)
    bid_imbalance = Column(Numeric(10, 6))
    ask_imbalance = Column(Numeric(10, 6))
    spread_bps = Column(Numeric(10, 2))

    # Метаданные
    source = Column(String(20), nullable=False, default="okx")
    bar_timestamp = Column(DateTime(timezone=True))
    timeframe = Column(String(10))

    # Версионирование (NOT NULL — всегда должны быть заполнены)
    run_id = Column(String(100), nullable=False)
    algo_version = Column(String(50), nullable=False)
    params_hash = Column(String(64), nullable=False)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "idx_market_data_ext_symbol_timeframe_bar_ts",
            "symbol",
            "timeframe",
            "bar_timestamp",
        ),
        Index("idx_market_data_ext_timestamp", "timestamp"),
        UniqueConstraint(
            "symbol",
            "timeframe",
            "bar_timestamp",
            name="uq_market_data_ext_symbol_timeframe_bar_ts",
        ),
    )


class MarketDataExtRepository:
    """
    Репозиторий для работы с market_data_ext.

    v1: синхронный на SQLAlchemy Core для простоты интеграции.
    asyncpg и полностью async-репозиторий — отдельная фаза при необходимости.
    """

    def __init__(self, engine):
        """
        Инициализация репозитория.

        Args:
            engine: SQLAlchemy engine для подключения к БД
        """
        self.engine = engine

    def upsert_records(
        self,
        records: list[dict[str, Any]],
        batch_size: int = 1000,
    ) -> int:
        """
        UPSERT записей в БД с идемпотентностью.

        Использует SQLAlchemy Core с INSERT ... ON CONFLICT.
        Бизнес-ключ: (symbol, timeframe, bar_timestamp)

        Политика DO_NOT_OVERWRITE_NON_NULL_WITH_NULL:
        - Поля данных (OI, funding, L2) используют COALESCE
        - Метаданные (algo_version, run_id, params_hash) всегда перезаписываются

        Args:
            records: Список записей для вставки/обновления
            batch_size: Размер батча для обработки

        Returns:
            Количество обработанных записей
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from .upsert_builder import (
            MARKET_DATA_EXT_COALESCE_FIELDS,
            MARKET_DATA_EXT_SKIP_FIELDS,
            build_upsert_set_clause,
        )

        if not records:
            return 0

        total_inserted = 0
        table = MarketDataExt.__table__

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            stmt = pg_insert(table).values(batch)

            update_dict = build_upsert_set_clause(
                stmt=stmt,
                table_columns=list(table.columns),
                coalesce_fields=MARKET_DATA_EXT_COALESCE_FIELDS,
                skip_fields=MARKET_DATA_EXT_SKIP_FIELDS,
            )

            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "timeframe", "bar_timestamp"],
                set_=update_dict,
            )
            with self.engine.begin() as conn:
                result = conn.execute(stmt)
                total_inserted += result.rowcount

        return total_inserted

    def get_latest(
        self,
        symbol: str,
        timeframe: str | None = None,
    ) -> MarketDataExt | None:
        """
        Получить последнюю запись для символа и таймфрейма.

        Args:
            symbol: Символ инструмента
            timeframe: Таймфрейм (опционально)

        Returns:
            Последняя запись или None
        """
        from sqlalchemy import select

        stmt = select(MarketDataExt).where(MarketDataExt.symbol == symbol)
        if timeframe:
            stmt = stmt.where(MarketDataExt.timeframe == timeframe)
        stmt = stmt.order_by(MarketDataExt.bar_timestamp.desc()).limit(1)

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            return result.scalar_one_or_none()

    def get_by_timeframe(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[MarketDataExt]:
        """
        Получить данные за период.

        Args:
            symbol: Символ инструмента
            timeframe: Таймфрейм
            start_time: Начало периода
            end_time: Конец периода

        Returns:
            Список записей
        """
        from sqlalchemy import select

        stmt = (
            select(MarketDataExt)
            .where(
                MarketDataExt.symbol == symbol,
                MarketDataExt.timeframe == timeframe,
                MarketDataExt.bar_timestamp >= start_time,
                MarketDataExt.bar_timestamp <= end_time,
            )
            .order_by(MarketDataExt.bar_timestamp)
        )

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            return list(result.scalars().all())

    def hard_reprocess(
        self,
        records: list[dict[str, Any]],
        symbol: str,
        timeframe: str,
        t0: datetime,
        t1: datetime,
        *,
        dry_run: bool = True,
    ) -> int:
        """
        Hard reprocess: DELETE окна + INSERT новых данных в транзакции.

        Используется когда нужно гарантированно заменить данные,
        а не дозаписать через COALESCE.

        Args:
            records: Новые записи для вставки.
            symbol: Символ инструмента.
            timeframe: Таймфрейм.
            t0: Начало окна (включительно).
            t1: Конец окна (исключительно).
            dry_run: Если True, только печатает план.

        Returns:
            Количество вставленных записей.
        """
        from sqlalchemy import delete
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        if dry_run:
            print(f"[DRY-RUN] Hard reprocess для {symbol}/{timeframe}")
            print(f"  Окно: {t0} - {t1}")
            print(f"  Будет удалено записей в окне, вставлено: {len(records)}")
            return len(records)

        table = MarketDataExt.__table__

        with self.engine.begin() as conn:
            # DELETE в окне
            del_stmt = delete(table).where(
                table.c.symbol == symbol,
                table.c.timeframe == timeframe,
                table.c.bar_timestamp >= t0,
                table.c.bar_timestamp < t1,
            )
            del_result = conn.execute(del_stmt)
            print(f"[HARD REPROCESS] Удалено {del_result.rowcount} записей")

            # INSERT новых
            if records:
                ins_stmt = pg_insert(table).values(records)
                ins_result = conn.execute(ins_stmt)
                return ins_result.rowcount

        return 0


# Функции для работы с базой данных
def create_tables(engine):
    """Создает все таблицы market_meta"""
    Base.metadata.create_all(engine)


def drop_tables(engine):
    """Удаляет все таблицы market_meta"""
    Base.metadata.drop_all(engine)
