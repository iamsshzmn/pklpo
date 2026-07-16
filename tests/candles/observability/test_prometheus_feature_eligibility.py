from __future__ import annotations

from typing import Any

from prometheus_client.exposition import generate_latest

from src.candles.observability import prometheus


def test_push_feature_eligibility_metrics_emits_state_and_transition_series(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_push_registry(registry: Any, job_name: str) -> bool:
        captured["job_name"] = job_name
        captured["text"] = generate_latest(registry).decode("utf-8")
        return True

    monkeypatch.setattr(prometheus, "_push_registry", _fake_push_registry)

    ok = prometheus.push_feature_eligibility_metrics(
        {
            "state_counts": {("1H", "eligible"): 2, ("1H", "invalid_history"): 1},
            "eligible_counts": {"1H": 2},
            "transitions": [
                {
                    "from_state": "eligible",
                    "to_state": "invalid_history",
                    "timeframe": "1H",
                }
            ],
            "invalid_total": 1,
            "stale_seconds": 42.0,
            "warmup_remaining": {("BTC-USDT-SWAP", "1H"): 125},
        }
    )

    assert ok is True
    assert captured["job_name"] == "feature_eligibility"
    text = captured["text"]
    assert (
        'pklpo_feature_eligibility_symbols{state="eligible",timeframe="1H"} 2.0' in text
    )
    assert 'pklpo_feature_eligible_total{timeframe="1H"} 2.0' in text
    assert "pklpo_feature_eligibility_invalid_total 1.0" in text
    assert "pklpo_feature_eligibility_stale_seconds 42.0" in text
    assert (
        'pklpo_feature_eligibility_transitions_total{from_state="eligible",to_state="invalid_history"} 1.0'
        in text
    )
    assert 'pklpo_feature_eligibility_lost{timeframe="1H"} 1.0' in text
    assert (
        'pklpo_feature_warmup_bars_remaining{symbol="BTC-USDT-SWAP",timeframe="1H"} 125.0'
        in text
    )


def test_delete_pushgateway_job_deletes_configured_job(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def _fake_delete_from_gateway(url: str, *, job: str) -> None:
        captured["url"] = url
        captured["job"] = job

    monkeypatch.setattr(prometheus, "delete_from_gateway", _fake_delete_from_gateway)
    monkeypatch.setenv("OBSERVABILITY_PROMETHEUS_ENABLED", "true")
    monkeypatch.setenv("OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL", "http://gw:9091")

    ok = prometheus.delete_pushgateway_job("swap_repair_v1")

    assert ok is True
    assert captured == {"url": "http://gw:9091", "job": "swap_repair_v1"}


def test_delete_pushgateway_job_is_noop_without_gateway(monkeypatch) -> None:
    monkeypatch.setenv("OBSERVABILITY_PROMETHEUS_ENABLED", "true")
    monkeypatch.delenv("OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL", raising=False)

    assert prometheus.delete_pushgateway_job("swap_repair_v1") is False
