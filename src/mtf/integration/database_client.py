"""
Database client for storing and retrieving MTF results
"""

from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from ..logging_config import create_log_context, get_integration_logger
from ..pipeline.models import PipelineResult

logger = get_integration_logger()


class DatabaseClient:
    """Клиент для работы с базой данных"""

    def __init__(self, database_url: str, pool_size: int = 10, timeout: float = 30.0):
        self.database_url = database_url
        self.pool_size = pool_size
        self.timeout = timeout

        # Создание асинхронного движка
        self.engine = create_async_engine(
            database_url, pool_size=pool_size, pool_timeout=timeout, echo=False
        )

        # Создание фабрики сессий
        self.session_factory = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

        logger.info(f"DatabaseClient initialized with URL: {database_url}")

    async def __aenter__(self):
        """Асинхронный контекстный менеджер - вход"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер - выход"""
        await self.engine.dispose()

    async def create_tables(self):
        """Создание таблиц для хранения результатов MTF"""
        with create_log_context("database_client", "create_tables"):
            async with self.engine.begin() as conn:
                # Таблица для результатов pipeline
                await conn.execute(
                    text(
                        """
                    CREATE TABLE IF NOT EXISTS mtf_pipeline_results (
                        id SERIAL PRIMARY KEY,
                        request_id VARCHAR(255) UNIQUE NOT NULL,
                        symbol VARCHAR(50) NOT NULL,
                        timeframes TEXT[] NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        processing_stage VARCHAR(50) NOT NULL,
                        context_result JSONB,
                        triggers_result JSONB,
                        consensus_result JSONB,
                        start_time TIMESTAMP,
                        end_time TIMESTAMP,
                        processing_time_seconds FLOAT,
                        errors TEXT[],
                        warnings TEXT[],
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                    )
                )

                # Таблица для рыночных данных
                await conn.execute(
                    text(
                        """
                    CREATE TABLE IF NOT EXISTS mtf_market_data (
                        id SERIAL PRIMARY KEY,
                        symbol VARCHAR(50) NOT NULL,
                        timeframe VARCHAR(10) NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        open DECIMAL(20, 8),
                        high DECIMAL(20, 8),
                        low DECIMAL(20, 8),
                        close DECIMAL(20, 8),
                        volume DECIMAL(20, 8),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol, timeframe, timestamp)
                    )
                """
                    )
                )

                # Таблица для метрик
                await conn.execute(
                    text(
                        """
                    CREATE TABLE IF NOT EXISTS mtf_metrics (
                        id SERIAL PRIMARY KEY,
                        metric_name VARCHAR(100) NOT NULL,
                        metric_value FLOAT NOT NULL,
                        metric_type VARCHAR(50) NOT NULL,
                        symbol VARCHAR(50),
                        timeframe VARCHAR(10),
                        timestamp TIMESTAMP NOT NULL,
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                    )
                )

                # Создание индексов
                await conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_mtf_pipeline_results_symbol
                    ON mtf_pipeline_results(symbol)
                """
                    )
                )

                await conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_mtf_pipeline_results_created_at
                    ON mtf_pipeline_results(created_at)
                """
                    )
                )

                await conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_mtf_market_data_symbol_timeframe
                    ON mtf_market_data(symbol, timeframe)
                """
                    )
                )

                await conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_mtf_market_data_timestamp
                    ON mtf_market_data(timestamp)
                """
                    )
                )

                await conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_mtf_metrics_metric_name
                    ON mtf_metrics(metric_name)
                """
                    )
                )

                await conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_mtf_metrics_timestamp
                    ON mtf_metrics(timestamp)
                """
                    )
                )

                logger.info("Database tables created successfully")

    async def save_pipeline_result(self, result: PipelineResult) -> bool:
        """Сохранение результата pipeline в базу данных"""
        with create_log_context("database_client", "save_pipeline_result"):
            try:
                async with self.session_factory() as session:
                    # Подготовка данных для сохранения
                    data = {
                        "request_id": result.request_id,
                        "symbol": result.symbol,
                        "timeframes": result.timeframes,
                        "status": result.status.value,
                        "processing_stage": result.processing_stage.value,
                        "start_time": result.start_time,
                        "end_time": result.end_time,
                        "processing_time_seconds": result.processing_time_seconds,
                        "errors": result.errors,
                        "warnings": result.warnings,
                        "metadata": result.metadata,
                    }

                    # Сериализация результатов компонентов
                    if result.context_result:
                        data["context_result"] = {
                            "symbol": result.context_result.symbol,
                            "overall_score": result.context_result.overall_score,
                            "dominant_regime": result.context_result.dominant_regime.value,
                            "confidence": result.context_result.confidence,
                            "valid": result.context_result.valid,
                            "timeframes": result.context_result.timeframes,
                        }

                    if result.triggers_result:
                        data["triggers_result"] = {
                            "symbol": result.triggers_result.symbol,
                            "overall_p_up": result.triggers_result.overall_p_up,
                            "overall_p_down": result.triggers_result.overall_p_down,
                            "dominant_acceleration": result.triggers_result.dominant_acceleration.value,
                            "valid": result.triggers_result.valid,
                            "timeframes": result.triggers_result.timeframes,
                        }

                    if result.consensus_result:
                        data["consensus_result"] = {
                            "symbol": result.consensus_result.symbol,
                            "consensus_type": result.consensus_result.consensus_type.value,
                            "confidence_level": result.consensus_result.confidence_level.value,
                            "final_score": result.consensus_result.final_score,
                            "is_valid": result.consensus_result.is_valid,
                        }

                    # Вставка данных
                    await session.execute(
                        text(
                            """
                        INSERT INTO mtf_pipeline_results
                        (request_id, symbol, timeframes, status, processing_stage,
                         context_result, triggers_result, consensus_result,
                         start_time, end_time, processing_time_seconds,
                         errors, warnings, metadata)
                        VALUES (:request_id, :symbol, :timeframes, :status, :processing_stage,
                                :context_result, :triggers_result, :consensus_result,
                                :start_time, :end_time, :processing_time_seconds,
                                :errors, :warnings, :metadata)
                        ON CONFLICT (request_id) DO UPDATE SET
                            status = EXCLUDED.status,
                            processing_stage = EXCLUDED.processing_stage,
                            context_result = EXCLUDED.context_result,
                            triggers_result = EXCLUDED.triggers_result,
                            consensus_result = EXCLUDED.consensus_result,
                            end_time = EXCLUDED.end_time,
                            processing_time_seconds = EXCLUDED.processing_time_seconds,
                            errors = EXCLUDED.errors,
                            warnings = EXCLUDED.warnings,
                            metadata = EXCLUDED.metadata
                    """
                        ),
                        data,
                    )

                    await session.commit()
                    logger.info(f"Pipeline result saved for {result.symbol}")
                    return True

            except Exception as e:
                logger.error(f"Failed to save pipeline result: {e}")
                return False

    async def save_market_data(
        self, symbol: str, timeframe: str, data: pd.DataFrame
    ) -> bool:
        """Сохранение рыночных данных в базу данных"""
        with create_log_context("database_client", "save_market_data"):
            try:
                if data.empty:
                    return True

                async with self.session_factory() as session:
                    # Подготовка данных для вставки
                    records = []
                    for timestamp, row in data.iterrows():
                        records.append(
                            {
                                "symbol": symbol,
                                "timeframe": timeframe,
                                "timestamp": timestamp,
                                "open": float(row["open"]),
                                "high": float(row["high"]),
                                "low": float(row["low"]),
                                "close": float(row["close"]),
                                "volume": float(row["volume"]),
                            }
                        )

                    # Вставка данных
                    await session.execute(
                        text(
                            """
                        INSERT INTO mtf_market_data
                        (symbol, timeframe, timestamp, open, high, low, close, volume)
                        VALUES (:symbol, :timeframe, :timestamp, :open, :high, :low, :close, :volume)
                        ON CONFLICT (symbol, timeframe, timestamp) DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume
                    """
                        ),
                        records,
                    )

                    await session.commit()
                    logger.info(
                        f"Market data saved for {symbol} {timeframe}: {len(records)} records"
                    )
                    return True

            except Exception as e:
                logger.error(f"Failed to save market data: {e}")
                return False

    async def get_pipeline_results(
        self, symbol: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Получение результатов pipeline из базы данных"""
        with create_log_context("database_client", "get_pipeline_results"):
            try:
                async with self.session_factory() as session:
                    query = """
                        SELECT * FROM mtf_pipeline_results
                    """
                    params = {}

                    if symbol:
                        query += " WHERE symbol = :symbol"
                        params["symbol"] = symbol

                    query += " ORDER BY created_at DESC LIMIT :limit"
                    params["limit"] = limit

                    result = await session.execute(text(query), params)
                    rows = result.fetchall()

                    # Преобразование в список словарей
                    results = []
                    for row in rows:
                        results.append(dict(row._mapping))

                    logger.info(f"Retrieved {len(results)} pipeline results")
                    return results

            except Exception as e:
                logger.error(f"Failed to get pipeline results: {e}")
                return []

    async def get_market_data(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> pd.DataFrame:
        """Получение рыночных данных из базы данных"""
        with create_log_context("database_client", "get_market_data"):
            try:
                async with self.session_factory() as session:
                    query = """
                        SELECT timestamp, open, high, low, close, volume
                        FROM mtf_market_data
                        WHERE symbol = :symbol AND timeframe = :timeframe
                    """
                    params = {"symbol": symbol, "timeframe": timeframe}

                    if start_time:
                        query += " AND timestamp >= :start_time"
                        params["start_time"] = start_time

                    if end_time:
                        query += " AND timestamp <= :end_time"
                        params["end_time"] = end_time

                    query += " ORDER BY timestamp"

                    result = await session.execute(text(query), params)
                    rows = result.fetchall()

                    if not rows:
                        return pd.DataFrame()

                    # Преобразование в DataFrame
                    data = []
                    for row in rows:
                        data.append(
                            {
                                "timestamp": row.timestamp,
                                "open": float(row.open),
                                "high": float(row.high),
                                "low": float(row.low),
                                "close": float(row.close),
                                "volume": float(row.volume),
                            }
                        )

                    df = pd.DataFrame(data)
                    df.set_index("timestamp", inplace=True)

                    logger.info(
                        f"Retrieved {len(df)} market data records for {symbol} {timeframe}"
                    )
                    return df

            except Exception as e:
                logger.error(f"Failed to get market data: {e}")
                return pd.DataFrame()

    async def save_metrics(self, metrics: dict[str, Any]) -> bool:
        """Сохранение метрик в базу данных"""
        with create_log_context("database_client", "save_metrics"):
            try:
                async with self.session_factory() as session:
                    timestamp = datetime.now()

                    for metric_name, metric_value in metrics.items():
                        await session.execute(
                            text(
                                """
                            INSERT INTO mtf_metrics
                            (metric_name, metric_value, metric_type, timestamp, metadata)
                            VALUES (:metric_name, :metric_value, :metric_type, :timestamp, :metadata)
                        """
                            ),
                            {
                                "metric_name": metric_name,
                                "metric_value": float(metric_value),
                                "metric_type": "gauge",
                                "timestamp": timestamp,
                                "metadata": {},
                            },
                        )

                    await session.commit()
                    logger.info(f"Metrics saved: {len(metrics)} metrics")
                    return True

            except Exception as e:
                logger.error(f"Failed to save metrics: {e}")
                return False

    async def health_check(self) -> dict[str, Any]:
        """Проверка здоровья базы данных"""
        try:
            async with self.session_factory() as session:
                # Простой запрос для проверки подключения
                result = await session.execute(text("SELECT 1"))
                result.fetchone()

                return {
                    "status": "healthy",
                    "database_accessible": True,
                    "connection_pool_size": self.pool_size,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "database_accessible": False,
            }
