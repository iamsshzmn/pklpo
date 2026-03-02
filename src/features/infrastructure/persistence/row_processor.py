"""Row processing for indicator batch preparation."""

from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import numpy as np

from src.logging import get_logger

from ...schema.name_aliases import CRITICAL_ALWAYS_SAVE

if TYPE_CHECKING:
    import pandas as pd

logger = get_logger(__name__)

# Type alias replacing the former TimestampValidatorProtocol
TimestampValidatorProtocol = Callable[[int | None, int | str], bool]


def build_batch_data(
    ind_df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    db_cols: set[str],
    timestamp_validator: TimestampValidatorProtocol | None = None,
    seen_timestamps: set[int] | None = None,
    on_duplicate: Callable[[str, str, int], None] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Build batch rows for DB insertion and deduplicate by timestamp."""
    if timestamp_validator is None:
        from .validator import validate_timestamp

        timestamp_validator = validate_timestamp

    batch_data: list[dict[str, Any]] = []
    skipped_rows = 0
    duplicate_rows = 0
    if seen_timestamps is None:
        seen_timestamps = set()

    critical_fields = CRITICAL_ALWAYS_SAVE

    for row_tuple in ind_df.itertuples(index=True, name=None):
        try:
            idx = row_tuple[0]
            row_dict = {col: row_tuple[i + 1] for i, col in enumerate(ind_df.columns)}

            timestamp_ms = row_dict.get("timestamp")
            if timestamp_ms is None or not timestamp_validator(timestamp_ms, idx):
                skipped_rows += 1
                continue

            if timestamp_ms in seen_timestamps:
                duplicate_rows += 1
                logger.debug(
                    "Row %s: duplicate timestamp %s, skipping", idx, timestamp_ms
                )
                continue
            seen_timestamps.add(timestamp_ms)

            ts_sec = timestamp_ms // 1000
            calculated_at = datetime.datetime.utcfromtimestamp(ts_sec)

            indicator_data = {"symbol": symbol, "timeframe": timeframe, "timestamp": timestamp_ms, "calculated_at": calculated_at}
            indicators_added = 0

            for col in ind_df.columns:
                if col in ("ts", "open", "high", "low", "close", "volume"):
                    continue
                if col not in db_cols:
                    if col in critical_fields:
                        logger.warning("Column '%s' not in db_cols but is critical, skipping", col)
                    continue

                val = row_dict.get(col)
                is_critical = col in critical_fields

                if val is None:
                    if is_critical:
                        indicator_data[col] = None
                        indicators_added += 1
                    continue

                if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
                    if is_critical:
                        indicator_data[col] = None
                        indicators_added += 1
                    continue

                try:
                    float_val = float(val)
                    if np.isnan(float_val) or np.isinf(float_val):
                        if is_critical:
                            indicator_data[col] = None
                            indicators_added += 1
                        continue
                    indicator_data[col] = float_val
                    indicators_added += 1
                except (ValueError, TypeError, OverflowError):
                    if is_critical:
                        indicator_data[col] = None
                        indicators_added += 1
                    continue

            if indicators_added == 0:
                logger.debug("Row %s: inserting base fields without calculated indicators", idx)

            batch_data.append(indicator_data)

        except Exception as e:
            logger.error("Row %s: Error processing row: %s", idx if "idx" in locals() else "unknown", e, exc_info=True, extra={"row_index": str(idx) if "idx" in locals() else "unknown", "symbol": symbol, "timeframe": timeframe})
            skipped_rows += 1
            continue

    if duplicate_rows > 0 and on_duplicate:
        on_duplicate(symbol, timeframe, duplicate_rows)
        logger.warning("Detected %d duplicate timestamps in batch for %s/%s", duplicate_rows, symbol, timeframe)

    logger.info("Prepared %d records for insertion, skipped %d rows (duplicates: %d)", len(batch_data), skipped_rows, duplicate_rows)
    return batch_data, skipped_rows
