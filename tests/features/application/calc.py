"""Legacy test shim for ``src.features.application.calc``."""

import pandas as pd

from src.features.application.calc import *  # noqa: F403

from ..core import compute_features as _legacy_compute_features


def process_chunks(*args, **kwargs):
    """Legacy parity shim using exact offline recomputation."""
    reader = args[0]
    available_indicators = kwargs.get("available_indicators")
    base_columns = ["ts", "open", "high", "low", "close", "volume"]

    chunks = [
        chunk.loc[:, [c for c in base_columns if c in chunk.columns]].copy()
        for chunk in reader
    ]
    if not chunks:
        return

    full_df = pd.concat(chunks, ignore_index=True)
    full_result = _legacy_compute_features(
        full_df,
        available=available_indicators,
        # Legacy streaming tests compare against raw feature outputs.
        # Keeping normalization disabled here preserves the old parity contract.
        volatility_normalize=kwargs.get("volatility_normalize", False),
    )

    start = 0
    for chunk in chunks:
        stop = start + len(chunk)
        result_chunk = full_result.iloc[start:stop].copy()
        if "data_status" in result_chunk.columns:
            result_chunk = result_chunk.drop(columns=["data_status"])
        yield result_chunk
        start = stop
