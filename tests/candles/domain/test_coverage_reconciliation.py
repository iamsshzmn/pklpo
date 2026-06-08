from __future__ import annotations

from src.candles.domain.okx_calendar import StorageCalendar
from src.candles.domain.repair import RepairWindow, reconcile_coverage
from src.candles.domain.timeframes import TF_TO_MS

_CAL = StorageCalendar()
_1D_MS = TF_TO_MS["1D"]
_1H_MS = TF_TO_MS["1H"]
_1W_MS = TF_TO_MS["1W"]


def test_raw_count_can_exceed_expected_but_valid_count_correct() -> None:
    window = RepairWindow(start_ts_ms=0, end_ts_ms=3 * _1H_MS)
    timestamps = [0, _1H_MS, 2 * _1H_MS, 2 * _1H_MS, 3 * _1H_MS - 1]

    rec = reconcile_coverage(
        timestamps=timestamps,
        timeframe="1H",
        window=window,
        calendar=_CAL,
    )

    assert rec.expected_bars == 3
    assert rec.valid_bars == 3
    assert rec.missing_bars == 0
    assert rec.invalid_extra_rows == 1


def test_invalid_cst_1d_row_not_counted_as_valid_coverage() -> None:
    window = RepairWindow(start_ts_ms=0, end_ts_ms=2 * _1D_MS)
    cst_midnight_timestamp = 16 * _1H_MS

    rec = reconcile_coverage(
        timestamps=[0, cst_midnight_timestamp],
        timeframe="1D",
        window=window,
        calendar=_CAL,
    )

    assert rec.expected_bars == 2
    assert rec.valid_bars == 1
    assert rec.missing_bars == 1
    assert rec.invalid_extra_rows == 1


def test_invalid_1w_anchor_not_counted_as_valid_coverage() -> None:
    monday_1970_01_05 = 4 * _1D_MS
    window = RepairWindow(
        start_ts_ms=monday_1970_01_05,
        end_ts_ms=monday_1970_01_05 + _1W_MS,
    )

    rec = reconcile_coverage(
        timestamps=[monday_1970_01_05 + _1D_MS],
        timeframe="1W",
        window=window,
        calendar=_CAL,
    )

    assert rec.expected_bars == 1
    assert rec.valid_bars == 0
    assert rec.missing_bars == 1
    assert rec.invalid_extra_rows == 1


def test_invalid_1m_non_month_start_not_counted_as_valid_coverage() -> None:
    feb_1_2024 = 1_706_745_600_000
    mar_1_2024 = 1_709_251_200_000
    feb_2_2024 = feb_1_2024 + _1D_MS
    window = RepairWindow(start_ts_ms=feb_1_2024, end_ts_ms=mar_1_2024)

    rec = reconcile_coverage(
        timestamps=[feb_2_2024],
        timeframe="1M",
        window=window,
        calendar=_CAL,
    )

    assert rec.expected_bars == 1
    assert rec.valid_bars == 0
    assert rec.missing_bars == 1
    assert rec.invalid_extra_rows == 1


def test_full_coverage_reports_zero_missing() -> None:
    window = RepairWindow(start_ts_ms=0, end_ts_ms=3 * _1H_MS)

    rec = reconcile_coverage(
        timestamps=[0, _1H_MS, 2 * _1H_MS],
        timeframe="1H",
        window=window,
        calendar=_CAL,
    )

    assert rec.expected_bars == 3
    assert rec.valid_bars == 3
    assert rec.missing_bars == 0
    assert rec.invalid_extra_rows == 0
