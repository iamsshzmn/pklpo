from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from src.candles.domain.candle_validation import CandleValidationError
from src.candles.domain.repair import RepairWindow
from src.candles.infrastructure.repair_repository import RepairCandlesRepository
from src.candles.repository import SwapCandlesRepository


def _raw_candle(**overrides: Any) -> dict[str, Any]:
    row = {
        "ts": 0,
        "open": 1.0,
        "high": 1.0,
        "low": 1.0,
        "close": 1.0,
        "volume": 1.0,
    }
    row.update(overrides)
    return row


def _normalized_candle(**overrides: Any) -> dict[str, Any]:
    row = {
        "timestamp": 0,
        "open": 1.0,
        "high": 1.0,
        "low": 1.0,
        "close": 1.0,
        "volume": 1.0,
        "fetched_at": datetime(2026, 5, 19, tzinfo=UTC),
    }
    row.update(overrides)
    return row


@dataclass
class _CandlesSettingsStub:
    strict_write_validation: bool


@dataclass
class _SettingsStub:
    candles: _CandlesSettingsStub


@pytest.mark.asyncio
async def test_swap_repository_logs_and_reraises_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import src.candles.repository as repository_module

    monkeypatch.setattr(
        repository_module,
        "get_settings",
        lambda: _SettingsStub(candles=_CandlesSettingsStub(True)),
    )
    repo = SwapCandlesRepository()

    async def fail_if_called(operation: object) -> int:
        raise AssertionError("DB retry should not run for validation failures")

    monkeypatch.setattr(repo, "_run_with_db_retry", fail_if_called)

    with pytest.raises(CandleValidationError) as exc_info:
        await repo.upsert_candles(
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            candles=[_raw_candle(open=2.0, high=1.0)],
            additional_data={},
            window=RepairWindow(0, 60_000),
        )

    assert exc_info.value.code == "geometry_violation"
    assert any(
        record.message == "candle.write_validation_failed"
        and record.code == "geometry_violation"
        and record.row_index == 0
        and record.timestamp == 0
        and record.symbol == "BTC-USDT-SWAP"
        and record.timeframe == "1m"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_swap_repository_strict_validation_false_bypasses_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.candles.repository as repository_module

    monkeypatch.setattr(
        repository_module,
        "get_settings",
        lambda: _SettingsStub(candles=_CandlesSettingsStub(False)),
    )
    repo = SwapCandlesRepository()
    called = False

    async def fake_retry(operation: object) -> int:
        nonlocal called
        called = True
        return 11

    monkeypatch.setattr(repo, "_run_with_db_retry", fake_retry)

    result = await repo.upsert_candles(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        candles=[_raw_candle(open=2.0, high=1.0)],
        additional_data={},
        window=RepairWindow(0, 60_000),
    )

    assert result == 11
    assert called is True


@pytest.mark.asyncio
async def test_repair_repository_logs_and_reraises_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import src.candles.infrastructure.repair_repository as repair_repository_module

    monkeypatch.setattr(
        repair_repository_module,
        "get_settings",
        lambda: _SettingsStub(candles=_CandlesSettingsStub(True)),
    )
    repo = RepairCandlesRepository()

    async def fail_if_called(operation: object) -> int:
        raise AssertionError("DB retry should not run for validation failures")

    monkeypatch.setattr(repo, "_run_with_db_retry", fail_if_called)

    with pytest.raises(CandleValidationError) as exc_info:
        await repo.selective_upsert_candles(
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            candles=[_normalized_candle(open=2.0, high=1.0)],
            window=RepairWindow(0, 60_000),
        )

    assert exc_info.value.code == "geometry_violation"
    assert any(
        record.message == "candle.write_validation_failed"
        and record.code == "geometry_violation"
        and record.row_index == 0
        and record.timestamp == 0
        and record.symbol == "BTC-USDT-SWAP"
        and record.timeframe == "1m"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_repair_repository_strict_validation_false_bypasses_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.candles.infrastructure.repair_repository as repair_repository_module

    monkeypatch.setattr(
        repair_repository_module,
        "get_settings",
        lambda: _SettingsStub(candles=_CandlesSettingsStub(False)),
    )
    repo = RepairCandlesRepository()
    called = False

    async def fake_retry(operation: object) -> int:
        nonlocal called
        called = True
        return 7

    monkeypatch.setattr(repo, "_run_with_db_retry", fake_retry)

    result = await repo.selective_upsert_candles(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        candles=[_normalized_candle(open=2.0, high=1.0)],
        window=RepairWindow(0, 60_000),
    )

    assert result == 7
    assert called is True


@pytest.mark.asyncio
async def test_count_valid_candles_counts_malformed_expected_rows_as_invalid_extra() -> None:
    class _Repository(RepairCandlesRepository):
        async def list_existing_valid_timestamps(self, **kwargs: Any) -> list[int]:
            return [0, 120_000]

        async def list_timestamps(self, **kwargs: Any) -> list[int]:
            return [0, 60_000, 120_000]

    rec = await _Repository().count_valid_candles(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=0,
        end_ts_ms=180_000,
    )

    assert rec.expected_bars == 3
    assert rec.valid_bars == 2
    assert rec.missing_bars == 1
    assert rec.invalid_extra_rows == 1


@pytest.mark.asyncio
async def test_count_valid_candles_counts_misaligned_raw_rows_as_invalid_extra() -> None:
    class _Repository(RepairCandlesRepository):
        async def list_existing_valid_timestamps(self, **kwargs: Any) -> list[int]:
            return [0, 60_000, 120_000]

        async def list_timestamps(self, **kwargs: Any) -> list[int]:
            return [0, 30_000, 60_000, 120_000]

    rec = await _Repository().count_valid_candles(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=0,
        end_ts_ms=180_000,
    )

    assert rec.expected_bars == 3
    assert rec.valid_bars == 3
    assert rec.missing_bars == 0
    assert rec.invalid_extra_rows == 1
