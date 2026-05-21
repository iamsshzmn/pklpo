from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.candles.domain.candle_validation import (
    CandleValidationError,
    validate_candle_for_write,
    validate_chunk_for_write,
)
from src.candles.domain.okx_calendar import StorageCalendar
from src.candles.domain.repair import RepairWindow
from src.candles.domain.timeframes import TF_TO_MS

_CAL = StorageCalendar()


def _ts(year: int, month: int, day: int, hour: int = 0) -> int:
    return int(datetime(year, month, day, hour, tzinfo=UTC).timestamp() * 1000)


def _candle(ts: int = 0, **overrides: Any) -> dict[str, Any]:
    row = {
        "ts": ts,
        "open": 10.0,
        "high": 12.0,
        "low": 9.0,
        "close": 11.0,
        "volume": 100.0,
    }
    row.update(overrides)
    return row


def _assert_code(exc_info: pytest.ExceptionInfo[CandleValidationError], code: str) -> None:
    assert exc_info.value.code == code


def test_misaligned_1d_cst_rejected() -> None:
    cst_midnight = _ts(2026, 5, 19, 16)

    with pytest.raises(CandleValidationError) as exc_info:
        validate_candle_for_write(
            _candle(cst_midnight),
            symbol="BTC-USDT-SWAP",
            timeframe="1D",
            calendar=_CAL,
            window=RepairWindow(_ts(2026, 5, 19), _ts(2026, 5, 21)),
            row_index=7,
        )

    _assert_code(exc_info, "misaligned_ts")
    assert exc_info.value.timestamp_ms == cst_midnight
    assert exc_info.value.row_index == 7


def test_misaligned_1w_anchor_rejected() -> None:
    tuesday = _ts(2026, 5, 19)

    with pytest.raises(CandleValidationError) as exc_info:
        validate_candle_for_write(
            _candle(tuesday),
            symbol="BTC-USDT-SWAP",
            timeframe="1W",
            calendar=_CAL,
            window=RepairWindow(_ts(2026, 5, 18), _ts(2026, 5, 25)),
            row_index=0,
        )

    _assert_code(exc_info, "misaligned_ts")


def test_misaligned_1m_non_month_start_rejected() -> None:
    jan_second = _ts(2026, 1, 2)

    with pytest.raises(CandleValidationError) as exc_info:
        validate_candle_for_write(
            _candle(jan_second),
            symbol="BTC-USDT-SWAP",
            timeframe="1M",
            calendar=_CAL,
            window=RepairWindow(_ts(2026, 1, 1), _ts(2026, 2, 1)),
            row_index=0,
        )

    _assert_code(exc_info, "misaligned_ts")


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"high": 8.0}, "geometry_violation"),
        ({"open": 13.0}, "geometry_violation"),
        ({"volume": -1.0}, "negative_volume"),
    ],
)
def test_ohlcv_value_violations_rejected(
    overrides: dict[str, Any],
    code: str,
) -> None:
    with pytest.raises(CandleValidationError) as exc_info:
        validate_candle_for_write(
            _candle(**overrides),
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            calendar=_CAL,
            window=RepairWindow(0, TF_TO_MS["1m"]),
            row_index=0,
        )

    _assert_code(exc_info, code)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("open", 0),
        ("high", 0),
        ("low", 0),
        ("close", 0),
        ("open", -1),
        ("high", -1),
        ("low", -1),
        ("close", -1),
    ],
)
def test_non_positive_ohlc_rejected_as_geometry_violation(
    field: str,
    value: int,
) -> None:
    with pytest.raises(CandleValidationError) as exc_info:
        validate_candle_for_write(
            _candle(**{field: value}),
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            calendar=_CAL,
            window=RepairWindow(0, TF_TO_MS["1m"]),
            row_index=0,
        )

    _assert_code(exc_info, "geometry_violation")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numeric_value_rejected_as_geometry_violation(value: str) -> None:
    with pytest.raises(CandleValidationError) as exc_info:
        validate_candle_for_write(
            _candle(open=value),
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            calendar=_CAL,
            window=RepairWindow(0, TF_TO_MS["1m"]),
            row_index=0,
        )

    _assert_code(exc_info, "geometry_violation")


@pytest.mark.parametrize("field", ["open", "high", "low", "close", "volume"])
def test_null_field_rejected(field: str) -> None:
    with pytest.raises(CandleValidationError) as exc_info:
        validate_candle_for_write(
            _candle(**{field: None}),
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            calendar=_CAL,
            window=RepairWindow(0, TF_TO_MS["1m"]),
            row_index=0,
        )

    _assert_code(exc_info, "null_field")


@pytest.mark.parametrize(
    ("symbol", "timeframe", "code"),
    [
        ("   ", "1m", "empty_symbol"),
        ("BTC-USDT-SWAP", "2m", "unsupported_tf"),
    ],
)
def test_symbol_and_timeframe_guards(symbol: str, timeframe: str, code: str) -> None:
    with pytest.raises(CandleValidationError) as exc_info:
        validate_candle_for_write(
            _candle(),
            symbol=symbol,
            timeframe=timeframe,
            calendar=_CAL,
            window=RepairWindow(0, TF_TO_MS["1m"]),
            row_index=0,
        )

    _assert_code(exc_info, code)


def test_ts_outside_window_rejected() -> None:
    with pytest.raises(CandleValidationError) as exc_info:
        validate_candle_for_write(
            _candle(60_000),
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            calendar=_CAL,
            window=RepairWindow(0, 60_000),
            row_index=0,
        )

    _assert_code(exc_info, "ts_outside_window")


@pytest.mark.parametrize("timestamp_value", [None, "not-a-timestamp"])
def test_malformed_timestamp_rejected_with_validation_error(
    timestamp_value: object,
) -> None:
    candle = _candle(0)
    del candle["ts"]
    if timestamp_value is not None:
        candle["timestamp"] = timestamp_value

    with pytest.raises(CandleValidationError) as exc_info:
        validate_candle_for_write(
            candle,
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            calendar=_CAL,
            window=RepairWindow(0, 60_000),
            row_index=3,
        )

    _assert_code(exc_info, "misaligned_ts")
    assert exc_info.value.timestamp_ms is None
    assert exc_info.value.row_index == 3


def test_duplicate_ts_inside_chunk_rejected() -> None:
    with pytest.raises(CandleValidationError) as exc_info:
        validate_chunk_for_write(
            [_candle(0), _candle(0, close=10.5)],
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            calendar=_CAL,
            window=RepairWindow(0, 60_000),
        )

    _assert_code(exc_info, "duplicate_ts")
    assert exc_info.value.row_index == 1


def test_chunk_valid_passes_with_normalized_timestamp_key() -> None:
    candles = [
        _candle(i * TF_TO_MS["5m"], timestamp=i * TF_TO_MS["5m"])
        for i in range(100)
    ]
    for candle in candles:
        del candle["ts"]

    validate_chunk_for_write(
        candles,
        symbol="BTC-USDT-SWAP",
        timeframe="5m",
        calendar=_CAL,
        window=RepairWindow(0, 100 * TF_TO_MS["5m"]),
    )
