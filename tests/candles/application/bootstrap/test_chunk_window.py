from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.candles.application.bootstrap.planning import compute_chunk_window
from src.candles.domain.okx_calendar import StorageCalendar
from src.candles.domain.timeframes import TF_TO_MS

CAL = StorageCalendar()


def _ts(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
    return int(datetime(year, month, day, hour, minute, tzinfo=UTC).timestamp() * 1000)


def test_compute_chunk_window_1m_steps_by_calendar_chunk_bars_small() -> None:
    assert compute_chunk_window(
        checkpoint_ts=_ts(2024, 4, 1),
        chunk_bars=2,
        timeframe="1M",
        calendar=CAL,
    ) == (_ts(2024, 2, 1), _ts(2024, 4, 1))


def test_compute_chunk_window_1m_leap_feb() -> None:
    start, end = compute_chunk_window(
        checkpoint_ts=_ts(2024, 3, 1),
        chunk_bars=1,
        timeframe="1M",
        calendar=CAL,
    )

    assert (start, end) == (_ts(2024, 2, 1), _ts(2024, 3, 1))
    assert end - start == 29 * TF_TO_MS["1D"]


def test_compute_chunk_window_1m_year_transition() -> None:
    assert compute_chunk_window(
        checkpoint_ts=_ts(2025, 2, 1),
        chunk_bars=2,
        timeframe="1M",
        calendar=CAL,
    ) == (_ts(2024, 12, 1), _ts(2025, 2, 1))


def test_compute_chunk_window_1w_respects_monday_utc_anchor() -> None:
    assert compute_chunk_window(
        checkpoint_ts=_ts(2026, 1, 21),
        chunk_bars=2,
        timeframe="1W",
        calendar=CAL,
    ) == (_ts(2026, 1, 5), _ts(2026, 1, 19))


@pytest.mark.parametrize("timeframe", ["1m", "5m", "1H", "1D"])
def test_compute_chunk_window_fixed_tf_unchanged(timeframe: str) -> None:
    checkpoint = _ts(2026, 5, 19)
    chunk_bars = 7
    old_arithmetic = (
        checkpoint - chunk_bars * TF_TO_MS[timeframe],
        checkpoint,
    )

    assert (
        compute_chunk_window(
            checkpoint_ts=checkpoint,
            chunk_bars=chunk_bars,
            timeframe=timeframe,
            calendar=CAL,
        )
        == old_arithmetic
    )
