from __future__ import annotations

from decimal import Decimal


def _facade_row(
    *,
    series_id: str,
    timestamp: int,
    close: str = "1",
    source_symbol: str,
    bar_kind: str = "native",
    adjustment_factor: str = "1",
    succession_id: str | None = None,
    is_gap: bool = False,
    gap_type: str | None = None,
):
    from src.identity.application.ohlcv_facade import OhlcvFacadeRow

    return OhlcvFacadeRow(
        series_id=series_id,
        timeframe="1m",
        timestamp=timestamp,
        open=None if is_gap else Decimal(close),
        high=None if is_gap else Decimal(close),
        low=None if is_gap else Decimal(close),
        close=None if is_gap else Decimal(close),
        volume=None if is_gap else Decimal("10"),
        segment_id="seg",
        source_venue=None if is_gap else "OKX",
        source_symbol=None if is_gap else source_symbol,
        source_timestamp=None if is_gap else timestamp,
        bar_kind=bar_kind,
        data_status="missing" if is_gap else "complete",
        succession_id=succession_id,
        adjustment_factor=Decimal(adjustment_factor),
        is_gap=is_gap,
        gap_type=gap_type,
    )


def _raw_bar(symbol: str, timestamp: int, close: str = "1"):
    from src.identity.application.shadow_mode_compare import RawBar

    return RawBar(
        symbol=symbol,
        timestamp=timestamp,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=Decimal("10"),
    )


def test_compare_trivial_series_is_clean_when_facade_matches_raw() -> None:
    from src.identity.application.shadow_mode_compare import compare_trivial_series

    raw_rows = [_raw_bar("BTC-USDT-SWAP", 1000), _raw_bar("BTC-USDT-SWAP", 2000)]
    facade_rows = [
        _facade_row(
            series_id="BTC-USDT-SWAP", timestamp=1000, source_symbol="BTC-USDT-SWAP"
        ),
        _facade_row(
            series_id="BTC-USDT-SWAP", timestamp=2000, source_symbol="BTC-USDT-SWAP"
        ),
    ]

    result = compare_trivial_series("BTC-USDT-SWAP", "1m", raw_rows, facade_rows)

    assert result.is_clean is True
    assert result.raw_count == 2
    assert result.facade_count == 2
    assert result.mismatches == ()


def test_compare_trivial_series_flags_value_mismatch() -> None:
    from src.identity.application.shadow_mode_compare import compare_trivial_series

    raw_rows = [_raw_bar("BTC-USDT-SWAP", 1000, close="100")]
    facade_rows = [
        _facade_row(
            series_id="BTC-USDT-SWAP",
            timestamp=1000,
            close="101",
            source_symbol="BTC-USDT-SWAP",
        )
    ]

    result = compare_trivial_series("BTC-USDT-SWAP", "1m", raw_rows, facade_rows)

    assert result.is_clean is False
    assert any(m.kind == "value_mismatch" for m in result.mismatches)


def test_compare_trivial_series_flags_non_native_bar_kind_and_adjustment() -> None:
    from src.identity.application.shadow_mode_compare import compare_trivial_series

    raw_rows = [_raw_bar("BTC-USDT-SWAP", 1000)]
    facade_rows = [
        _facade_row(
            series_id="BTC-USDT-SWAP",
            timestamp=1000,
            source_symbol="BTC-USDT-SWAP",
            bar_kind="synthetic",
            adjustment_factor="1.5",
            succession_id="lineage",
        )
    ]

    result = compare_trivial_series("BTC-USDT-SWAP", "1m", raw_rows, facade_rows)

    kinds = {m.kind for m in result.mismatches}
    assert "bar_kind_mismatch" in kinds
    assert "adjustment_factor_mismatch" in kinds
    assert "succession_id_mismatch" in kinds


def test_compare_trivial_series_flags_missing_rows_either_direction() -> None:
    from src.identity.application.shadow_mode_compare import compare_trivial_series

    raw_rows = [_raw_bar("BTC-USDT-SWAP", 1000), _raw_bar("BTC-USDT-SWAP", 2000)]
    facade_rows = [
        _facade_row(
            series_id="BTC-USDT-SWAP", timestamp=1000, source_symbol="BTC-USDT-SWAP"
        ),
        _facade_row(
            series_id="BTC-USDT-SWAP", timestamp=3000, source_symbol="BTC-USDT-SWAP"
        ),
    ]

    result = compare_trivial_series("BTC-USDT-SWAP", "1m", raw_rows, facade_rows)

    kinds_by_ts = {m.timestamp: m.kind for m in result.mismatches}
    assert kinds_by_ts[2000] == "missing_in_facade"
    assert kinds_by_ts[3000] == "missing_in_raw"


def test_compare_composite_series_explains_gap_and_segment_boundary() -> None:
    from src.identity.application.shadow_mode_compare import (
        GapWindow,
        SegmentWindow,
        compare_composite_series,
    )

    # 1000: TON leg, matches facade exactly -> clean.
    # 2000: TON raw bar sits inside a classified migration_halt gap -> explained.
    # 3000: GRAM leg after the cutover, facade agrees -> clean.
    # 4000: output-only gap marker from the facade (never physically stored raw).
    raw_rows_by_symbol = {
        "TON-USDT-SWAP": [
            _raw_bar("TON-USDT-SWAP", 1000),
            _raw_bar("TON-USDT-SWAP", 2000),
        ],
        "GRAM-USDT-SWAP": [_raw_bar("GRAM-USDT-SWAP", 3000)],
    }
    facade_rows = [
        _facade_row(
            series_id="TON-USDT-SWAP", timestamp=1000, source_symbol="TON-USDT-SWAP"
        ),
        _facade_row(
            series_id="TON-USDT-SWAP", timestamp=3000, source_symbol="GRAM-USDT-SWAP"
        ),
        _facade_row(
            series_id="TON-USDT-SWAP",
            timestamp=4000,
            source_symbol="GRAM-USDT-SWAP",
            is_gap=True,
            gap_type="migration_halt",
            bar_kind="gap_marker",
        ),
    ]
    gap_ranges = [
        GapWindow(gap_start_ts=1500, gap_end_ts=2500, gap_type="migration_halt")
    ]
    segments = [
        SegmentWindow(
            source_symbol="TON-USDT-SWAP", segment_start_ts=0, segment_end_ts=2500
        ),
        SegmentWindow(
            source_symbol="GRAM-USDT-SWAP", segment_start_ts=2500, segment_end_ts=None
        ),
    ]

    result = compare_composite_series(
        "TON-USDT-SWAP", "1m", raw_rows_by_symbol, facade_rows, gap_ranges, segments
    )

    assert result.is_clean is True
    assert result.unexplained == ()
    explained_kinds = {(d.timestamp, d.kind) for d in result.explained}
    assert (2000, "known_gap") in explained_kinds
    assert (4000, "gap_marker_output_only") in explained_kinds
    assert result.raw_symbol_counts == {"TON-USDT-SWAP": 2, "GRAM-USDT-SWAP": 1}
    assert result.facade_bar_count == 2
    assert result.facade_gap_marker_count == 1


def test_compare_composite_series_flags_unexplained_discrepancy() -> None:
    from src.identity.application.shadow_mode_compare import compare_composite_series

    # Raw TON bar at 5000 is neither reflected in the facade nor covered by any
    # classified gap or segment boundary -> must surface as unexplained.
    raw_rows_by_symbol = {"TON-USDT-SWAP": [_raw_bar("TON-USDT-SWAP", 5000)]}
    facade_rows: list = []
    gap_ranges: list = []
    segments: list = []

    result = compare_composite_series(
        "TON-USDT-SWAP", "1m", raw_rows_by_symbol, facade_rows, gap_ranges, segments
    )

    assert result.is_clean is False
    assert len(result.unexplained) == 1
    assert result.unexplained[0].kind == "missing_in_facade"


def test_compare_composite_series_flags_source_symbol_mismatch_without_segment() -> (
    None
):
    from src.identity.application.shadow_mode_compare import compare_composite_series

    # Facade attributes 6000 to GRAM, but raw TON also has a bar there and no
    # segment says TON was superseded by then -> unexplained, not silently
    # accepted as an "overlap".
    raw_rows_by_symbol = {"TON-USDT-SWAP": [_raw_bar("TON-USDT-SWAP", 6000)]}
    facade_rows = [
        _facade_row(
            series_id="TON-USDT-SWAP", timestamp=6000, source_symbol="GRAM-USDT-SWAP"
        )
    ]
    gap_ranges: list = []
    segments: list = []

    result = compare_composite_series(
        "TON-USDT-SWAP", "1m", raw_rows_by_symbol, facade_rows, gap_ranges, segments
    )

    assert result.is_clean is False
    assert result.unexplained[0].kind == "source_symbol_mismatch"
