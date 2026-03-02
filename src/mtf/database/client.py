"""
MTF Database Client

Клиент для работы с базой данных MTF системы.
"""

import json
from datetime import datetime
from typing import Any

import asyncpg
import pandas as pd

from ..logging_config import get_main_logger
from .models import (
    AccelerationType,
    ConfidenceLevel,
    ConsensusType,
    MTFAggregatedResult,
    MTFConsensusRecord,
    MTFContextRecord,
    MTFIntegrationRecord,
    MTFPipelineRecord,
    MTFQueryFilters,
    MTFTriggersRecord,
    ProcessingStatus,
    RegimeType,
)

logger = get_main_logger()


class MTFDatabaseClient:
    """Клиент для работы с базой данных MTF системы"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: asyncpg.Pool | None = None
        self.logger = logger

    async def initialize(self):
        """Инициализация пула соединений"""
        try:
            self.pool = await asyncpg.create_pool(
                self.connection_string, min_size=2, max_size=10, command_timeout=30
            )
            self.logger.info("MTF Database client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize MTF database client: {e}")
            raise

    async def close(self):
        """Закрытие пула соединений"""
        if self.pool:
            await self.pool.close()
            self.logger.info("MTF Database client closed")

    async def _execute_query(self, query: str, *args) -> list[dict[str, Any]]:
        """Выполнение запроса к базе данных"""
        if not self.pool:
            raise RuntimeError("Database client not initialized")

        async with self.pool.acquire() as conn:
            try:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows]
            except Exception as e:
                self.logger.error(f"Database query failed: {e}")
                raise

    async def _execute_insert(self, query: str, *args) -> int:
        """Выполнение INSERT запроса"""
        if not self.pool:
            raise RuntimeError("Database client not initialized")

        async with self.pool.acquire() as conn:
            try:
                return await conn.fetchval(query, *args)
            except Exception as e:
                self.logger.error(f"Database insert failed: {e}")
                raise

    # Context модуль

    async def save_context_result(self, record: MTFContextRecord) -> int:
        """Сохранение результата Context модуля"""
        query = """
        INSERT INTO mtf_context (
            symbol, timeframe, timestamp, dominant_regime, regime_confidence,
            overall_score, timeframe_results, valid, errors, processing_time_ms
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id
        """

        record_id = await self._execute_insert(
            query,
            record.symbol,
            record.timeframe,
            record.timestamp,
            record.dominant_regime.value,
            record.regime_confidence,
            record.overall_score,
            json.dumps(record.timeframe_results),
            record.valid,
            record.errors,
            record.processing_time_ms,
        )

        self.logger.debug(f"Context result saved with ID: {record_id}")
        return record_id

    async def get_context_results(
        self, filters: MTFQueryFilters
    ) -> list[MTFContextRecord]:
        """Получение результатов Context модуля"""
        query = """
        SELECT * FROM mtf_context
        WHERE 1=1
        """
        params = []
        param_count = 0

        if filters.symbols:
            param_count += 1
            query += f" AND symbol = ANY(${param_count})"
            params.append(filters.symbols)

        if filters.timeframes:
            param_count += 1
            query += f" AND timeframe = ANY(${param_count})"
            params.append(filters.timeframes)

        if filters.start_time:
            param_count += 1
            query += f" AND timestamp >= ${param_count}"
            params.append(filters.start_time)

        if filters.end_time:
            param_count += 1
            query += f" AND timestamp <= ${param_count}"
            params.append(filters.end_time)

        if filters.regimes:
            param_count += 1
            query += f" AND dominant_regime = ANY(${param_count})"
            params.append([r.value for r in filters.regimes])

        if filters.valid_only:
            query += " AND valid = TRUE"

        query += " ORDER BY timestamp DESC"

        if filters.limit:
            query += f" LIMIT {filters.limit}"

        if filters.offset:
            query += f" OFFSET {filters.offset}"

        rows = await self._execute_query(query, *params)

        results = []
        for row in rows:
            record = MTFContextRecord(
                id=row["id"],
                symbol=row["symbol"],
                timeframe=row["timeframe"],
                timestamp=row["timestamp"],
                dominant_regime=RegimeType(row["dominant_regime"]),
                regime_confidence=float(row["regime_confidence"]),
                overall_score=float(row["overall_score"]),
                timeframe_results=row["timeframe_results"],
                valid=row["valid"],
                errors=row["errors"] or [],
                processing_time_ms=row["processing_time_ms"],
                created_at=row["created_at"],
            )
            results.append(record)

        return results

    # Triggers модуль

    async def save_triggers_result(self, record: MTFTriggersRecord) -> int:
        """Сохранение результата Triggers модуля"""
        query = """
        INSERT INTO mtf_triggers (
            symbol, timeframe, timestamp, overall_p_up, overall_p_down,
            acceleration_type, acceleration_strength, micro_ok, micro_filter_score,
            timeframe_results, valid, errors, processing_time_ms
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        RETURNING id
        """

        record_id = await self._execute_insert(
            query,
            record.symbol,
            record.timeframe,
            record.timestamp,
            record.overall_p_up,
            record.overall_p_down,
            record.acceleration_type.value,
            record.acceleration_strength,
            record.micro_ok,
            record.micro_filter_score,
            json.dumps(record.timeframe_results),
            record.valid,
            record.errors,
            record.processing_time_ms,
        )

        self.logger.debug(f"Triggers result saved with ID: {record_id}")
        return record_id

    async def get_triggers_results(
        self, filters: MTFQueryFilters
    ) -> list[MTFTriggersRecord]:
        """Получение результатов Triggers модуля"""
        query = """
        SELECT * FROM mtf_triggers
        WHERE 1=1
        """
        params = []
        param_count = 0

        if filters.symbols:
            param_count += 1
            query += f" AND symbol = ANY(${param_count})"
            params.append(filters.symbols)

        if filters.timeframes:
            param_count += 1
            query += f" AND timeframe = ANY(${param_count})"
            params.append(filters.timeframes)

        if filters.start_time:
            param_count += 1
            query += f" AND timestamp >= ${param_count}"
            params.append(filters.start_time)

        if filters.end_time:
            param_count += 1
            query += f" AND timestamp <= ${param_count}"
            params.append(filters.end_time)

        if filters.acceleration_types:
            param_count += 1
            query += f" AND acceleration_type = ANY(${param_count})"
            params.append([a.value for a in filters.acceleration_types])

        if filters.valid_only:
            query += " AND valid = TRUE"

        query += " ORDER BY timestamp DESC"

        if filters.limit:
            query += f" LIMIT {filters.limit}"

        if filters.offset:
            query += f" OFFSET {filters.offset}"

        rows = await self._execute_query(query, *params)

        results = []
        for row in rows:
            record = MTFTriggersRecord(
                id=row["id"],
                symbol=row["symbol"],
                timeframe=row["timeframe"],
                timestamp=row["timestamp"],
                overall_p_up=float(row["overall_p_up"]),
                overall_p_down=float(row["overall_p_down"]),
                acceleration_type=AccelerationType(row["acceleration_type"]),
                acceleration_strength=float(row["acceleration_strength"]),
                micro_ok=row["micro_ok"],
                micro_filter_score=float(row["micro_filter_score"]),
                timeframe_results=row["timeframe_results"],
                valid=row["valid"],
                errors=row["errors"] or [],
                processing_time_ms=row["processing_time_ms"],
                created_at=row["created_at"],
            )
            results.append(record)

        return results

    # Consensus модуль

    async def save_consensus_result(self, record: MTFConsensusRecord) -> int:
        """Сохранение результата Consensus модуля"""
        query = """
        INSERT INTO mtf_consensus (
            symbol, timeframes, timestamp, consensus_type, confidence_level,
            consensus_score, context_weight, triggers_weight, coverage_ratio,
            disagreement_ratio, veto_applied, veto_reasons, timeframe_consensus,
            evidence_summary, valid, errors, processing_time_ms
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        RETURNING id
        """

        record_id = await self._execute_insert(
            query,
            record.symbol,
            record.timeframes,
            record.timestamp,
            record.consensus_type.value,
            record.confidence_level.value,
            record.consensus_score,
            record.context_weight,
            record.triggers_weight,
            record.coverage_ratio,
            record.disagreement_ratio,
            record.veto_applied,
            record.veto_reasons,
            json.dumps(record.timeframe_consensus),
            json.dumps(record.evidence_summary),
            record.valid,
            record.errors,
            record.processing_time_ms,
        )

        self.logger.debug(f"Consensus result saved with ID: {record_id}")
        return record_id

    async def get_consensus_results(
        self, filters: MTFQueryFilters
    ) -> list[MTFConsensusRecord]:
        """Получение результатов Consensus модуля"""
        query = """
        SELECT * FROM mtf_consensus
        WHERE 1=1
        """
        params = []
        param_count = 0

        if filters.symbols:
            param_count += 1
            query += f" AND symbol = ANY(${param_count})"
            params.append(filters.symbols)

        if filters.timeframes:
            param_count += 1
            query += f" AND timeframes && ${param_count}"
            params.append(filters.timeframes)

        if filters.start_time:
            param_count += 1
            query += f" AND timestamp >= ${param_count}"
            params.append(filters.start_time)

        if filters.end_time:
            param_count += 1
            query += f" AND timestamp <= ${param_count}"
            params.append(filters.end_time)

        if filters.consensus_types:
            param_count += 1
            query += f" AND consensus_type = ANY(${param_count})"
            params.append([c.value for c in filters.consensus_types])

        if filters.confidence_levels:
            param_count += 1
            query += f" AND confidence_level = ANY(${param_count})"
            params.append([c.value for c in filters.confidence_levels])

        if filters.valid_only:
            query += " AND valid = TRUE"

        query += " ORDER BY timestamp DESC"

        if filters.limit:
            query += f" LIMIT {filters.limit}"

        if filters.offset:
            query += f" OFFSET {filters.offset}"

        rows = await self._execute_query(query, *params)

        results = []
        for row in rows:
            record = MTFConsensusRecord(
                id=row["id"],
                symbol=row["symbol"],
                timeframes=row["timeframes"],
                timestamp=row["timestamp"],
                consensus_type=ConsensusType(row["consensus_type"]),
                confidence_level=ConfidenceLevel(row["confidence_level"]),
                consensus_score=float(row["consensus_score"]),
                context_weight=float(row["context_weight"]),
                triggers_weight=float(row["triggers_weight"]),
                coverage_ratio=float(row["coverage_ratio"]),
                disagreement_ratio=float(row["disagreement_ratio"]),
                veto_applied=row["veto_applied"],
                veto_reasons=row["veto_reasons"] or [],
                timeframe_consensus=row["timeframe_consensus"],
                evidence_summary=row["evidence_summary"],
                valid=row["valid"],
                errors=row["errors"] or [],
                processing_time_ms=row["processing_time_ms"],
                created_at=row["created_at"],
            )
            results.append(record)

        return results

    # Pipeline модуль

    async def save_pipeline_result(self, record: MTFPipelineRecord) -> int:
        """Сохранение результата Pipeline модуля"""
        query = """
        INSERT INTO mtf_pipeline (
            symbol, timeframes, timestamp, status, processing_stage,
            context_id, triggers_id, consensus_id, total_processing_time_ms,
            errors, warnings
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING id
        """

        record_id = await self._execute_insert(
            query,
            record.symbol,
            record.timeframes,
            record.timestamp,
            record.status.value,
            record.processing_stage.value,
            record.context_id,
            record.triggers_id,
            record.consensus_id,
            record.total_processing_time_ms,
            record.errors,
            record.warnings,
        )

        self.logger.debug(f"Pipeline result saved with ID: {record_id}")
        return record_id

    # Integration модуль

    async def save_integration_result(self, record: MTFIntegrationRecord) -> int:
        """Сохранение результата Integration модуля"""
        query = """
        INSERT INTO mtf_integration (
            symbol, timeframes, timestamp, status, okx_success,
            database_success, notifications_sent, processing_time_ms,
            errors, warnings
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id
        """

        record_id = await self._execute_insert(
            query,
            record.symbol,
            record.timeframes,
            record.timestamp,
            record.status.value,
            record.okx_success,
            record.database_success,
            record.notifications_sent,
            record.processing_time_ms,
            record.errors,
            record.warnings,
        )

        self.logger.debug(f"Integration result saved with ID: {record_id}")
        return record_id

    # Агрегированные запросы

    async def get_latest_results(
        self, symbols: list[str] | None = None
    ) -> list[MTFAggregatedResult]:
        """Получение последних результатов MTF анализа"""
        query = """
        SELECT * FROM mtf_latest_results
        WHERE 1=1
        """
        params = []

        if symbols:
            query += " AND symbol = ANY($1)"
            params.append(symbols)

        query += " ORDER BY timestamp DESC"

        rows = await self._execute_query(query, *params)

        results = []
        for row in rows:
            result = MTFAggregatedResult(
                symbol=row["symbol"],
                timeframes=row["timeframes"],
                timestamp=row["timestamp"],
                dominant_regime=RegimeType(row["dominant_regime"]),
                regime_confidence=float(row["regime_confidence"]),
                context_score=float(row["context_score"]),
                overall_p_up=float(row["overall_p_up"]),
                overall_p_down=float(row["overall_p_down"]),
                acceleration_type=AccelerationType(row["acceleration_type"]),
                micro_ok=row["micro_ok"],
                consensus_type=ConsensusType(row["consensus_type"]),
                confidence_level=ConfidenceLevel(row["confidence_level"]),
                consensus_score=float(row["consensus_score"]),
                veto_applied=row["veto_applied"],
                integration_status=ProcessingStatus(row["integration_status"]),
                total_processing_time_ms=row["total_processing_time_ms"],
                created_at=row["created_at"],
            )
            results.append(result)

        return results

    async def get_statistics(self, hours: int = 24) -> list[dict[str, Any]]:
        """Получение статистики MTF системы"""
        query = """
        SELECT * FROM mtf_statistics
        WHERE hour >= NOW() - INTERVAL '%s hours'
        ORDER BY hour DESC
        """

        return await self._execute_query(query, hours)

    # Получение данных для обработки

    async def get_features_data(
        self, symbol: str, timeframes: list[str], lookback_hours: int = 24
    ) -> dict[str, pd.DataFrame]:
        """Получение данных features для MTF обработки"""
        # Здесь нужно интегрироваться с существующей системой features
        # Пока возвращаем пустой словарь - будет доработано
        self.logger.warning(
            "get_features_data not implemented yet - needs integration with features module"
        )
        return {}

    async def get_latest_features_timestamp(
        self, symbol: str, timeframe: str
    ) -> datetime | None:
        """Получение времени последнего обновления features данных"""
        # Здесь нужно интегрироваться с существующей системой features
        self.logger.warning(
            "get_latest_features_timestamp not implemented yet - needs integration with features module"
        )
        return None
