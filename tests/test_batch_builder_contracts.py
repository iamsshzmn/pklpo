import pandas as pd

from src.features.infrastructure.persistence.batch_builder import build_batch_data


def test_build_batch_data_deduplicates_across_chunk_boundaries_with_shared_set():
    db_cols = {"symbol", "timeframe", "timestamp", "calculated_at", "ema_21"}
    validator = lambda _ts, _idx: True
    seen_timestamps: set[int] = set()
    duplicate_events: list[tuple[str, str, int]] = []

    first_chunk = pd.DataFrame(
        {
            "timestamp": [1_000, 2_000],
            "ema_21": [10.0, 11.0],
        }
    )
    second_chunk = pd.DataFrame(
        {
            "timestamp": [2_000, 3_000],
            "ema_21": [11.5, 12.0],
        }
    )

    batch_1, skipped_1 = build_batch_data(
        first_chunk,
        "BTC-USDT-SWAP",
        "1m",
        db_cols,
        timestamp_validator=validator,
        seen_timestamps=seen_timestamps,
        on_duplicate=lambda s, tf, cnt: duplicate_events.append((s, tf, cnt)),
    )
    batch_2, skipped_2 = build_batch_data(
        second_chunk,
        "BTC-USDT-SWAP",
        "1m",
        db_cols,
        timestamp_validator=validator,
        seen_timestamps=seen_timestamps,
        on_duplicate=lambda s, tf, cnt: duplicate_events.append((s, tf, cnt)),
    )

    assert skipped_1 == 0
    assert skipped_2 == 0
    assert len(batch_1) == 2
    assert len(batch_2) == 1
    assert batch_2[0]["timestamp"] == 3_000
    assert seen_timestamps == {1_000, 2_000, 3_000}
    assert duplicate_events == [("BTC-USDT-SWAP", "1m", 1)]


def test_build_batch_data_keeps_boundary_rows_without_shared_set():
    db_cols = {"symbol", "timeframe", "timestamp", "calculated_at", "ema_21"}
    validator = lambda _ts, _idx: True

    first_chunk = pd.DataFrame(
        {
            "timestamp": [1_000, 2_000],
            "ema_21": [10.0, 11.0],
        }
    )
    second_chunk = pd.DataFrame(
        {
            "timestamp": [2_000, 3_000],
            "ema_21": [11.5, 12.0],
        }
    )

    batch_1, _ = build_batch_data(
        first_chunk,
        "BTC-USDT-SWAP",
        "1m",
        db_cols,
        timestamp_validator=validator,
    )
    batch_2, _ = build_batch_data(
        second_chunk,
        "BTC-USDT-SWAP",
        "1m",
        db_cols,
        timestamp_validator=validator,
    )

    assert len(batch_1) == 2
    assert len(batch_2) == 2
