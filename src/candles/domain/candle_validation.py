from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from src.candles.domain.timeframes import TF_TO_MS

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from src.candles.domain.okx_calendar import StorageCalendar
    from src.candles.domain.repair import RepairWindow


class CandleValidationError(ValueError):
    def __init__(
        self,
        code: str,
        *,
        timestamp_ms: int | None,
        row_index: int,
    ) -> None:
        self.code = code
        self.timestamp_ms = timestamp_ms
        self.row_index = row_index
        super().__init__(f"{code}: row_index={row_index} timestamp_ms={timestamp_ms}")


def validate_candle_for_write(
    candle: Mapping[str, Any],
    *,
    symbol: str,
    timeframe: str,
    calendar: StorageCalendar,
    window: RepairWindow,
    row_index: int,
) -> None:
    try:
        timestamp_ms = _timestamp_ms(candle)
    except (TypeError, ValueError) as exc:
        raise CandleValidationError(
            "misaligned_ts",
            timestamp_ms=None,
            row_index=row_index,
        ) from exc

    if not symbol.strip():
        raise CandleValidationError(
            "empty_symbol", timestamp_ms=timestamp_ms, row_index=row_index
        )
    if timeframe not in TF_TO_MS:
        raise CandleValidationError(
            "unsupported_tf", timestamp_ms=timestamp_ms, row_index=row_index
        )
    if calendar.floor_open(timestamp_ms, timeframe) != timestamp_ms:
        raise CandleValidationError(
            "misaligned_ts", timestamp_ms=timestamp_ms, row_index=row_index
        )
    if timestamp_ms < window.start_ts_ms or timestamp_ms >= window.end_ts_ms:
        raise CandleValidationError(
            "ts_outside_window", timestamp_ms=timestamp_ms, row_index=row_index
        )

    raw_values = {
        name: candle.get(name) for name in ("open", "high", "low", "close", "volume")
    }
    if any(value is None for value in raw_values.values()):
        raise CandleValidationError(
            "null_field", timestamp_ms=timestamp_ms, row_index=row_index
        )

    try:
        open_price = _decimal(raw_values["open"])
        high_price = _decimal(raw_values["high"])
        low_price = _decimal(raw_values["low"])
        close_price = _decimal(raw_values["close"])
        volume = _decimal(raw_values["volume"])
    except (InvalidOperation, ValueError) as exc:
        raise CandleValidationError(
            "geometry_violation", timestamp_ms=timestamp_ms, row_index=row_index
        ) from exc

    if not all(
        value.is_finite()
        for value in (open_price, high_price, low_price, close_price, volume)
    ):
        raise CandleValidationError(
            "geometry_violation", timestamp_ms=timestamp_ms, row_index=row_index
        )
    if any(value <= 0 for value in (open_price, high_price, low_price, close_price)):
        raise CandleValidationError(
            "geometry_violation", timestamp_ms=timestamp_ms, row_index=row_index
        )
    if high_price < max(open_price, close_price, low_price):
        raise CandleValidationError(
            "geometry_violation", timestamp_ms=timestamp_ms, row_index=row_index
        )
    if low_price > min(open_price, close_price, high_price):
        raise CandleValidationError(
            "geometry_violation", timestamp_ms=timestamp_ms, row_index=row_index
        )
    if volume < 0:
        raise CandleValidationError(
            "negative_volume", timestamp_ms=timestamp_ms, row_index=row_index
        )


def validate_chunk_for_write(
    candles: Sequence[Mapping[str, Any]],
    *,
    symbol: str,
    timeframe: str,
    calendar: StorageCalendar,
    window: RepairWindow,
) -> None:
    seen: set[int] = set()
    for row_index, candle in enumerate(candles):
        validate_candle_for_write(
            candle,
            symbol=symbol,
            timeframe=timeframe,
            calendar=calendar,
            window=window,
            row_index=row_index,
        )
        timestamp_ms = _timestamp_ms(candle)
        if timestamp_ms in seen:
            raise CandleValidationError(
                "duplicate_ts", timestamp_ms=timestamp_ms, row_index=row_index
            )
        seen.add(timestamp_ms)


def _timestamp_ms(candle: Mapping[str, Any]) -> int:
    value = candle.get("ts", candle.get("timestamp"))
    return int(value)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))
