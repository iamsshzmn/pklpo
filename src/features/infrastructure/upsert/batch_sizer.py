from __future__ import annotations

import os

DEFAULT_MIN_BATCH_SIZE = 5
DEFAULT_MAX_BATCH_SIZE = int(os.getenv("FEATURES_UPSERT_MAX_BATCH_SIZE", "200"))
TARGET_SQL_PARAMS = int(os.getenv("FEATURES_UPSERT_TARGET_SQL_PARAMS", "15000"))
DIAGNOSTIC_SINGLE_ROW = os.getenv("DIAGNOSTIC_SINGLE_ROW", "0").lower() in (
    "1",
    "true",
    "yes",
)


def _get_dynamic_batch_size(num_fields: int, total_records: int) -> int:
    """Compute adaptive batch size based on row width and workload size."""
    if num_fields <= 0:
        return DEFAULT_MIN_BATCH_SIZE

    by_sql_params = max(DEFAULT_MIN_BATCH_SIZE, TARGET_SQL_PARAMS // num_fields)
    batch_size = min(DEFAULT_MAX_BATCH_SIZE, by_sql_params)

    if total_records > 50_000:
        batch_size = max(DEFAULT_MIN_BATCH_SIZE, batch_size // 2)
    elif total_records > 10_000:
        batch_size = max(DEFAULT_MIN_BATCH_SIZE, int(batch_size * 0.75))

    return batch_size


__all__ = [
    "DEFAULT_MAX_BATCH_SIZE",
    "DEFAULT_MIN_BATCH_SIZE",
    "DIAGNOSTIC_SINGLE_ROW",
    "TARGET_SQL_PARAMS",
    "_get_dynamic_batch_size",
]
