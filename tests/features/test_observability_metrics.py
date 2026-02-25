from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.observability.metrics import calculate_quality_score


def test_calculate_quality_score_handles_nullable_and_infinite_values() -> None:
    df = pd.DataFrame(
        {
            "open": [1.0, 2.0, 3.0, 4.0],  # excluded column
            "feature_nullable": pd.Series([1, 2, pd.NA, 100], dtype="Float64"),
            "feature_infinite": [1.0, np.inf, 3.0, -np.inf],
            "feature_text": ["a", "b", "c", "d"],
        }
    )

    nan_ratio, outlier_ratio, quality_score = calculate_quality_score(df)

    assert isinstance(nan_ratio, (int, float, np.floating))
    assert isinstance(outlier_ratio, (int, float, np.floating))
    assert isinstance(quality_score, (int, float, np.floating))
    assert 0.0 <= float(nan_ratio) <= 1.0
    assert 0.0 <= float(outlier_ratio) <= 1.0
    assert 0.0 <= float(quality_score) <= 1.0
