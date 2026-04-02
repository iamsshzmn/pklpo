"""
Version management for features module.

This module provides centralized version management for schema versions,
algorithm versions, and parameter hashes to ensure consistency across
CLI and infrastructure components.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from src.logging import get_features_logger

logger = get_features_logger("features.versioning")


@dataclass
class VersionInfo:
    """Version information container."""

    schema_version: str
    algo_version: str
    params_hash: str
    created_at: str
    features_count: int
    phase2_compliant: bool


class FeaturesVersionManager:
    """
    Centralized version management for features module.

    Manages schema versions, algorithm versions, and parameter hashes
    to ensure consistency across CLI and infrastructure components.
    """

    def __init__(self):
        self.logger = get_features_logger("features.versioning")
        self._version_cache: VersionInfo | None = None

    def get_schema_version(self) -> str:
        """
        Get current schema version.

        Returns:
            Schema version string
        """
        # Schema version is based on the structure of FEATURE_SPECS
        from ..specs import FEATURE_SPECS

        # Create a hash of the feature specs structure
        specs_data = []
        for spec in FEATURE_SPECS.values():
            if hasattr(spec, "name"):
                specs_data.append(
                    {
                        "name": spec.name,
                        "type": getattr(spec, "type", "unknown"),
                        "params": getattr(spec, "params", {}),
                    }
                )
            elif isinstance(spec, str):
                specs_data.append({"name": spec, "type": "string"})

        # Create deterministic hash
        specs_json = json.dumps(specs_data, sort_keys=True)
        schema_hash = hashlib.sha256(specs_json.encode()).hexdigest()[:8]

        return f"schema_v{schema_hash}"

    def get_algorithm_version(self) -> str:
        """
        Get current algorithm version.

        Returns:
            Algorithm version string
        """
        # Algorithm version is based on the core calculation logic
        from ..core import compute_features
        from ..schema.name_aliases import normalize_name
        from ..utils import volatility_normalize_features

        # Create hash of key algorithm components
        volatility_func_name = (
            volatility_normalize_features.__name__
            if volatility_normalize_features is not None
            else "volatility_normalize_features"
        )
        algo_components = [
            compute_features.__name__,
            volatility_func_name,
            normalize_name.__name__,
            "pandas_ta_integration",
            "time_normalization",
            "feature_validation",
        ]

        algo_string = "|".join(algo_components)
        algo_hash = hashlib.sha256(algo_string.encode()).hexdigest()[:8]

        return f"algo_v{algo_hash}"

    def get_params_hash(self, **kwargs) -> str:
        """
        Get hash of current parameters.

        Args:
            **kwargs: Parameters to hash

        Returns:
            Parameters hash string
        """
        # Default parameters
        default_params = {
            "volatility_normalize": True,
            "normalize_window": 20,
            "normalize_method": "rolling_std",
        }

        # Merge with provided parameters
        params = {**default_params, **kwargs}

        # Create deterministic hash
        params_json = json.dumps(params, sort_keys=True)
        params_hash = hashlib.sha256(params_json.encode()).hexdigest()[:8]

        return f"params_{params_hash}"

    def get_version_info(self, **kwargs) -> VersionInfo:
        """
        Get complete version information.

        Args:
            **kwargs: Parameters for params_hash calculation

        Returns:
            VersionInfo object
        """
        if self._version_cache is None:
            from ..specs import FEATURE_SPECS, PHASE_2_REQUIRED_FEATURES

            # Count features
            features_count = len(FEATURE_SPECS)

            # Check Phase 2 compliance
            required_features = set(PHASE_2_REQUIRED_FEATURES)
            spec_names = set()
            for spec in FEATURE_SPECS.values():
                if hasattr(spec, "name"):
                    spec_names.add(spec.name)
                elif isinstance(spec, str):
                    spec_names.add(spec)

            phase2_compliant = len(required_features - spec_names) == 0

            self._version_cache = VersionInfo(
                schema_version=self.get_schema_version(),
                algo_version=self.get_algorithm_version(),
                params_hash=self.get_params_hash(**kwargs),
                created_at=datetime.now(UTC).isoformat(),
                features_count=features_count,
                phase2_compliant=phase2_compliant,
            )

            self.logger.info(
                "Version info generated",
                schema_version=self._version_cache.schema_version,
                algo_version=self._version_cache.algo_version,
                features_count=features_count,
                phase2_compliant=phase2_compliant,
            )

        return self._version_cache

    def clear_cache(self):
        """Clear version cache to force regeneration."""
        self._version_cache = None
        self.logger.debug("Version cache cleared")

    def export_version_info(self, filepath: str, **kwargs):
        """
        Export version information to file.

        Args:
            filepath: Path to export file
            **kwargs: Parameters for version calculation
        """
        version_info = self.get_version_info(**kwargs)

        with open(filepath, "w") as f:
            json.dump(asdict(version_info), f, indent=2)

        self.logger.info(f"Version info exported to {filepath}")

    def validate_version_consistency(self, expected_version: str | None = None) -> bool:
        """
        Validate version consistency.

        Args:
            expected_version: Expected version to validate against

        Returns:
            True if version is consistent
        """
        current_version = self.get_schema_version()

        if expected_version and current_version != expected_version:
            self.logger.warning(
                "Version mismatch detected",
                expected=expected_version,
                current=current_version,
            )
            return False

        self.logger.debug("Version consistency validated version=%s", current_version)
        return True

    def get_version_summary(self, **kwargs) -> dict[str, Any]:
        """
        Get version summary for logging and monitoring.

        Args:
            **kwargs: Parameters for version calculation

        Returns:
            Version summary dictionary
        """
        version_info = self.get_version_info(**kwargs)

        return {
            "schema_version": version_info.schema_version,
            "algo_version": version_info.algo_version,
            "params_hash": version_info.params_hash,
            "features_count": version_info.features_count,
            "phase2_compliant": version_info.phase2_compliant,
            "created_at": version_info.created_at,
        }


class VersionTracker:
    """
    Track version changes and migrations.
    """

    def __init__(self):
        self.logger = get_features_logger("features.versioning.tracker")
        self.version_history: list[dict[str, Any]] = []

    def track_version_change(
        self,
        old_version: str,
        new_version: str,
        change_type: str,
        details: dict[str, Any] | None = None,
    ):
        """
        Track a version change.

        Args:
            old_version: Previous version
            new_version: New version
            change_type: Type of change (schema, algo, params)
            details: Additional details about the change
        """
        change_record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "old_version": old_version,
            "new_version": new_version,
            "change_type": change_type,
            "details": details or {},
        }

        self.version_history.append(change_record)

        self.logger.info(
            "Version change tracked",
            change_type=change_type,
            old_version=old_version,
            new_version=new_version,
        )

    def get_migration_plan(self, from_version: str, to_version: str) -> dict[str, Any]:
        """
        Get migration plan between versions.

        Args:
            from_version: Source version
            to_version: Target version

        Returns:
            Migration plan dictionary
        """
        # This would be expanded based on actual version differences
        migration_plan: dict[str, Any] = {
            "from_version": from_version,
            "to_version": to_version,
            "steps": [],
            "rollback_steps": [],
            "estimated_duration": "unknown",
            "risk_level": "low",
        }

        # Add specific migration steps based on version differences
        if "schema" in from_version and "schema" in to_version:
            migration_plan["steps"].append("Update feature specifications")
            migration_plan["steps"].append("Validate data consistency")

        if "algo" in from_version and "algo" in to_version:
            migration_plan["steps"].append("Update calculation algorithms")
            migration_plan["steps"].append("Recalculate affected features")

        self.logger.info(
            "Migration plan generated",
            from_version=from_version,
            to_version=to_version,
            steps_count=len(migration_plan["steps"]),
        )

        return migration_plan


# Global version manager instance
version_manager = FeaturesVersionManager()
version_tracker = VersionTracker()


def get_current_version(**kwargs) -> VersionInfo:
    """
    Get current version information.

    Args:
        **kwargs: Parameters for version calculation

    Returns:
        Current version information
    """
    return version_manager.get_version_info(**kwargs)


def track_version_change(
    old_version: str,
    new_version: str,
    change_type: str,
    details: dict[str, Any] | None = None,
):
    """
    Track a version change.

    Args:
        old_version: Previous version
        new_version: New version
        change_type: Type of change
        details: Additional details
    """
    version_tracker.track_version_change(old_version, new_version, change_type, details)


def export_version_info(filepath: str, **kwargs):
    """
    Export version information to file.

    Args:
        filepath: Path to export file
        **kwargs: Parameters for version calculation
    """
    version_manager.export_version_info(filepath, **kwargs)


# ===============================================================================
# FEAT-001: Snapshot Management for ML Reproducibility
# ===============================================================================

import uuid

# Import models (lazy to avoid circular dependencies)
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

    Usage:
        manager = SnapshotManager()
        snapshot_id = await manager.create_snapshot(session, config)
        # ... perform calculations ...
        await manager.complete_snapshot(session, snapshot_id, rows=1000)
    """

    def __init__(self):
        self.logger = get_features_logger("features.snapshot_manager")
        self._module_version = "1.0.0"  # Features module version

    def _generate_snapshot_id(self) -> str:
        """Generate unique snapshot ID."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"snap_{timestamp}_{unique_id}"

    def _get_algorithm_version(self) -> str:
        """Get current algorithm version."""
        # Use the version manager's algorithm version
        return version_manager.get_algorithm_version()

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

        # Create metadata record
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
    ):
        """
        Update snapshot progress.

        Args:
            session: Database session
            snapshot_id: Snapshot identifier
            rows_calculated: Number of rows calculated so far
        """
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
    ):
        """
        Mark snapshot as completed.

        Args:
            session: Database session
            snapshot_id: Snapshot identifier
            rows_calculated: Total rows calculated
            duration_seconds: Execution duration in seconds
        """
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

    async def fail_snapshot(self, session, snapshot_id: str, error_message: str):
        """
        Mark snapshot as failed.

        Args:
            session: Database session
            snapshot_id: Snapshot identifier
            error_message: Error description
        """
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
        """
        Get snapshot metadata.

        Args:
            session: Database session
            snapshot_id: Snapshot identifier

        Returns:
            Snapshot metadata dictionary or None
        """
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
        """
        List calculation snapshots.

        Args:
            session: Database session
            limit: Maximum number of snapshots to return
            status: Filter by status
            algorithm_version: Filter by algorithm version

        Returns:
            List of snapshot metadata dictionaries
        """
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


# Global snapshot manager instance
snapshot_manager = SnapshotManager()


async def create_calculation_snapshot(
    session,
    symbols: list[str],
    timeframes: list[str],
    features: list[str] | None = None,
    **kwargs: Any,
) -> str:
    """
    Create calculation snapshot (convenience function).

    Args:
        session: Database session
        symbols: List of symbols
        timeframes: List of timeframes
        features: List of feature names (None = all)
        **kwargs: Additional configuration

    Returns:
        Snapshot ID
    """
    config = SnapshotConfig(
        symbols=symbols,
        timeframes=timeframes,
        features=features or [],
        volatility_normalize=kwargs.get("volatility_normalize", True),
        normalize_window=kwargs.get("normalize_window", 20),
        normalize_method=kwargs.get("normalize_method", "rolling_std"),
    )

    return await snapshot_manager.create_snapshot(session, config)
