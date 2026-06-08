from __future__ import annotations

import pandas as pd

from src.features.validation.gate_validator import validate_data_gate


def test_gate_validator_rejects_indicator_when_rows_are_below_required_lookback() -> None:
    df = pd.DataFrame(
        {
            "timestamp": range(20),
            "open": [1.0] * 20,
            "high": [2.0] * 20,
            "low": [0.5] * 20,
            "close": [1.5] * 20,
            "volume": [10.0] * 20,
            "ema_200": [1.5] * 20,
        }
    )

    valid, result = validate_data_gate(df)

    assert valid is False
    assert any(
        "ema_200 requires at least 200 OHLCV rows" in error
        for error in result["errors"]
    )
