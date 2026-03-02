"""
Асинхронный клиент для работы с БД модуля Risk
"""

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    # Защищенное преобразование для float/int/str
    try:
        return Decimal(str(value))
    except Exception as err:
        raise ValueError(f"Cannot convert {value!r} to Decimal") from err


def _json_default(o: Any):
    if isinstance(o, datetime | date):
        return o.isoformat()
    if isinstance(o, Decimal):
        return str(o)
    return str(o)


def _to_jsonb_param(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, default=_json_default)


class RiskDatabaseClient:
    """Минимальный клиент для записи и чтения risk-данных"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        self._pool = await asyncpg.create_pool(
            self.database_url, min_size=1, max_size=5
        )
        logger.info("Risk DB client initialized")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    # Guards
    async def upsert_guard(
        self, name: str, type_: str, status: str, config: dict[str, Any]
    ) -> UUID:
        sql = """
            INSERT INTO risk.guards (name, type, status, config)
            VALUES ($1, $2, $3, $4::jsonb)
            ON CONFLICT (name, type)
            DO UPDATE SET status = EXCLUDED.status, config = EXCLUDED.config, updated_at = NOW()
            RETURNING id
        """
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                sql, name, type_, status, _to_jsonb_param(config)
            )

    async def add_guard_state(
        self,
        guard_id: UUID,
        state: str,
        trigger_count: int = 0,
        context: dict[str, Any] | None = None,
    ) -> None:
        sql = """
            INSERT INTO risk.guard_state_history (guard_id, state, trigger_count, context)
            VALUES ($1, $2, $3, $4::jsonb)
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                sql, guard_id, state, trigger_count, _to_jsonb_param(context)
            )

    # Alerts
    async def add_alert(
        self,
        guard_id: UUID | None,
        alert_type: str,
        severity: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> UUID:
        sql = """
            INSERT INTO risk.alerts (guard_id, alert_type, severity, message, context)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING id
        """
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                sql, guard_id, alert_type, severity, message, _to_jsonb_param(context)
            )

    # Metrics
    async def add_metric(
        self,
        guard_id: UUID | None,
        metric_name: str,
        metric_value: Decimal,
        labels: dict[str, Any] | None = None,
    ) -> None:
        sql = """
            INSERT INTO risk.metrics (guard_id, ts, metric_name, metric_value, labels)
            VALUES ($1, NOW(), $2, $3, $4::jsonb)
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                sql,
                guard_id,
                metric_name,
                _to_decimal(metric_value),
                _to_jsonb_param(labels),
            )

    # Limits
    async def upsert_limit(
        self,
        name: str,
        type_: str,
        value: Decimal,
        time_window: str | None,
        enabled: bool,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        sql = """
            INSERT INTO risk.limits (name, type, value, time_window, enabled, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            ON CONFLICT (name)
            DO UPDATE SET type = EXCLUDED.type, value = EXCLUDED.value, time_window = EXCLUDED.time_window,
                          enabled = EXCLUDED.enabled, metadata = EXCLUDED.metadata, updated_at = NOW()
            RETURNING id
        """
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                sql,
                name,
                type_,
                _to_decimal(value),
                time_window,
                enabled,
                _to_jsonb_param(metadata),
            )

    # Violations
    async def add_violation(
        self,
        source: str,
        code: str,
        message: str,
        severity: str,
        context: dict[str, Any] | None = None,
    ) -> UUID:
        sql = """
            INSERT INTO risk.violations (source, code, message, severity, context)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING id
        """
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                sql, source, code, message, severity, _to_jsonb_param(context)
            )

    # Sizing logs
    async def add_sizing_log(
        self,
        symbol_id: int | None,
        entry: Decimal,
        stop: Decimal,
        take: Decimal | None,
        balance: Decimal,
        risk_pct: Decimal,
        size: Decimal,
        notional: Decimal,
        fees: Decimal = Decimal("0"),
        slippage: Decimal = Decimal("0"),
        lot_size: Decimal = Decimal("0"),
        config: dict[str, Any] | None = None,
    ) -> UUID:
        sql = """
            INSERT INTO risk.sizing_logs (symbol_id, entry, stop, take, balance, risk_pct, size, notional, fees, slippage, lot_size, config)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb)
            RETURNING id
        """
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                sql,
                symbol_id,
                _to_decimal(entry),
                _to_decimal(stop),
                _to_decimal(take),
                _to_decimal(balance),
                _to_decimal(risk_pct),
                _to_decimal(size),
                _to_decimal(notional),
                _to_decimal(fees),
                _to_decimal(slippage),
                _to_decimal(lot_size),
                _to_jsonb_param(config),
            )
