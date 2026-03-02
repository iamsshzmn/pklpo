"""Провайдер для загрузки индикаторов из БД."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd
from sqlalchemy import text

from ..logging_config import get_combinations_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_combinations_logger("provider")


class PostgresIndicatorProvider:
    """PostgreSQL реализация провайдера индикаторов."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def load_indicators(
        self,
        symbol: str,
        timeframe: str,
        start: int | None = None,  # timestamp_ms
        end: int | None = None,  # timestamp_ms
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Загрузить индикаторы из БД.

        Args:
            symbol: Символ инструмента
            timeframe: Таймфрейм
            start: Начальный timestamp (ms)
            end: Конечный timestamp (ms)
            limit: Максимальное количество строк

        Returns:
            DataFrame с колонками timestamp и индикаторами
        """
        # Строим WHERE условия
        conditions = ["symbol = :symbol", "timeframe = :timeframe"]
        params: dict[str, Any] = {"symbol": symbol, "timeframe": timeframe}

        if start is not None:
            conditions.append("timestamp >= :start")
            params["start"] = start

        if end is not None:
            conditions.append("timestamp <= :end")
            params["end"] = end

        where_clause = " AND ".join(conditions)

        # Загружаем список колонок из БД (исключаем служебные)
        cols_query = text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'indicators'
            AND table_schema = 'public'
            AND column_name NOT IN ('symbol', 'timeframe', 'calculated_at',
                                     'run_id', 'params_hash', 'data_quality_status',
                                     'nan_count', 'valid_rate', 'schema_version',
                                     'algo_version', 'created_at', 'updated_at')
            ORDER BY ordinal_position
        """
        )

        cols_result = await self.session.execute(cols_query)
        available_cols = [row[0] for row in cols_result.all()]

        if not available_cols:
            logger.warning(f"No indicator columns found for {symbol}/{timeframe}")
            return pd.DataFrame()

        # Формируем SELECT с явным указанием колонок
        select_cols = ["timestamp", *available_cols]
        select_clause = ", ".join(select_cols)

        # Строим запрос
        query_str = f"""
            SELECT {select_clause}
            FROM indicators
            WHERE {where_clause}
            ORDER BY timestamp ASC
        """

        if limit is not None:
            query_str += f" LIMIT {limit}"

        query = text(query_str)

        try:
            result = await self.session.execute(query, params)
            rows = result.fetchall()

            if not rows:
                logger.info(f"No indicators found for {symbol}/{timeframe}")
                return pd.DataFrame()

            # Преобразуем в DataFrame
            data = []
            for row in rows:
                row_dict = dict(row._mapping)
                data.append(row_dict)

            df = pd.DataFrame(data)

            # Убеждаемся, что timestamp есть
            if "timestamp" not in df.columns:
                logger.error("timestamp column not found in result")
                return pd.DataFrame()

            logger.info(
                f"Loaded {len(df)} indicator rows for {symbol}/{timeframe}, "
                f"columns: {len(df.columns)}"
            )
            return df

        except Exception as e:
            logger.error(f"Failed to load indicators: {e}")
            return pd.DataFrame()
