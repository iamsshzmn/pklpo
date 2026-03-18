"""Infrastructure adapters for platform context."""

from .postgres_indicators_partition_maintenance import (
    PostgresIndicatorsPartitionMaintenanceAdapter,
)

__all__ = ["PostgresIndicatorsPartitionMaintenanceAdapter"]
