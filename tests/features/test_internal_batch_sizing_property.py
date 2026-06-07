"""Property-based tests for adaptive batch sizing."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from src.features.infrastructure.upsert import (
    DEFAULT_MAX_BATCH_SIZE,
    DEFAULT_MIN_BATCH_SIZE,
    TARGET_SQL_PARAMS,
    _get_dynamic_batch_size,
)


@settings(max_examples=100)
@given(
    num_fields=st.integers(min_value=0, max_value=2000),
    total_records=st.integers(min_value=0, max_value=2_000_000),
)
def test_batch_size_is_within_global_bounds(num_fields: int, total_records: int) -> None:
    batch_size = _get_dynamic_batch_size(num_fields, total_records)
    assert DEFAULT_MIN_BATCH_SIZE <= batch_size <= DEFAULT_MAX_BATCH_SIZE


@settings(max_examples=100)
@given(
    num_fields=st.integers(min_value=1, max_value=2000),
    total_records=st.integers(min_value=0, max_value=2_000_000),
)
def test_batch_size_does_not_exceed_target_sql_params(
    num_fields: int, total_records: int
) -> None:
    batch_size = _get_dynamic_batch_size(num_fields, total_records)
    assert batch_size * num_fields <= max(
        TARGET_SQL_PARAMS, DEFAULT_MIN_BATCH_SIZE * num_fields
    )


@settings(max_examples=100, deadline=None)
@given(
    total_records=st.integers(min_value=0, max_value=2_000_000),
    num_fields=st.integers(min_value=1, max_value=2000),
)
def test_all_records_are_covered_by_batches(
    total_records: int,
    num_fields: int,
) -> None:
    batch_size = _get_dynamic_batch_size(num_fields, total_records)

    batches = []
    start = 0
    while start < total_records:
        end = min(start + batch_size, total_records)
        batches.append(end - start)
        start = end

    assert sum(batches) == total_records
