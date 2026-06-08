"""Contract tests for batch_builder facade and build_batch_data."""

from __future__ import annotations

import datetime

import pandas as pd

from src.features.infrastructure.persistence.batch_builder import (
    TimestampValidatorProtocol,
    build_batch_data,
    filter_batch_by_schema,
    normalize_record_names,
)


def _make_ind_df(rows: int = 5, base_ts: int = 1_700_000_000_000) -> pd.DataFrame:
    ts = [base_ts + i * 60_000 for i in range(rows)]
    return pd.DataFrame(
        {
            "timestamp": ts,
            "close": [100.0 + i for i in range(rows)],
            "rsi_14": [50.0 + i for i in range(rows)],
            "ema_21": [100.0 + i * 0.5 for i in range(rows)],
        }
    )


def _make_db_cols() -> set[str]:
    return {"rsi_14", "ema_21", "timestamp"}


def test_build_batch_data_returns_tuple():
    df = _make_ind_df()
    result = build_batch_data(df, "BTC-USDT", "1m", _make_db_cols())
    assert isinstance(result, tuple)
    assert len(result) == 2
    batch, skipped = result
    assert isinstance(batch, list)
    assert isinstance(skipped, int)


def test_build_batch_data_rows_count():
    df = _make_ind_df(5)
    batch, skipped = build_batch_data(df, "BTC-USDT", "1m", _make_db_cols())
    assert len(batch) == 5
    assert skipped == 0


def test_build_batch_data_metadata_fields():
    df = _make_ind_df(3)
    batch, _ = build_batch_data(df, "BTC-USDT", "1m", _make_db_cols())
    for row in batch:
        assert "symbol" in row
        assert "timeframe" in row
        assert "timestamp" in row
        assert "calculated_at" in row
        assert row["symbol"] == "BTC-USDT"
        assert row["timeframe"] == "1m"


def test_build_batch_data_uses_utc_timezone_aware_calculated_at():
    df = _make_ind_df(1)
    batch, _ = build_batch_data(df, "BTC-USDT", "1m", _make_db_cols())
    assert batch[0]["calculated_at"].tzinfo is None
    assert batch[0]["calculated_at"] == datetime.datetime.utcfromtimestamp(
        batch[0]["timestamp"] / 1000
    )


def test_build_batch_data_filters_nan():
    df = _make_ind_df(3)
    df.at[1, "rsi_14"] = float("nan")
    batch, _ = build_batch_data(df, "BTC-USDT", "1m", _make_db_cols())
    row1 = next(r for r in batch if r["timestamp"] == df.at[1, "timestamp"])
    assert "rsi_14" not in row1 or row1.get("rsi_14") is None


def test_build_batch_data_filters_inf():
    df = _make_ind_df(3)
    df.at[0, "ema_21"] = float("inf")
    batch, _ = build_batch_data(df, "BTC-USDT", "1m", _make_db_cols())
    row0 = next(r for r in batch if r["timestamp"] == df.at[0, "timestamp"])
    assert "ema_21" not in row0 or row0.get("ema_21") is None


def test_build_batch_data_deduplication():
    base_ts = 1_700_000_000_000
    df = pd.DataFrame(
        {
            "timestamp": [base_ts, base_ts, base_ts + 60_000],
            "rsi_14": [50.0, 51.0, 52.0],
        }
    )
    batch, _ = build_batch_data(df, "BTC-USDT", "1m", {"rsi_14"})
    timestamps = [r["timestamp"] for r in batch]
    assert len(set(timestamps)) == len(timestamps)
    assert len(batch) == 2


def test_build_batch_data_skips_none_timestamp():
    df = pd.DataFrame(
        {
            "timestamp": [None, 1_700_000_060_000],
            "rsi_14": [50.0, 51.0],
        }
    )
    batch, skipped = build_batch_data(df, "BTC-USDT", "1m", {"rsi_14"})
    assert skipped >= 1
    assert len(batch) == 1


def test_build_batch_data_custom_validator():
    calls: list[tuple] = []

    def tracking_validator(ts: int | None, idx: int | str) -> bool:
        calls.append((ts, idx))
        return ts is not None

    df = _make_ind_df(3)
    build_batch_data(
        df,
        "BTC-USDT",
        "1m",
        _make_db_cols(),
        timestamp_validator=tracking_validator,
    )
    assert len(calls) == 3


def test_facade_imports():
    assert callable(build_batch_data)
    assert callable(filter_batch_by_schema)
    assert callable(normalize_record_names)
    assert TimestampValidatorProtocol is not None


def test_filter_batch_by_schema_keeps_allowed_keys():
    base_keys = ["symbol", "timeframe", "timestamp"]
    batch = [
        {
            "symbol": "BTC-USDT",
            "timeframe": "1m",
            "timestamp": 1,
            "rsi_14": 50.0,
            "unknown_col": 99.0,
        },
    ]
    db_cols = {"symbol", "timeframe", "timestamp", "rsi_14"}
    filtered = filter_batch_by_schema(batch, db_cols, base_keys)
    for row in filtered:
        assert "unknown_col" not in row
        assert "rsi_14" in row
