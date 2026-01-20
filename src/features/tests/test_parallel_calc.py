"""
Tests for parallel calculation module.
"""

import numpy as np
import pandas as pd
import pytest

from ..parallel_calc import (
    ParallelCalculator,
    calculate_features_with_parallelism,
    calculate_multi_symbol_parallel,
    split_dataframe_for_parallel,
)


class TestParallelCalculator:
    """Tests for ParallelCalculator class."""

    @pytest.fixture()
    def sample_chunks(self):
        """Create sample data chunks for testing."""
        chunks = []
        for _i in range(3):
            df = pd.DataFrame(
                {
                    "open": np.random.random(100) * 100 + 100,
                    "high": np.random.random(100) * 100 + 110,
                    "low": np.random.random(100) * 100 + 90,
                    "close": np.random.random(100) * 100 + 100,
                    "volume": np.random.random(100) * 1000000,
                }
            )
            chunks.append(df)
        return chunks

    def test_thread_executor_initialization(self):
        """Test initializing with thread executor."""
        calc = ParallelCalculator(max_workers=4, executor_type="thread")

        assert calc.max_workers == 4
        assert calc.executor_type == "thread"

    def test_process_executor_initialization(self):
        """Test initializing with process executor."""
        calc = ParallelCalculator(max_workers=2, executor_type="process")

        assert calc.max_workers == 2
        assert calc.executor_type == "process"

    def test_process_chunks_parallel_success(self, sample_chunks):
        """Test successful parallel processing."""
        calc = ParallelCalculator(max_workers=2, executor_type="thread")

        # Simple processing function
        def add_column(df):
            df_copy = df.copy()
            df_copy["processed"] = True
            return df_copy

        results = calc.process_chunks_parallel(sample_chunks, add_column)

        assert len(results) == 3
        for result in results:
            assert "processed" in result.columns
            assert result["processed"].all()

    def test_process_chunks_parallel_with_error(self, sample_chunks):
        """Test parallel processing handles errors gracefully."""
        calc = ParallelCalculator(max_workers=2, executor_type="thread")

        call_count = 0

        def sometimes_fails(df):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValueError("Processing error")
            df_copy = df.copy()
            df_copy["processed"] = True
            return df_copy

        results = calc.process_chunks_parallel(sample_chunks, sometimes_fails)

        # Should return only successful results
        assert len(results) == 2
        for result in results:
            assert "processed" in result.columns

    def test_process_empty_chunks(self):
        """Test processing empty chunk list."""
        calc = ParallelCalculator(max_workers=2, executor_type="thread")

        results = calc.process_chunks_parallel([], lambda x: x)

        assert results == []


class TestCalculateMultiSymbolParallel:
    """Tests for calculate_multi_symbol_parallel function."""

    @pytest.fixture()
    def multi_symbol_data(self):
        """Create sample multi-symbol data."""
        symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
        data = {}

        for symbol in symbols:
            df = pd.DataFrame(
                {
                    "open": np.random.random(50) * 100 + 100,
                    "high": np.random.random(50) * 100 + 110,
                    "low": np.random.random(50) * 100 + 90,
                    "close": np.random.random(50) * 100 + 100,
                    "volume": np.random.random(50) * 1000000,
                }
            )
            data[symbol] = df

        return data

    def test_calculate_multiple_symbols(self, multi_symbol_data):
        """Test calculating features for multiple symbols."""

        # Mock function that just adds a column
        def mock_compute(df, **kwargs):
            result = df.copy()
            result["feature1"] = result["close"].rolling(10).mean()
            return result

        # Patch compute_features for this test
        import features.parallel_calc as parallel_calc

        original_compute = parallel_calc.compute_features
        parallel_calc.compute_features = mock_compute

        try:
            results = calculate_multi_symbol_parallel(multi_symbol_data, max_workers=2)

            assert len(results) == 3
            assert "BTC-USDT" in results
            assert "ETH-USDT" in results
            assert "SOL-USDT" in results

            for _symbol, df in results.items():
                assert "feature1" in df.columns

        finally:
            parallel_calc.compute_features = original_compute


class TestSplitDataframeForParallel:
    """Tests for split_dataframe_for_parallel function."""

    def test_split_into_chunks(self):
        """Test splitting DataFrame into chunks."""
        df = pd.DataFrame({"value": range(100)})

        chunks = split_dataframe_for_parallel(df, num_splits=4, overlap=0)

        assert len(chunks) == 4
        # Each chunk should have approximately 25 rows
        for chunk in chunks:
            assert len(chunk) >= 20
            assert len(chunk) <= 30

    def test_split_with_overlap(self):
        """Test splitting with overlap."""
        df = pd.DataFrame({"value": range(100)})

        chunks = split_dataframe_for_parallel(df, num_splits=4, overlap=10)

        assert len(chunks) == 4
        # Chunks should have overlap
        for i in range(len(chunks) - 1):
            # Last row of current chunk should overlap with first row of next
            last_val = chunks[i]["value"].iloc[-1]
            assert last_val >= chunks[i + 1]["value"].iloc[0]

    def test_split_small_dataframe(self):
        """Test splitting DataFrame smaller than num_splits."""
        df = pd.DataFrame({"value": range(5)})

        chunks = split_dataframe_for_parallel(df, num_splits=10, overlap=0)

        # Should return single chunk
        assert len(chunks) == 1
        assert len(chunks[0]) == 5


class TestCalculateFeaturesWithParallelism:
    """Tests for calculate_features_with_parallelism function."""

    @pytest.fixture()
    def large_dataframe(self):
        """Create large sample DataFrame."""
        return pd.DataFrame(
            {
                "open": np.random.random(400) * 100 + 100,
                "high": np.random.random(400) * 100 + 110,
                "low": np.random.random(400) * 100 + 90,
                "close": np.random.random(400) * 100 + 100,
                "volume": np.random.random(400) * 1000000,
                "ts": pd.date_range("2024-01-01", periods=400, freq="1h"),
            }
        )

    def test_parallel_calculation(self, large_dataframe):
        """Test parallel feature calculation."""

        # Mock function
        def mock_compute(df, **kwargs):
            result = df.copy()
            result["sma_20"] = result["close"].rolling(20).mean()
            return result

        import features.parallel_calc as parallel_calc

        original_compute = parallel_calc.compute_features
        parallel_calc.compute_features = mock_compute

        try:
            result = calculate_features_with_parallelism(
                large_dataframe, num_workers=2, num_chunks=4
            )

            # Should return combined result
            assert len(result) > 0
            assert "sma_20" in result.columns
            # Check no duplicates
            assert not result["ts"].duplicated().any()

        finally:
            parallel_calc.compute_features = original_compute
