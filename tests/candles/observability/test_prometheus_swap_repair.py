from __future__ import annotations

from typing import Any

from prometheus_client.exposition import generate_latest

from src.candles.observability import prometheus


def _capture_registry(monkeypatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def _fake_push_registry(registry: Any, job_name: str) -> bool:
        captured["registry"] = registry
        captured["job_name"] = job_name
        captured["text"] = generate_latest(registry).decode("utf-8")
        return True

    monkeypatch.setattr(prometheus, "_push_registry", _fake_push_registry)
    return captured


def test_push_swap_repair_metrics_emits_new_semantic_gauges(monkeypatch) -> None:
    captured = _capture_registry(monkeypatch)

    ok = prometheus.push_swap_repair_metrics(
        [
            {
                "symbol": "BTC-USDT-SWAP",
                "timeframe": "1m",
                "mode": "apply",
                "strategy": "gap-repair",
                "gap_tasks": 1,
                "requested_bars": 4,
                "remaining_gap_tasks": 0,
                "remaining_requested_bars": 0,
                "rows_written": 3,
                "verified": True,
                "auto_apply_incomplete": False,
                "received_bars": 3,
                "progress": 3,
                "api_fill_ratio": 0.75,
                "write_success_ratio": 1.0,
                "remaining_missing_before": 3,
                "remaining_missing_after": 0,
                "outcome": "partial",
                "blocked": True,
                "blocked_reason": "empty-chunk",
                "blocked_cause": "api_returned_empty",
            }
        ]
    )

    assert ok is True
    text = captured["text"]
    for metric_name in (
        "pklpo_swap_repair_received_bars",
        "pklpo_swap_repair_progress",
        "pklpo_swap_repair_api_fill_ratio",
        "pklpo_swap_repair_write_success_ratio",
        "pklpo_swap_repair_remaining_missing_before",
        "pklpo_swap_repair_remaining_missing_after",
        "pklpo_swap_repair_outcome_total",
        "pklpo_swap_repair_blocked",
        "pklpo_swap_repair_blocked_reason_total",
        "pklpo_swap_repair_blocked_cause_total",
    ):
        assert metric_name in text, f"missing {metric_name} in pushed metrics"

    assert 'outcome="partial"' in text
    assert 'blocked_reason="empty-chunk"' in text
    assert 'blocked_cause="api_returned_empty"' in text
    assert 'pklpo_swap_repair_api_fill_ratio{' in text


def test_push_swap_repair_metrics_without_outcome_skips_outcome_counter(monkeypatch) -> None:
    captured = _capture_registry(monkeypatch)

    ok = prometheus.push_swap_repair_metrics(
        [
            {
                "symbol": "BTC-USDT-SWAP",
                "timeframe": "1m",
                "mode": "apply",
                "strategy": "gap-repair",
                "gap_tasks": 1,
                "requested_bars": 4,
                "remaining_gap_tasks": 0,
                "remaining_requested_bars": 0,
                "rows_written": 4,
                "verified": True,
            }
        ]
    )

    assert ok is True
    text = captured["text"]
    assert "pklpo_swap_repair_received_bars" in text
    assert "outcome=" not in text
