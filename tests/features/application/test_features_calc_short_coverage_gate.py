from __future__ import annotations

from typing import Any

import pandas as pd
import pytest


def _eligibility_record(
    *,
    state: str = "eligible",
    can_compute_features: bool = True,
):
    from src.candles.interfaces.eligibility import EligibilityRecord

    return EligibilityRecord(
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
        state=state,
        can_compute_features=can_compute_features,
        can_score=can_compute_features,
        can_train_ml=can_compute_features,
        context_only=False,
        reason_flags=[],
        actual_bars=500,
        required_bars=500,
        coverage_pct=100.0,
        evaluated_at=None,
    )


async def _eligible_state(_symbol: str, _timeframe: str):
    return _eligibility_record()


@pytest.mark.asyncio
async def test_process_symbol_features_skips_when_coverage_gate_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.candles.interfaces import eligibility as eligibility_interface
    from src.features.application import features_calc_short_service as service

    async def _last_calculated_ts(*_args: Any, **_kwargs: Any) -> int | None:
        return 0

    async def _has_new_ohlcv(*_args: Any, **_kwargs: Any) -> tuple[bool, int | None]:
        return (True, 280)

    async def _ohlcv_window(*_args: Any, **_kwargs: Any) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "timestamp": ts * 1000,
                    "open": 1,
                    "high": 2,
                    "low": 1,
                    "close": 2,
                    "volume": 10,
                }
                for ts in (100, 220, 280)
            ]
        )

    compute_calls: list[str] = []
    save_calls: list[str] = []

    async def _save_features_batch(*_args: Any, **_kwargs: Any) -> int:
        save_calls.append("save")
        return 1

    monkeypatch.setattr(service, "get_last_calculated_ts", _last_calculated_ts)
    monkeypatch.setattr(service, "check_has_new_ohlcv", _has_new_ohlcv)
    monkeypatch.setattr(service, "get_ohlcv_window", _ohlcv_window)
    monkeypatch.setattr(eligibility_interface, "get_state", _eligible_state)
    monkeypatch.setattr(
        service,
        "compute_features",
        lambda *_args, **_kwargs: compute_calls.append("compute"),
    )
    monkeypatch.setattr(service, "save_features_batch", _save_features_batch)

    result = await service.process_symbol_features(
        session=object(),  # type: ignore[arg-type]
        symbol="BTC-USDT-SWAP",
        timeframes=["1m"],
        specs=["rsi"],
        storage_gateway=object(),  # type: ignore[arg-type]
        save_dependencies_factory=object(),  # type: ignore[arg-type]
        warmup_bars=3,
    )

    assert result["success"]
    assert result["results"]["1m"]["status"] == "skipped"
    assert result["results"]["1m"]["reason"] == "coverage_gate_failed"
    assert result["results"]["1m"]["coverage_gate_reason"] == "interior_gap"
    assert compute_calls == []
    assert save_calls == []


@pytest.mark.asyncio
async def test_process_symbol_features_skips_when_eligibility_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.candles.interfaces import eligibility as eligibility_interface
    from src.candles.interfaces.eligibility import EligibilityRecord
    from src.features.application import features_calc_short_service as service

    async def _last_calculated_ts(*_args: Any, **_kwargs: Any) -> int | None:
        return 0

    async def _has_new_ohlcv(*_args: Any, **_kwargs: Any) -> tuple[bool, int | None]:
        return (True, 280)

    async def _blocked_state(_symbol: str, _timeframe: str) -> EligibilityRecord:
        return EligibilityRecord(
            symbol="BTC-USDT-SWAP",
            timeframe="1H",
            state="insufficient_history",
            can_compute_features=False,
            can_score=False,
            can_train_ml=False,
            context_only=False,
            reason_flags=["SHORT_HISTORY"],
            actual_bars=279,
            required_bars=500,
            coverage_pct=100.0,
            evaluated_at=None,
        )

    compute_calls: list[str] = []

    monkeypatch.setattr(service, "get_last_calculated_ts", _last_calculated_ts)
    monkeypatch.setattr(service, "check_has_new_ohlcv", _has_new_ohlcv)
    monkeypatch.setattr(eligibility_interface, "get_state", _blocked_state)
    monkeypatch.setattr(
        service,
        "compute_features",
        lambda *_args, **_kwargs: compute_calls.append("compute"),
    )

    result = await service.process_symbol_features(
        session=object(),  # type: ignore[arg-type]
        symbol="BTC-USDT-SWAP",
        timeframes=["1H"],
        specs=["rsi"],
        storage_gateway=object(),  # type: ignore[arg-type]
        save_dependencies_factory=object(),  # type: ignore[arg-type]
        warmup_bars=500,
    )

    assert result["success"]
    assert result["results"]["1H"]["status"] == "skipped"
    assert result["results"]["1H"]["reason"] == "feature_eligibility_blocked"
    assert result["results"]["1H"]["eligibility_state"] == "insufficient_history"
    assert compute_calls == []


@pytest.mark.asyncio
async def test_process_symbol_features_skips_when_eligibility_row_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.candles.interfaces import eligibility as eligibility_interface
    from src.features.application import features_calc_short_service as service

    async def _last_calculated_ts(*_args: Any, **_kwargs: Any) -> int | None:
        return 0

    async def _has_new_ohlcv(*_args: Any, **_kwargs: Any) -> tuple[bool, int | None]:
        return (True, 280)

    async def _missing_state(_symbol: str, _timeframe: str) -> None:
        return None

    compute_calls: list[str] = []

    monkeypatch.setattr(service, "get_last_calculated_ts", _last_calculated_ts)
    monkeypatch.setattr(service, "check_has_new_ohlcv", _has_new_ohlcv)
    monkeypatch.setattr(eligibility_interface, "get_state", _missing_state)
    monkeypatch.setattr(
        service,
        "compute_features",
        lambda *_args, **_kwargs: compute_calls.append("compute"),
    )

    result = await service.process_symbol_features(
        session=object(),  # type: ignore[arg-type]
        symbol="BTC-USDT-SWAP",
        timeframes=["1H"],
        specs=["rsi"],
        storage_gateway=object(),  # type: ignore[arg-type]
        save_dependencies_factory=object(),  # type: ignore[arg-type]
        warmup_bars=500,
    )

    assert result["success"]
    assert result["results"]["1H"]["status"] == "skipped"
    assert result["results"]["1H"]["reason"] == "feature_eligibility_missing"
    assert compute_calls == []
