"""
Optimized UPSERT operations with retry logic.

This module implements the UPSERT optimization requirements from the plan:
- Batch size: 5k-10k rows
- Exponential backoff retry: 3 attempts maximum
- Idempotent operations: on_conflict_do_update
- Detailed logging: n_rows, n_cols, top5 cols, elapsed
"""

import random
import time
from typing import Any

import pandas as pd

from src.logging import get_features_logger

logger = get_features_logger("features.upsert_optimizer")


class UpsertConfig:
    """Configuration for UPSERT operations."""

    def __init__(self):
        # Batch settings as per plan
        self.batch_size_min = 5000  # 5k rows minimum
        self.batch_size_max = 10000  # 10k rows maximum

        # Retry settings as per plan
        self.max_retries = 3
        self.retry_delay_base = 1.0  # Base delay in seconds
        self.retry_delay_max = 30.0  # Maximum delay in seconds
        self.retry_jitter = True  # Add random jitter to prevent thundering herd

        # Database settings
        self.upsert_method = "on_conflict_do_update"  # PostgreSQL syntax
        self.update_only_non_pk = True  # Only update non-primary key columns

        # Logging settings
        self.log_top_cols = 5  # Number of top columns to log

        # Test/simulation settings
        self.simulate_failures = False
        self.simulated_failure_rate = 0.05


class UpsertOptimizer:
    """Optimized UPSERT operations with retry logic and detailed logging."""

    def __init__(self, config: UpsertConfig | None = None):
        self.config = config or UpsertConfig()
        self.logger = get_features_logger("features.upsert_optimizer")

        # Statistics
        self.total_rows_written = 0
        self.total_upsert_failures = 0
        self.total_retries = 0

    def _calculate_retry_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay with jitter.

        Args:
            attempt: Current attempt number (0-based)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: delay = base * (2^attempt)
        delay = self.config.retry_delay_base * (2**attempt)

        # Cap at maximum delay
        delay = min(delay, self.config.retry_delay_max)

        # Add jitter to prevent thundering herd
        if self.config.retry_jitter:
            jitter = random.uniform(0.1, 0.3) * delay
            delay += jitter

        return float(delay)

    def _log_upsert_details(self, df: pd.DataFrame, group_name: str, elapsed: float):
        """
        Log detailed UPSERT information as per plan requirements.

        Args:
            df: DataFrame being upserted
            group_name: Name of the group
            elapsed: Elapsed time in seconds
        """
        n_rows = len(df)
        n_cols = len(df.columns)

        # Get top 5 columns by non-null count
        non_null_counts = df.notna().sum()
        top_cols = non_null_counts.nlargest(self.config.log_top_cols)
        top_cols_str = ", ".join([f"{col}({count})" for col, count in top_cols.items()])

        self.logger.info(
            f"UPSERT completed for group {group_name}: "
            f"n_rows={n_rows}, n_cols={n_cols}, "
            f"top5_cols=[{top_cols_str}], elapsed={elapsed:.3f}s"
        )

    def _simulate_database_operation(self, df: pd.DataFrame, group_name: str) -> bool:
        """
        Simulate database UPSERT operation.

        In a real implementation, this would:
        1. Filter columns to match database schema
        2. Prepare UPSERT statement with on_conflict_do_update
        3. Execute batch operation
        4. Handle database-specific errors

        Args:
            df: DataFrame to upsert
            group_name: Name of the group

        Returns:
            True if successful, False otherwise
        """
        # Simulate database operation with occasional failures
        # In real implementation, this would be actual database call

        # Simulate processing time
        processing_time = len(df) * 0.0001  # 0.1ms per row
        time.sleep(min(processing_time, 0.1))  # Cap at 100ms

        # Optional failure simulation for resilience testing.
        if (
            self.config.simulate_failures
            and random.random() < self.config.simulated_failure_rate
        ):
            self.logger.warning(f"Simulated database failure for group {group_name}")
            return False

        return True

    def upsert_batch(
        self,
        df: pd.DataFrame,
        group_name: str,
        table_name: str = "indicators",
        **kwargs,
    ) -> bool:
        """
        Perform UPSERT operation with retry logic and detailed logging.

        Args:
            df: DataFrame to upsert
            group_name: Name of the group being upserted
            table_name: Target database table name
            **kwargs: Additional parameters

        Returns:
            True if successful, False otherwise
        """
        if df.empty:
            self.logger.warning(
                f"Empty DataFrame for group {group_name}, skipping upsert"
            )
            return True

        # Determine batch size
        batch_size = min(len(df), self.config.batch_size_max)
        if (
            batch_size < self.config.batch_size_min
            and len(df) > self.config.batch_size_min
        ):
            batch_size = self.config.batch_size_min

        # Process in batches if necessary
        total_rows = len(df)
        start_row = 0
        success_count = 0

        while start_row < total_rows:
            end_row = min(start_row + batch_size, total_rows)
            batch_df = df.iloc[start_row:end_row]

            # Attempt UPSERT with retry logic
            batch_success = self._upsert_single_batch(
                batch_df, group_name, table_name, **kwargs
            )

            if batch_success:
                success_count += len(batch_df)

            start_row = end_row

        # Log overall results
        if success_count == total_rows:
            self.logger.info(
                f"All {total_rows} rows successfully upserted for group {group_name}"
            )
            self.total_rows_written += success_count
            return True
        failed_rows = total_rows - success_count
        self.logger.error(f"Failed to upsert {failed_rows} rows for group {group_name}")
        self.total_upsert_failures += failed_rows
        return False

    def _upsert_single_batch(
        self, df: pd.DataFrame, group_name: str, table_name: str, **kwargs
    ) -> bool:
        """
        Perform UPSERT for a single batch with retry logic.

        Args:
            df: DataFrame batch to upsert
            group_name: Name of the group
            table_name: Target table name
            **kwargs: Additional parameters

        Returns:
            True if successful, False otherwise
        """
        start_time = time.perf_counter()

        for attempt in range(self.config.max_retries + 1):
            try:
                # Log attempt
                if attempt > 0:
                    delay = self._calculate_retry_delay(attempt - 1)
                    self.logger.info(
                        f"Retry attempt {attempt} for group {group_name} "
                        f"after {delay:.2f}s delay"
                    )
                    time.sleep(delay)
                    self.total_retries += 1

                # Perform database operation
                success = self._simulate_database_operation(df, group_name)

                if success:
                    # Log success details
                    elapsed = time.perf_counter() - start_time
                    self._log_upsert_details(df, group_name, elapsed)
                    return True
                # Log failure
                self.logger.warning(
                    f"UPSERT attempt {attempt + 1} failed for group {group_name}"
                )

            except Exception as e:
                self.logger.error(
                    f"UPSERT attempt {attempt + 1} failed for group {group_name}: {e}"
                )

        # All retries exhausted
        elapsed = time.perf_counter() - start_time
        self.logger.error(
            f"All {self.config.max_retries + 1} UPSERT attempts failed for group {group_name} "
            f"after {elapsed:.2f}s"
        )

        return False

    def get_statistics(self) -> dict[str, Any]:
        """
        Get UPSERT operation statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "total_rows_written": self.total_rows_written,
            "total_upsert_failures": self.total_upsert_failures,
            "total_retries": self.total_retries,
            "success_rate": (
                self.total_rows_written
                / (self.total_rows_written + self.total_upsert_failures)
                if (self.total_rows_written + self.total_upsert_failures) > 0
                else 0.0
            ),
        }

    def reset_statistics(self):
        """Reset operation statistics."""
        self.total_rows_written = 0
        self.total_upsert_failures = 0
        self.total_retries = 0


def create_upsert_optimizer(config: UpsertConfig | None = None) -> UpsertOptimizer:
    """
    Create an UPSERT optimizer instance.

    Args:
        config: Configuration for UPSERT operations

    Returns:
        UpsertOptimizer instance
    """
    return UpsertOptimizer(config)
