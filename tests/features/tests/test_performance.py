"""
РўРµСЃС‚С‹ РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚Рё РґР»СЏ РјРѕРґСѓР»СЏ features.
"""

import time

import numpy as np
import pandas as pd
import pytest

from src.features.core import compute_features
from src.features.indicator_groups.data_cleaner import (
    clean_close_data,
    clean_ohlcv_data,
)
from src.features.validation.feature_validator import (
    validate_specs_registry_consistency,
)


class TestPerformance:
    """РўРµСЃС‚С‹ РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚Рё РґР»СЏ РёСЃРїСЂР°РІР»РµРЅРёР№ РІ features/"""

    @staticmethod
    def _build_valid_ohlcv_df(n_rows: int) -> pd.DataFrame:
        open_ = np.random.uniform(100, 200, n_rows)
        close = open_ + np.random.uniform(-5, 5, n_rows)
        high = np.maximum(open_, close) + np.random.uniform(0, 3, n_rows)
        low = np.minimum(open_, close) - np.random.uniform(0, 3, n_rows)
        ts_start_ms = 1_700_000_000_000
        ts_step_ms = 60_000

        return pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": np.random.uniform(1000, 10000, n_rows),
                "ts": [ts_start_ms + i * ts_step_ms for i in range(n_rows)],
            }
        )

    def test_dataframe_creation_performance(self):
        """РўРµСЃС‚ РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚Рё СЃРѕР·РґР°РЅРёСЏ DataFrame Р±РµР· С„СЂР°РіРјРµРЅС‚Р°С†РёРё"""
        n_rows = 1000
        df = self._build_valid_ohlcv_df(n_rows)

        available = {"sma_20", "ema_12", "rsi_14", "macd", "atr_14", "obv"}

        start_time = time.time()
        result = compute_features(df, available=available, volatility_normalize=False)
        end_time = time.time()

        execution_time = end_time - start_time

        assert execution_time < 2.0, (
            f"Execution took {execution_time:.2f}s, expected < 2.0s"
        )

        expected_columns = available | {"ts"}
        assert set(result.columns) >= expected_columns, (
            f"Missing columns: {expected_columns - set(result.columns)}"
        )

        assert len(result) == n_rows, f"Expected {n_rows} rows, got {len(result)}"

    def test_data_cleaner_performance(self):
        """РўРµСЃС‚ РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚Рё РѕС‡РёСЃС‚РєРё РґР°РЅРЅС‹С…"""
        n_rows = 500
        df = pd.DataFrame(
            {
                "open": [100, 101, np.nan, 103, float("inf"), 105] * (n_rows // 6),
                "high": [101, 102, 103, np.nan, 105, float("-inf")] * (n_rows // 6),
                "low": [99, 100, 101, 102, 103, 104] * (n_rows // 6),
                "close": [100.5, 101.5, 102.5, 103.5, 104.5, 105.5] * (n_rows // 6),
            }
        )

        start_time = time.time()
        open_clean, high_clean, low_clean, close_clean, has_sufficient = (
            clean_ohlcv_data(df, min_length=10)
        )
        end_time = time.time()

        execution_time = end_time - start_time

        assert execution_time < 0.1, (
            f"Data cleaning took {execution_time:.3f}s, expected < 0.1s"
        )

        assert not open_clean.isna().any(), (
            "Open series should not contain NaN after cleaning"
        )
        assert not high_clean.isna().any(), (
            "High series should not contain NaN after cleaning"
        )
        assert not low_clean.isna().any(), (
            "Low series should not contain NaN after cleaning"
        )
        assert not close_clean.isna().any(), (
            "Close series should not contain NaN after cleaning"
        )

    def test_close_data_cleaning_performance(self):
        """РўРµСЃС‚ РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚Рё РѕС‡РёСЃС‚РєРё С‚РѕР»СЊРєРѕ close РґР°РЅРЅС‹С…"""
        n_rows = 1000
        df = pd.DataFrame(
            {"close": [100, 101, np.nan, 103, float("inf"), 105] * (n_rows // 6)}
        )

        start_time = time.time()
        close_clean, has_sufficient = clean_close_data(df, min_length=50)
        end_time = time.time()

        execution_time = end_time - start_time

        assert execution_time < 0.05, (
            f"Close data cleaning took {execution_time:.3f}s, expected < 0.05s"
        )

        assert not close_clean.isna().any(), (
            "Close series should not contain NaN after cleaning"
        )
        assert has_sufficient, "Should have sufficient data after cleaning"

    def test_specs_registry_validation_performance(self):
        """РўРµСЃС‚ РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚Рё РІР°Р»РёРґР°С†РёРё СЃРѕРѕС‚РІРµС‚СЃС‚РІРёСЏ specs Рё registry"""
        start_time = time.time()
        is_consistent = validate_specs_registry_consistency()
        end_time = time.time()

        execution_time = end_time - start_time

        assert execution_time < 0.5, (
            f"Validation took {execution_time:.3f}s, expected < 0.5s"
        )

        assert is_consistent, "Specs and registry should be consistent"

    def test_large_dataset_performance(self):
        """РўРµСЃС‚ РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚Рё РЅР° Р±РѕР»СЊС€РѕРј РЅР°Р±РѕСЂРµ РґР°РЅРЅС‹С…"""
        n_rows = 10000
        df = self._build_valid_ohlcv_df(n_rows)

        available = {
            "sma_20",
            "sma_50",
            "sma_200",
            "ema_8",
            "ema_12",
            "ema_21",
            "ema_26",
            "ema_50",
            "ema_200",
            "rsi_14",
            "macd",
            "macd_signal",
            "macd_histogram",
            "atr_14",
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "obv",
            "cmf",
            "vwap",
        }

        start_time = time.time()
        result = compute_features(df, available=available, volatility_normalize=False)
        end_time = time.time()

        execution_time = end_time - start_time

        assert execution_time < 10.0, (
            f"Large dataset processing took {execution_time:.2f}s, expected < 10.0s"
        )

        assert len(result) == n_rows, f"Expected {n_rows} rows, got {len(result)}"
        assert len(result.columns) >= len(available), (
            f"Expected at least {len(available)} columns, got {len(result.columns)}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
