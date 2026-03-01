from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    import pandas as pd


def validate_input_schema(
    df: pd.DataFrame,
    required_cols: Iterable[str] | None = None,
    ts_col: str = "ts",
) -> pd.DataFrame:
    missing = []
    if required_cols:
        missing.extend([c for c in required_cols if c not in df.columns])
    if ts_col and ts_col not in df.columns:
        missing.append(ts_col)
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    return df
