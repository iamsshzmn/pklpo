"""
Snapshot management for ML reproducibility.

This module owns snapshot persistence logic for calculation metadata.
Version hashing and tracking stay in `versioning.py`.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from src.logging import get_features_logger

logger = get_features_logger("features.snapshot_manager")

# Import models lazily to avoid circular dependencies at import time.
_CalculationMetadata = None


def _get_calculation_metadata_model():
    """Lazy import of CalculationMetadata model."""
    global _CalculationMetadata
    if _CalculationMetadata is None:
        from .models import CalculationMetadata

        _CalculationMetadata = CalculationMetadata
    return _CalculationMetadata


@dataclass
class SnapshotConfig:
    """Configuration for calculation snapshot."""

    symbols: list[str]
    timeframes: list[str]
    features: list[str]
    volatility_normalize: bool = True
    normalize_window: int = 20
    normalize_method: str = "rolling_std"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)


class SnapshotManager:
    """
    Manager for calculation snapshots to enable ML reproducibility.

    This class handles:
    - Creating new calculation snapshots
    - Updating snapshot status
    - Querying snapshots by version/date/config
    - Reproducing calculations from snapshots
    """

    def __init__(self) -> None:
        from .versioning import version_manager

        self.logger = get_features_logger("features.snapshot_manager")
        self._module_version = "1.0.0"
        self._version_manager = version_manager

    def _generate_snapshot_id(self) -> str:
        """Generate unique snapshot ID."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"snap_{timestamp}_{unique_id}"

    def _get_algorithm_version(self) -> str:
        """Get current algorithm version."""
        return self._version_manager.get_algorithm_version()

    async def create_snapshot(
        self, session, config: SnapshotConfig, snapshot_id: str | None = None
    ) -> str:
        """
        Create new calculation snapshot.

        Args:
            session: Database session
            config: Snapshot configuration
            snapshot_id: Optional custom snapshot ID

        Returns:
            Created snapshot ID
        """
        CalculationMetadata = _get_calculation_metadata_model()

        if snapshot_id is None:
            snapshot_id = self._generate_snapshot_id()

        metadata = CalculationMetadata(
            snapshot_id=snapshot_id,
            created_at=datetime.now(UTC),
            algorithm_version=self._get_algorithm_version(),
            module_version=self._module_version,
            config=config.to_json(),
            symbols=json.dumps(config.symbols),
            timeframes=json.dumps(config.timeframes),
            status="in_progress",
            rows_calculated=0,
        )

        session.add(metadata)
        await session.commit()

        self.logger.info(f"Created calculation snapshot: {snapshot_id}")
        return snapshot_id

    async def update_snapshot_progress(
        self, session, snapshot_id: str, rows_calculated: int
    ) -> None:
        """Update snapshot progress."""
        CalculationMetadata = _get_calculation_metadata_model()

        from sqlalchemy import update

        stmt = (
            update(CalculationMetadata)
            .where(CalculationMetadata.snapshot_id == snapshot_id)
            .values(rows_calculated=rows_calculated)
        )
        await session.execute(stmt)
        await session.commit()

    async def complete_snapshot(
        self, session, snapshot_id: str, rows_calculated: int, duration_seconds: float
    ) -> None:
        """Mark snapshot as completed."""
        CalculationMetadata = _get_calculation_metadata_model()

        from sqlalchemy import update

        stmt = (
            update(CalculationMetadata)
            .where(CalculationMetadata.snapshot_id == snapshot_id)
            .values(
                completed_at=datetime.now(UTC),
                status="completed",
                rows_calculated=rows_calculated,
                execution_duration_seconds=duration_seconds,
            )
        )
        await session.execute(stmt)
        await session.commit()

        self.logger.info(
            f"Completed snapshot {snapshot_id}: "
            f"{rows_calculated} rows in {duration_seconds:.2f}s"
        )

    async def fail_snapshot(
        self, session, snapshot_id: str, error_message: str
    ) -> None:
        """Mark snapshot as failed."""
        CalculationMetadata = _get_calculation_metadata_model()

        from sqlalchemy import update

        stmt = (
            update(CalculationMetadata)
            .where(CalculationMetadata.snapshot_id == snapshot_id)
            .values(
                completed_at=datetime.now(UTC),
                status="failed",
                error_message=error_message,
            )
        )
        await session.execute(stmt)
        await session.commit()

        self.logger.error(f"Snapshot {snapshot_id} failed: {error_message}")

    async def get_snapshot(self, session, snapshot_id: str) -> dict[str, Any] | None:
        """Get snapshot metadata."""
        CalculationMetadata = _get_calculation_metadata_model()

        from sqlalchemy import select

        stmt = select(CalculationMetadata).where(
            CalculationMetadata.snapshot_id == snapshot_id
        )
        result = await session.execute(stmt)
        metadata = result.scalar_one_or_none()

        if metadata is None:
            return None

        return {
            "snapshot_id": metadata.snapshot_id,
            "created_at": metadata.created_at.isoformat(),
            "completed_at": (
                metadata.completed_at.isoformat() if metadata.completed_at else None
            ),
            "algorithm_version": metadata.algorithm_version,
            "module_version": metadata.module_version,
            "config": json.loads(metadata.config),
            "symbols": json.loads(metadata.symbols) if metadata.symbols else [],
            "timeframes": (
                json.loads(metadata.timeframes) if metadata.timeframes else []
            ),
            "status": metadata.status,
            "rows_calculated": metadata.rows_calculated,
            "execution_duration_seconds": (
                float(metadata.execution_duration_seconds)
                if metadata.execution_duration_seconds
                else None
            ),
            "error_message": metadata.error_message,
        }

    async def list_snapshots(
        self,
        session,
        limit: int = 50,
        status: str | None = None,
        algorithm_version: str | None = None,
    ) -> list[dict[str, Any]]:
        """List calculation snapshots."""
        CalculationMetadata = _get_calculation_metadata_model()

        from sqlalchemy import desc, select

        stmt = (
            select(CalculationMetadata)
            .order_by(desc(CalculationMetadata.created_at))
            .limit(limit)
        )

        if status:
            stmt = stmt.where(CalculationMetadata.status == status)
        if algorithm_version:
            stmt = stmt.where(
                CalculationMetadata.algorithm_version == algorithm_version
            )

        result = await session.execute(stmt)
        snapshots = result.scalars().all()

        return [
            {
                "snapshot_id": s.snapshot_id,
                "created_at": s.created_at.isoformat(),
                "status": s.status,
                "algorithm_version": s.algorithm_version,
                "symbols": json.loads(s.symbols) if s.symbols else [],
                "timeframes": json.loads(s.timeframes) if s.timeframes else [],
                "rows_calculated": s.rows_calculated,
            }
            for s in snapshots
        ]


snapshot_manager = SnapshotManager()


async def create_calculation_snapshot(
    session,
    symbols: list[str],
    timeframes: list[str],
    features: list[str] | None = None,
    **kwargs: Any,
) -> str:
    """Create calculation snapshot (convenience function)."""
    config = SnapshotConfig(
        symbols=symbols,
        timeframes=timeframes,
        features=features or [],
        volatility_normalize=kwargs.get("volatility_normalize", True),
        normalize_window=kwargs.get("normalize_window", 20),
        normalize_method=kwargs.get("normalize_method", "rolling_std"),
    )

    return await snapshot_manager.create_snapshot(session, config)


__all__ = [
    "SnapshotConfig",
    "SnapshotManager",
    "create_calculation_snapshot",
    "snapshot_manager",
]
