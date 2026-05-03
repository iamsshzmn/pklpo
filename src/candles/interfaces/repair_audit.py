from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

from src.candles.application.repair.summary import RepairSummary
from src.candles.infrastructure.repair_audit_repository import SwapRepairAuditRepository


async def write_swap_repair_audit(
    *,
    validated_conf: dict[str, Any],
    preview_payloads: list[dict[str, Any]] | None,
    summary_payloads: list[dict[str, Any]],
    dag_id: str,
    dag_run_id: str | None,
    logical_date: datetime | None,
) -> int:
    preview_by_symbol_timeframe = {
        (str(payload.get("symbol", "")), str(payload.get("timeframe", ""))): payload
        for payload in (preview_payloads or [])
    }
    records: list[dict[str, Any]] = []
    for summary in summary_payloads:
        normalized_summary = RepairSummary.from_mapping(summary).to_dict()
        window = normalized_summary.get("window") or {}
        symbol = str(normalized_summary.get("symbol", validated_conf.get("symbol", "")))
        timeframe = str(normalized_summary.get("timeframe", ""))
        records.append(
            {
                "dag_id": dag_id,
                "dag_run_id": dag_run_id,
                "logical_date": logical_date,
                "symbol": symbol,
                "timeframe": timeframe,
                "mode": str(normalized_summary.get("mode", validated_conf.get("mode", ""))),
                "strategy": str(
                    normalized_summary.get("strategy", validated_conf.get("repair_strategy", ""))
                ),
                "auto_apply_window": bool(validated_conf.get("auto_apply_window", False)),
                "auto_apply_incomplete": bool(normalized_summary.get("auto_apply_incomplete", False)),
                "verified": bool(normalized_summary.get("verified", False)),
                "gap_tasks": int(normalized_summary.get("gap_tasks", 0)),
                "requested_bars": int(normalized_summary.get("requested_bars", 0)),
                "remaining_gap_tasks": int(normalized_summary.get("remaining_gap_tasks", 0)),
                "remaining_requested_bars": int(normalized_summary.get("remaining_requested_bars", 0)),
                "rows_written": int(normalized_summary.get("rows_written", 0)),
                "fetch_calls": int(normalized_summary.get("fetch_calls", 0)),
                "window_start_ts_ms": int(window.get("start_ts_ms", 0)),
                "window_end_ts_ms": int(window.get("end_ts_ms", 0)),
                "verification_method": normalized_summary.get("verification_method"),
                "preview_payload": preview_by_symbol_timeframe.get((symbol, timeframe)) or {},
                "summary_payload": normalized_summary,
                "requested_conf": validated_conf,
                "outcome": normalized_summary.get("outcome"),
                "received_bars": normalized_summary.get("received_bars"),
                "remaining_missing_before": normalized_summary.get("remaining_missing_before"),
                "remaining_missing_after": normalized_summary.get("remaining_missing_after"),
                "progress": normalized_summary.get("progress"),
                "api_fill_ratio": normalized_summary.get("api_fill_ratio"),
                "write_success_ratio": normalized_summary.get("write_success_ratio"),
            }
        )

    repository = SwapRepairAuditRepository()
    return await repository.insert_records(records)
