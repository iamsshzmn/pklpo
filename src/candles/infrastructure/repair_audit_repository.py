from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from src.utils.session_utils import get_db_session


class SwapRepairAuditRepository:
    async def insert_records(self, records: list[dict[str, Any]]) -> int:
        if not records:
            return 0

        stmt = text(
            """
            INSERT INTO ops.swap_repair_audit (
                dag_id,
                dag_run_id,
                logical_date,
                symbol,
                timeframe,
                mode,
                strategy,
                auto_apply_window,
                auto_apply_incomplete,
                verified,
                gap_tasks,
                requested_bars,
                remaining_gap_tasks,
                remaining_requested_bars,
                rows_written,
                fetch_calls,
                window_start_ts_ms,
                window_end_ts_ms,
                verification_method,
                preview_payload,
                summary_payload,
                requested_conf
            ) VALUES (
                :dag_id,
                :dag_run_id,
                :logical_date,
                :symbol,
                :timeframe,
                :mode,
                :strategy,
                :auto_apply_window,
                :auto_apply_incomplete,
                :verified,
                :gap_tasks,
                :requested_bars,
                :remaining_gap_tasks,
                :remaining_requested_bars,
                :rows_written,
                :fetch_calls,
                :window_start_ts_ms,
                :window_end_ts_ms,
                :verification_method,
                CAST(:preview_payload AS JSONB),
                CAST(:summary_payload AS JSONB),
                CAST(:requested_conf AS JSONB)
            )
            """
        )

        params = [
            {
                **record,
                "preview_payload": json.dumps(record.get("preview_payload") or {}),
                "summary_payload": json.dumps(record.get("summary_payload") or {}),
                "requested_conf": json.dumps(record.get("requested_conf") or {}),
            }
            for record in records
        ]

        async with get_db_session() as session:
            result = await session.execute(stmt, params)
            return int(result.rowcount if result.rowcount and result.rowcount > 0 else len(params))
