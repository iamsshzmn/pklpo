"""
Internal white-box tests for application/calc.py dependency injection.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest


def _make_ohlcv_df(n: int = 50) -> pd.DataFrame:
    """Minimal OHLCV DataFrame for tests."""
    import numpy as np

    return pd.DataFrame(
        {
            "ts": range(n),
            "open": np.ones(n),
            "high": np.ones(n) * 1.01,
            "low": np.ones(n) * 0.99,
            "close": np.ones(n),
            "volume": np.ones(n) * 1000,
        }
    )


def _make_fake_calculator(result_df: pd.DataFrame | None = None):
    """Fake FeatureCalculator for tests."""
    mock = MagicMock()
    mock.calculate.return_value = (
        result_df if result_df is not None else _make_ohlcv_df()
    )
    return mock


class TestProcessChunksRequiresCalculator:
    def test_uses_deprecated_default_calculator_without_explicit_dependency(self):
        from src.features.application.calc import process_chunks

        df = _make_ohlcv_df()
        reader = iter([df])

        with pytest.warns(
            DeprecationWarning,
            match="without an explicit calculator is deprecated",
        ):
            with pytest.raises(Exception):
                list(process_chunks(reader, symbol="BTC", timeframe="1m"))

    def test_works_with_injected_calculator(self):
        from src.features.application.calc import process_chunks

        df = _make_ohlcv_df(100)
        result_df = df.copy()
        calculator = _make_fake_calculator(result_df)
        reader = iter([df])

        chunks = list(
            process_chunks(
                reader,
                symbol="BTC",
                timeframe="1m",
                calculator=calculator,
            )
        )

        calculator.calculate.assert_called_once()
        assert len(chunks) == 1


class TestComputeAndDumpParquetRequiresCalculator:
    def test_uses_deprecated_default_calculator_without_explicit_dependency(
        self,
        tmp_path,
    ):
        from src.features.application.calc import compute_and_dump_parquet

        df = _make_ohlcv_df()
        output = str(tmp_path / "out.parquet")

        with pytest.warns(
            DeprecationWarning,
            match="without an explicit calculator is deprecated",
        ):
            with pytest.raises(Exception):
                compute_and_dump_parquet(
                    df_ohlcv=df,
                    symbol="BTC",
                    timeframe="1m",
                    output_path=output,
                )

    def test_works_with_injected_calculator(self, tmp_path):
        """Calculator should be called even if parquet engine is unavailable."""
        from src.features.application.calc import compute_and_dump_parquet

        df = _make_ohlcv_df(50)
        result_df = df.copy()
        result_df["ts"] = range(50)
        calculator = _make_fake_calculator(result_df)
        output = str(tmp_path / "out.parquet")

        try:
            compute_and_dump_parquet(
                df_ohlcv=df,
                symbol="BTC",
                timeframe="1m",
                output_path=output,
                calculator=calculator,
            )
        except ImportError:
            pass
        except Exception:
            pass

        calculator.calculate.assert_called_once()


class TestCalcModuleNoDirectServiceImport:
    def test_calc_module_does_not_import_get_default_service(self):
        """calc.py should not import get_default_service at module scope."""
        import importlib.util
        import sys

        mod_name = "src.features.application.calc"
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
        else:
            spec = importlib.util.find_spec(mod_name)
            mod = importlib.util.module_from_spec(spec)

        assert not hasattr(mod, "get_default_service"), (
            "calc.py should not import get_default_service at module scope"
        )


class TestCalcCliExamplePath:
    def test_main_block_uses_create_feature_service(self):
        """CLI/example path should build calculator through factory."""
        from pathlib import Path

        source = Path("D:/projects/pklpo/src/features/application/calc.py").read_text(
            encoding="utf-8"
        )

        assert "from .feature_service import create_feature_service" in source
        assert "calculator=create_feature_service()" in source
