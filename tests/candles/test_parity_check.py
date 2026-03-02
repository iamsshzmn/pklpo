from __future__ import annotations

import pytest

from src.candles.parity_check import (
    ParityGate,
    compare_candles,
    evaluate_parity_gate,
    run_adapter_parity_check,
)


def test_compare_candles_ok() -> None:
    baseline = [
        {"ts": 1, "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 100},
        {"ts": 2, "open": 10.5, "high": 11.2, "low": 10.0, "close": 11.0, "volume": 110},
    ]
    candidate = [
        {"ts": 1, "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 100},
        {"ts": 2, "open": 10.5, "high": 11.2, "low": 10.0, "close": 11.0, "volume": 110},
    ]

    report = compare_candles(baseline_rows=baseline, candidate_rows=candidate)
    assert report["ok"] is True
    assert report["mismatch_count"] == 0
    assert report["missing_in_candidate_count"] == 0
    assert report["extra_in_candidate_count"] == 0


def test_compare_candles_detects_mismatch_and_missing() -> None:
    baseline = [
        {"ts": 1, "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 100},
        {"ts": 2, "open": 10.5, "high": 11.2, "low": 10.0, "close": 11.0, "volume": 110},
    ]
    candidate = [
        {"ts": 1, "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.4, "volume": 100},
        {"ts": 3, "open": 10.7, "high": 11.3, "low": 10.1, "close": 11.1, "volume": 120},
    ]

    report = compare_candles(baseline_rows=baseline, candidate_rows=candidate)
    assert report["ok"] is False
    assert report["mismatch_count"] == 1
    assert report["missing_in_candidate_count"] == 1
    assert report["extra_in_candidate_count"] == 1


class _FakeAdapter:
    def __init__(self, data: dict[str, list[dict]]) -> None:
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def get_candles(
        self,
        *,
        inst_id: str,
        bar: str = "1m",
        limit: int = 300,
        before: str | None = None,
        after: str | None = None,
    ):
        return self._data.get(inst_id, [])[:limit]

    async def get_funding_rates(self, symbols):
        return {s: {} for s in symbols}

    async def get_open_interest(self, symbols):
        return {s: {} for s in symbols}


@pytest.mark.asyncio
async def test_run_adapter_parity_check_aggregates() -> None:
    baseline_adapter = _FakeAdapter(
        {
            "BTC-USDT-SWAP": [
                {"ts": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10}
            ],
            "ETH-USDT-SWAP": [
                {"ts": 1, "open": 2, "high": 3, "low": 1.5, "close": 2.5, "volume": 20}
            ],
        }
    )
    candidate_adapter = _FakeAdapter(
        {
            "BTC-USDT-SWAP": [
                {"ts": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10}
            ],
            "ETH-USDT-SWAP": [
                {"ts": 1, "open": 2, "high": 3, "low": 1.5, "close": 2.4, "volume": 20}
            ],
        }
    )

    report = await run_adapter_parity_check(
        baseline_adapter=baseline_adapter,  # type: ignore[arg-type]
        candidate_adapter=candidate_adapter,  # type: ignore[arg-type]
        symbols=["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
        timeframe="1m",
    )

    assert report["symbols_total"] == 2
    assert report["symbols_failed"] == 1
    assert report["ok"] is False


def test_evaluate_parity_gate_respects_thresholds() -> None:
    report = {
        "per_symbol": {
            "BTC-USDT-SWAP": {
                "mismatch_count": 1,
                "missing_in_candidate_count": 0,
                "extra_in_candidate_count": 0,
            },
            "ETH-USDT-SWAP": {
                "mismatch_count": 0,
                "missing_in_candidate_count": 1,
                "extra_in_candidate_count": 0,
            },
        }
    }
    gate = ParityGate(
        max_failed_symbols=1,
        max_mismatch_per_symbol=0,
        max_missing_per_symbol=0,
        max_extra_per_symbol=0,
    )

    result = evaluate_parity_gate(report, gate)
    assert result["ok"] is False
    assert result["failed_symbols"] == 2
    assert "BTC-USDT-SWAP" in result["violations"]
    assert "ETH-USDT-SWAP" in result["violations"]


def test_evaluate_parity_gate_allows_configured_drift() -> None:
    report = {
        "per_symbol": {
            "BTC-USDT-SWAP": {
                "mismatch_count": 1,
                "missing_in_candidate_count": 0,
                "extra_in_candidate_count": 1,
            }
        }
    }
    gate = ParityGate(
        max_failed_symbols=1,
        max_mismatch_per_symbol=1,
        max_missing_per_symbol=0,
        max_extra_per_symbol=1,
    )

    result = evaluate_parity_gate(report, gate)
    assert result["ok"] is True
    assert result["failed_symbols"] == 0
    assert result["violations"] == {}
