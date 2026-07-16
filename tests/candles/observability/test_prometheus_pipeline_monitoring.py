from __future__ import annotations

from typing import Any

from prometheus_client.exposition import generate_latest

from src.candles.observability import prometheus


def test_push_pipeline_monitoring_metrics_emits_readonly_snapshot_series(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_push_registry(registry: Any, job_name: str) -> bool:
        captured["job_name"] = job_name
        captured["text"] = generate_latest(registry).decode("utf-8")
        return True

    monkeypatch.setattr(prometheus, "_push_registry", _fake_push_registry)

    ok = prometheus.push_pipeline_monitoring_metrics(
        {
            "candle_lag_seconds": {"1H": 120.0},
            "recalc_queue": {"queued": 3, "blocked": 1},
            "bootstrap_state": {"completed": 7},
            "eligibility_state": [{"timeframe": "1H", "state": "eligible", "count": 5}],
            "alerts": {"critical": 2},
        }
    )

    assert ok is True
    assert captured["job_name"] == "pipeline_monitoring"
    text = captured["text"]
    assert 'pklpo_pipeline_candle_lag_seconds{timeframe="1H"} 120.0' in text
    assert 'pklpo_pipeline_recalc_queue_rows{status="queued"} 3.0' in text
    assert 'pklpo_pipeline_recalc_queue_rows{status="blocked"} 1.0' in text
    assert 'pklpo_pipeline_bootstrap_state_rows{status="completed"} 7.0' in text
    assert (
        'pklpo_pipeline_eligibility_state_rows{state="eligible",timeframe="1H"} 5.0'
        in text
    )
    assert 'pklpo_pipeline_alerts{severity="critical"} 2.0' in text
