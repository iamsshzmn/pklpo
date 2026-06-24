"""Repository for ops.pipeline_recovery_decisions.

Persistence and cooldown query for the pipeline recovery controller.
Layer: infrastructure (asyncpg / SQLAlchemy text queries only).
No domain logic here.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

_INSERT_SQL = text(
    """
    INSERT INTO ops.pipeline_recovery_decisions (
        controller_dag_id,
        controller_dag_run_id,
        logical_date,
        decision_status,
        action_kind,
        target_dag_id,
        target_run_id,
        reason,
        symbol,
        timeframe,
        priority,
        cooldown_until,
        precheck_payload,
        trigger_conf,
        safety_payload,
        error
    ) VALUES (
        :controller_dag_id,
        :controller_dag_run_id,
        :logical_date,
        :decision_status,
        :action_kind,
        :target_dag_id,
        :target_run_id,
        :reason,
        :symbol,
        :timeframe,
        :priority,
        :cooldown_until,
        CAST(:precheck_payload AS jsonb),
        CAST(:trigger_conf AS jsonb),
        CAST(:safety_payload AS jsonb),
        :error
    )
    RETURNING id, created_at
    """
)

_COOLDOWN_SQL = text(
    """
    SELECT id, created_at, decision_status, action_kind, target_dag_id,
           symbol, timeframe, cooldown_until
    FROM ops.pipeline_recovery_decisions
    WHERE action_kind     = :action_kind
      AND target_dag_id   = :target_dag_id
      AND symbol          = :symbol
      AND timeframe       = :timeframe
      AND created_at     >= :since
    ORDER BY created_at DESC
    LIMIT :limit
    """
)

_RECENT_SQL = text(
    """
    SELECT id, created_at, decision_status, action_kind, target_dag_id,
           symbol, timeframe, reason, cooldown_until
    FROM ops.pipeline_recovery_decisions
    WHERE controller_dag_id = :controller_dag_id
      AND created_at >= :since
    ORDER BY created_at DESC
    LIMIT :limit
    """
)


class RecoveryDecisionRepository:
    """Persist and query ``ops.pipeline_recovery_decisions``."""

    async def insert_decision(
        self,
        *,
        controller_dag_id: str,
        controller_dag_run_id: str | None,
        logical_date: datetime | None,
        decision_status: str,
        action_kind: str,
        target_dag_id: str | None,
        target_run_id: str | None,
        reason: str,
        symbol: str | None,
        timeframe: str | None,
        priority: int = 0,
        cooldown_until: datetime | None,
        precheck_payload: dict[str, Any] | None = None,
        trigger_conf: dict[str, Any] | None = None,
        safety_payload: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Insert a new decision row and return ``{"id": ..., "created_at": ...}``."""
        import json

        params: dict[str, Any] = {
            "controller_dag_id": controller_dag_id,
            "controller_dag_run_id": controller_dag_run_id,
            "logical_date": logical_date,
            "decision_status": decision_status,
            "action_kind": action_kind,
            "target_dag_id": target_dag_id,
            "target_run_id": target_run_id,
            "reason": reason,
            "symbol": symbol,
            "timeframe": timeframe,
            "priority": priority,
            "cooldown_until": cooldown_until,
            "precheck_payload": json.dumps(precheck_payload or {}),
            "trigger_conf": json.dumps(trigger_conf or {}),
            "safety_payload": json.dumps(safety_payload or {}),
            "error": error,
        }
        async with get_db_session() as session:
            result = await session.execute(_INSERT_SQL, params)
            row = result.fetchone()
            await session.commit()

        decision_id = int(row[0])
        created_at: datetime = row[1]
        logger.info(
            "recovery_decision inserted id=%d status=%s action=%s reason=%s symbol=%s timeframe=%s",
            decision_id,
            decision_status,
            action_kind,
            reason,
            symbol,
            timeframe,
        )
        return {"id": decision_id, "created_at": created_at}

    async def get_cooldown_rows(
        self,
        *,
        action_kind: str,
        target_dag_id: str,
        symbol: str,
        timeframe: str,
        cooldown_minutes: int,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return recent decisions matching the cooldown key.

        Cooldown key: ``action_kind + target_dag_id + symbol + timeframe``.
        Returns rows where ``created_at >= now() - cooldown_minutes``.
        """
        since = datetime.now(UTC) - timedelta(minutes=cooldown_minutes)
        params: dict[str, Any] = {
            "action_kind": action_kind,
            "target_dag_id": target_dag_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "since": since,
            "limit": limit,
        }
        async with get_db_session() as session:
            result = await session.execute(_COOLDOWN_SQL, params)
            rows = result.fetchall()

        return [
            {
                "id": int(r[0]),
                "created_at": r[1],
                "decision_status": r[2],
                "action_kind": r[3],
                "target_dag_id": r[4],
                "symbol": r[5],
                "timeframe": r[6],
                "cooldown_until": r[7],
            }
            for r in rows
        ]

    async def get_recent_decisions(
        self,
        *,
        controller_dag_id: str,
        since_minutes: int = 60,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return recent decisions for a given controller DAG (for audit/logging)."""
        since = datetime.now(UTC) - timedelta(minutes=since_minutes)
        async with get_db_session() as session:
            result = await session.execute(
                _RECENT_SQL,
                {
                    "controller_dag_id": controller_dag_id,
                    "since": since,
                    "limit": limit,
                },
            )
            rows = result.fetchall()

        return [
            {
                "id": int(r[0]),
                "created_at": r[1],
                "decision_status": r[2],
                "action_kind": r[3],
                "target_dag_id": r[4],
                "symbol": r[5],
                "timeframe": r[6],
                "reason": r[7],
                "cooldown_until": r[8],
            }
            for r in rows
        ]
