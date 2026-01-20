"""
Parallel calculation module for independent data chunks.

This module provides parallel processing capabilities for data chunks that
don't require overlap (e.g., different symbols or non-overlapping time periods).
"""

from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from functools import partial
from typing import Any, Literal

import pandas as pd

from .core import compute_features
from .logging_config import get_features_logger

logger = get_features_logger("features.parallel_calc")


class ParallelCalculator:
    """
    Parallel calculator for independent data chunks.

    Uses ThreadPoolExecutor for I/O-bound operations (database reads)
    and ProcessPoolExecutor for CPU-bound operations (calculations).
    """

    def __init__(
        self,
        max_workers: int = 4,
        executor_type: Literal["thread", "process"] = "thread",
    ):
        """
        Initialize parallel calculator.

        Args:
            max_workers: Maximum number of parallel workers (default: 4)
            executor_type: Type of executor - "thread" or "process"
                          "thread" is better for I/O-bound operations
                          "process" is better for CPU-bound operations
        """
        self.max_workers = max_workers
        self.executor_type = executor_type
        self.logger = get_features_logger("features.parallel_calc")

        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")

        if executor_type not in ("thread", "process"):
            raise ValueError("executor_type must be 'thread' or 'process'")

        self.logger.info(
            f"Initialized parallel calculator: {executor_type} executor "
            f"with {max_workers} workers"
        )

    def process_chunks_parallel(
        self,
        chunks: list[pd.DataFrame],
        process_func: Callable[[pd.DataFrame], pd.DataFrame],
        **kwargs: Any,
    ) -> list[pd.DataFrame]:
        """
        Process multiple independent chunks in parallel.

        Args:
            chunks: List of DataFrames to process
            process_func: Function to apply to each chunk
            **kwargs: Additional arguments to pass to process_func

        Returns:
            List of processed DataFrames in the same order as input
        """
        if not chunks:
            self.logger.warning("No chunks to process")
            return []

        self.logger.info(f"Processing {len(chunks)} chunks in parallel")

        # Choose executor based on type
        executor_class = (
            ThreadPoolExecutor
            if self.executor_type == "thread"
            else ProcessPoolExecutor
        )

        results: list[pd.DataFrame | None] = [None] * len(chunks)

        with executor_class(max_workers=self.max_workers) as executor:
            # Submit all chunks
            future_to_index = {
                executor.submit(process_func, chunk, **kwargs): i
                for i, chunk in enumerate(chunks)
            }

            # Collect results
            completed_count = 0
            for future in as_completed(future_to_index):
                index = future_to_index[future]

                try:
                    result = future.result()
                    results[index] = result
                    completed_count += 1

                    self.logger.debug(
                        f"Completed chunk {index + 1}/{len(chunks)} "
                        f"({completed_count}/{len(chunks)} total)"
                    )

                except Exception as e:
                    self.logger.error(
                        f"Error processing chunk {index}: {e}", exc_info=True
                    )
                    # Store None for failed chunks
                    results[index] = None

        # Filter out failed chunks
        successful_results = [r for r in results if r is not None]

        self.logger.info(
            f"Parallel processing complete: {len(successful_results)}/{len(chunks)} successful"
        )

        return successful_results

    def calculate_features_parallel(
        self,
        chunks: list[pd.DataFrame],
        available_indicators: set[str] | None = None,
        volatility_normalize: bool = True,
        **kwargs: Any,
    ) -> list[pd.DataFrame]:
        """
        Calculate features for multiple chunks in parallel.

        Args:
            chunks: List of OHLCV DataFrames
            available_indicators: Set of indicators to calculate
            volatility_normalize: Enable volatility normalization
            **kwargs: Additional arguments for compute_features

        Returns:
            List of DataFrames with calculated features
        """
        # Create partial function with fixed arguments
        calc_func = partial(
            compute_features,
            available=available_indicators,
            volatility_normalize=volatility_normalize,
            **kwargs,
        )

        self.logger.info(
            f"Starting parallel feature calculation for {len(chunks)} chunks"
        )

        return self.process_chunks_parallel(chunks, calc_func)


def calculate_multi_symbol_parallel(
    symbol_data: dict[str, pd.DataFrame],
    max_workers: int = 4,
    available_indicators: set[str] | None = None,
    **kwargs: Any,
) -> dict[str, pd.DataFrame]:
    """
    Calculate features for multiple symbols in parallel.

    Each symbol's data is processed independently, enabling parallel execution.

    Args:
        symbol_data: Dictionary mapping symbol names to OHLCV DataFrames
        max_workers: Maximum number of parallel workers
        available_indicators: Set of indicators to calculate
        **kwargs: Additional arguments for compute_features

    Returns:
        Dictionary mapping symbol names to DataFrames with features
    """
    calculator = ParallelCalculator(max_workers=max_workers, executor_type="thread")

    # Convert dict to lists
    symbols = list(symbol_data.keys())
    chunks = [symbol_data[symbol] for symbol in symbols]

    logger.info(f"Calculating features for {len(symbols)} symbols in parallel")

    # Process in parallel
    results = calculator.calculate_features_parallel(
        chunks, available_indicators=available_indicators, **kwargs
    )

    # Reconstruct dictionary
    result_dict = {
        symbol: result
        for symbol, result in zip(symbols, results, strict=False)
        if result is not None
    }

    logger.info(
        f"Completed parallel calculation: {len(result_dict)}/{len(symbols)} symbols successful"
    )

    return result_dict


def split_dataframe_for_parallel(
    df: pd.DataFrame,
    num_splits: int = 4,
    overlap: int = 0,
) -> list[pd.DataFrame]:
    """
    Split a DataFrame into chunks for parallel processing.

    Args:
        df: DataFrame to split
        num_splits: Number of chunks to create
        overlap: Number of rows to overlap between chunks (for indicators requiring lookback)

    Returns:
        List of DataFrame chunks
    """
    if len(df) < num_splits:
        logger.warning(
            f"DataFrame too small ({len(df)} rows) for {num_splits} splits. "
            f"Returning single chunk."
        )
        return [df]

    chunk_size = len(df) // num_splits
    chunks = []

    for i in range(num_splits):
        start_idx = max(0, i * chunk_size - overlap)
        end_idx = min(len(df), (i + 1) * chunk_size + overlap)

        chunk = df.iloc[start_idx:end_idx].copy()
        chunks.append(chunk)

        logger.debug(
            f"Created chunk {i + 1}/{num_splits}: "
            f"rows {start_idx}-{end_idx} ({len(chunk)} total)"
        )

    return chunks


# Convenience function
def calculate_features_with_parallelism(
    df: pd.DataFrame,
    num_workers: int = 4,
    num_chunks: int = 4,
    available_indicators: set[str] | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """
    Calculate features with automatic parallelization.

    Splits the DataFrame into chunks and processes them in parallel.
    Useful for very large datasets.

    Args:
        df: OHLCV DataFrame
        num_workers: Number of parallel workers
        num_chunks: Number of chunks to split data into
        available_indicators: Set of indicators to calculate
        **kwargs: Additional arguments for compute_features

    Returns:
        DataFrame with calculated features
    """
    logger.info(
        f"Starting parallel feature calculation: "
        f"{len(df)} rows → {num_chunks} chunks → {num_workers} workers"
    )

    # Split data
    chunks = split_dataframe_for_parallel(df, num_splits=num_chunks, overlap=100)

    # Calculate in parallel
    calculator = ParallelCalculator(max_workers=num_workers, executor_type="thread")
    results = calculator.calculate_features_parallel(
        chunks, available_indicators=available_indicators, **kwargs
    )

    # Combine results
    if not results:
        logger.error("No successful results from parallel calculation")
        return pd.DataFrame()

    combined_df = pd.concat(results, ignore_index=True)

    # Remove duplicates from overlaps (keep first occurrence)
    if "ts" in combined_df.columns:
        combined_df = combined_df.drop_duplicates(subset=["ts"], keep="first")

    logger.info(f"Parallel calculation complete: {len(combined_df)} rows in result")

    return combined_df
