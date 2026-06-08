from __future__ import annotations

from typing import Any

from src.candles.observability import prometheus


def test_push_swap_repair_metrics_builds_registry_and_pushes(
    monkeypatch,
) -> None:
    pushed: dict[str, Any] = {}

    def _fake_push_registry(registry: Any, job_name: str) -> bool:
        pushed["registry"] = registry
        pushed["job_name"] = job_name
        return True

    monkeypatch.setattr(prometheus, "_push_registry", _fake_push_registry)

    result = prometheus.push_swap_repair_metrics(
        [
            {
                "symbol": "BTC-USDT-SWAP",
                "timeframe": "1m",
                "mode": "apply",
                "strategy": "gap-repair",
                "gap_tasks": 2,
                "requested_bars": 20,
                "remaining_gap_tasks": 1,
                "remaining_requested_bars": 10,
                "rows_written": 10,
                "verified": False,
                "auto_apply_incomplete": True,
            }
        ]
    )

    assert result is True
    assert pushed["job_name"] == "swap_repair_v1"
