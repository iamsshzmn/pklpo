"""
Memory monitoring utilities for features module.

This module provides memory tracking and logging capabilities
to monitor memory usage during feature calculation and saving.
"""

import gc
import tracemalloc
from contextlib import contextmanager
from typing import Any

import pandas as pd
import psutil  # type: ignore[import-untyped]

from src.logging import get_logger

logger = get_logger(__name__)


class MemLog:
    """Memory monitoring context manager."""

    def __init__(self, name: str = "operation"):
        self.name = name
        self.start_memory = 0
        self.peak_memory = 0
        self.start_tracemalloc = 0
        self.peak_tracemalloc = 0
        self.process = psutil.Process()

    def __enter__(self):
        # Start tracemalloc
        tracemalloc.start()

        # Get initial memory stats
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.start_tracemalloc = tracemalloc.get_traced_memory()[0] / 1024 / 1024  # MB

        logger.info(f"Memory monitoring started for {self.name}")
        logger.info(f"Initial memory: {self.start_memory:.2f} MB")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Get final memory stats
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        current_tracemalloc = tracemalloc.get_traced_memory()[0] / 1024 / 1024  # MB

        # Calculate peak memory
        self.peak_memory = max(self.start_memory, current_memory)
        self.peak_tracemalloc = max(self.start_tracemalloc, current_tracemalloc)

        # Stop tracemalloc
        tracemalloc.stop()

        # Log memory usage
        memory_delta = current_memory - self.start_memory
        logger.info(f"Memory monitoring completed for {self.name}")
        logger.info(f"Final memory: {current_memory:.2f} MB")
        logger.info(f"Memory delta: {memory_delta:+.2f} MB")
        logger.info(f"Peak memory: {self.peak_memory:.2f} MB")
        logger.info(f"Tracemalloc peak: {self.peak_tracemalloc:.2f} MB")

        # Force garbage collection
        gc.collect()

    def log_dataframe_memory(self, df: pd.DataFrame, name: str = "DataFrame"):
        """Log DataFrame memory usage."""
        if df is not None and not df.empty:
            memory_usage = df.memory_usage(deep=True).sum() / 1024 / 1024  # MB
            logger.info(f"{name} memory usage: {memory_usage:.2f} MB")
            logger.info(f"{name} shape: {df.shape}")
            logger.info(f"{name} dtypes: {df.dtypes.value_counts().to_dict()}")
        else:
            logger.info(f"{name} is empty or None")

    def get_memory_stats(self) -> dict[str, Any]:
        """Get current memory statistics."""
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        current_tracemalloc = tracemalloc.get_traced_memory()[0] / 1024 / 1024  # MB

        return {
            "current_memory_mb": current_memory,
            "current_tracemalloc_mb": current_tracemalloc,
            "peak_memory_mb": self.peak_memory,
            "peak_tracemalloc_mb": self.peak_tracemalloc,
            "memory_delta_mb": current_memory - self.start_memory,
        }


@contextmanager
def memory_monitor(name: str = "operation"):
    """Context manager for memory monitoring."""
    with MemLog(name) as mem_log:
        yield mem_log


def log_dataframe_info(
    df: pd.DataFrame, name: str = "DataFrame", log_level: int = logging.INFO
):
    """Log detailed DataFrame information."""
    if df is not None and not df.empty:
        memory_usage = df.memory_usage(deep=True).sum() / 1024 / 1024  # MB
        logger.log(log_level, f"{name} info:")
        logger.log(log_level, f"  Shape: {df.shape}")
        logger.log(log_level, f"  Memory: {memory_usage:.2f} MB")
        logger.log(log_level, f"  Columns: {len(df.columns)}")
        logger.log(log_level, f"  Dtypes: {df.dtypes.value_counts().to_dict()}")

        # Log null counts for key columns
        key_cols = ["open", "high", "low", "close", "volume", "ts"]
        available_key_cols = [col for col in key_cols if col in df.columns]
        if available_key_cols:
            null_counts = df[available_key_cols].isnull().sum()
            logger.log(log_level, f"  Null counts: {null_counts.to_dict()}")
    else:
        logger.log(log_level, f"{name} is empty or None")


def force_cleanup(*objects):
    """Force cleanup of objects and garbage collection."""
    for obj in objects:
        if obj is not None:
            del obj

    # Force garbage collection
    collected = gc.collect()
    logger.debug(f"Garbage collection freed {collected} objects")


def get_memory_usage() -> dict[str, float]:
    """Get current memory usage statistics."""
    process = psutil.Process()
    memory_info = process.memory_info()

    return {
        "rss_mb": memory_info.rss / 1024 / 1024,
        "vms_mb": memory_info.vms / 1024 / 1024,
        "percent": process.memory_percent(),
    }


if __name__ == "__main__":
    import numpy as np
    import pandas as pd

    # Test memory monitoring
    with memory_monitor("test_operation") as mem_log:
        # Create test DataFrame
        df = pd.DataFrame(
            {
                "open": np.random.randn(1000),
                "high": np.random.randn(1000),
                "low": np.random.randn(1000),
                "close": np.random.randn(1000),
                "volume": np.random.randn(1000),
            }
        )

        mem_log.log_dataframe_memory(df, "Test DataFrame")

        # Simulate some processing
        df["hlc3"] = (df["high"] + df["low"] + df["close"]) / 3
        df["sma_20"] = df["close"].rolling(20).mean()

        mem_log.log_dataframe_memory(df, "Processed DataFrame")

        # Force cleanup
        force_cleanup(df)

    print("Memory monitoring test completed")
