from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

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
        window = summary.get("window") or {}
        symbol = str(summary.get("symbol", validated_conf.get("symbol", "")))
        timeframe = str(summary.get("timeframe", ""))
        records.append(
            {
                "dag_id": dag_id,
                "dag_run_id": dag_run_id,
                "logical_date": logical_date,
                "symbol": symbol,
                "timeframe": timeframe,
                "mode": str(summary.get("mode", validated_conf.get("mode", ""))),
                "strategy": str(summary.get("strategy", validated_conf.get("repair_strategy", ""))),
                "auto_apply_window": bool(validated_conf.get("auto_apply_window", False)),
                "auto_apply_incomplete": bool(summary.get("auto_apply_incomplete", False)),
                "verified": bool(summary.get("verified", False)),
                "gap_tasks": int(summary.get("gap_tasks", 0)),
                "requested_bars": int(summary.get("requested_bars", 0)),
                "remaining_gap_tasks": int(summary.get("remaining_gap_tasks", 0)),
                "remaining_requested_bars": int(summary.get("remaining_requested_bars", 0)),
                "rows_written": int(summary.get("rows_written", 0)),
                "fetch_calls": int(summary.get("fetch_calls", 0)),
                "window_start_ts_ms": int(window.get("start_ts_ms", 0)),
                "window_end_ts_ms": int(window.get("end_ts_ms", 0)),
                "verification_method": summary.get("verification_method"),
                "preview_payload": preview_by_symbol_timeframe.get((symbol, timeframe)) or {},
                "summary_payload": summary,
                "requested_conf": validated_conf,
                "outcome": summary.get("outcome"),
                "received_bars": summary.get("received_bars"),
                "remaining_missing_before": summary.get("remaining_missing_before"),
                "remaining_missing_after": summary.get("remaining_missing_after"),
                "progress": summary.get("progress"),
                "api_fill_ratio": summary.get("api_fill_ratio"),
                "write_success_ratio": summary.get("write_success_ratio"),
            }
        )

    repository = SwapRepairAuditRepository()
    return await repository.insert_records(records)
