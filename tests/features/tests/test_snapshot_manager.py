"""
Tests for SnapshotManager (FEAT-001: ML Reproducibility).

This module tests the snapshot management functionality for ensuring
ML model reproducibility through versioned calculation tracking.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.features.infrastructure.versioning import (
    SnapshotConfig,
    SnapshotManager,
    create_calculation_snapshot,
)


@pytest.fixture
def snapshot_config():
    """Create test snapshot configuration."""
    return SnapshotConfig(
        symbols=["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
        timeframes=["1H", "4H"],
        features=["rsi_14", "sma_50", "macd"],
        volatility_normalize=True,
        normalize_window=20,
        normalize_method="rolling_std",
    )


@pytest.fixture
def mock_session():
    """Create mock database session."""
    session = AsyncMock()
    session.add = Mock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    return session


class TestSnapshotConfig:
    """Test SnapshotConfig dataclass."""

    def test_snapshot_config_creation(self, snapshot_config):
        """Test snapshot config can be created."""
        assert snapshot_config.symbols == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
        assert snapshot_config.timeframes == ["1H", "4H"]
        assert snapshot_config.volatility_normalize is True

    def test_snapshot_config_to_dict(self, snapshot_config):
        """Test conversion to dictionary."""
        config_dict = snapshot_config.to_dict()

        assert "symbols" in config_dict
        assert "timeframes" in config_dict
        assert "features" in config_dict
        assert config_dict["normalize_window"] == 20

    def test_snapshot_config_to_json(self, snapshot_config):
        """Test conversion to JSON."""
        import json

        config_json = snapshot_config.to_json()
        parsed = json.loads(config_json)

        assert parsed["symbols"] == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
        assert parsed["normalize_method"] == "rolling_std"


class TestSnapshotManager:
    """Test SnapshotManager class."""

    def test_snapshot_manager_initialization(self):
        """Test snapshot manager can be initialized."""
        manager = SnapshotManager()

        assert manager is not None
        assert manager._module_version == "1.0.0"

    def test_generate_snapshot_id(self):
        """Test snapshot ID generation."""
        manager = SnapshotManager()

        snapshot_id_1 = manager._generate_snapshot_id()
        snapshot_id_2 = manager._generate_snapshot_id()

        # Should be unique
        assert snapshot_id_1 != snapshot_id_2

        # Should have correct format
        assert snapshot_id_1.startswith("snap_")
        assert len(snapshot_id_1.split("_")) == 3  # snap_timestamp_uuid

    @pytest.mark.asyncio
    async def test_create_snapshot(self, mock_session, snapshot_config):
        """Test snapshot creation."""
        manager = SnapshotManager()

        snapshot_id = await manager.create_snapshot(mock_session, snapshot_config)

        # Should return a snapshot ID
        assert snapshot_id is not None
        assert snapshot_id.startswith("snap_")

        # Should have added metadata to session
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_snapshot_with_custom_id(self, mock_session, snapshot_config):
        """Test snapshot creation with custom ID."""
        manager = SnapshotManager()
        custom_id = "snap_test_12345678"

        snapshot_id = await manager.create_snapshot(
            mock_session, snapshot_config, snapshot_id=custom_id
        )

        assert snapshot_id == custom_id

    @pytest.mark.asyncio
    async def test_update_snapshot_progress(self, mock_session):
        """Test updating snapshot progress."""
        manager = SnapshotManager()

        await manager.update_snapshot_progress(
            mock_session, "snap_test_001", rows_calculated=5000
        )

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_snapshot(self, mock_session):
        """Test completing a snapshot."""
        manager = SnapshotManager()

        await manager.complete_snapshot(
            mock_session, "snap_test_001", rows_calculated=10000, duration_seconds=45.5
        )

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_fail_snapshot(self, mock_session):
        """Test failing a snapshot."""
        manager = SnapshotManager()
        error_msg = "Test error: calculation failed"

        await manager.fail_snapshot(
            mock_session, "snap_test_001", error_message=error_msg
        )

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_snapshot(self, mock_session):
        """Test retrieving a snapshot."""
        manager = SnapshotManager()

        # Mock the result
        mock_metadata = Mock()
        mock_metadata.snapshot_id = "snap_test_001"
        mock_metadata.created_at = datetime.now(UTC)
        mock_metadata.completed_at = datetime.now(UTC)
        mock_metadata.algorithm_version = "algo_v12345678"
        mock_metadata.module_version = "1.0.0"
        mock_metadata.config = '{"symbols": ["BTC"], "timeframes": ["1H"]}'
        mock_metadata.symbols = '["BTC"]'
        mock_metadata.timeframes = '["1H"]'
        mock_metadata.status = "completed"
        mock_metadata.rows_calculated = 10000
        mock_metadata.execution_duration_seconds = 45.5
        mock_metadata.error_message = None

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = Mock(return_value=mock_metadata)
        mock_session.execute.return_value = mock_result

        snapshot = await manager.get_snapshot(mock_session, "snap_test_001")

        assert snapshot is not None
        assert snapshot["snapshot_id"] == "snap_test_001"
        assert snapshot["status"] == "completed"
        assert snapshot["rows_calculated"] == 10000

    @pytest.mark.asyncio
    async def test_get_snapshot_not_found(self, mock_session):
        """Test retrieving non-existent snapshot."""
        manager = SnapshotManager()

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        mock_session.execute.return_value = mock_result

        snapshot = await manager.get_snapshot(mock_session, "snap_nonexistent")

        assert snapshot is None

    @pytest.mark.asyncio
    async def test_list_snapshots(self, mock_session):
        """Test listing snapshots."""
        manager = SnapshotManager()

        # Mock snapshot list
        mock_snapshot1 = Mock()
        mock_snapshot1.snapshot_id = "snap_001"
        mock_snapshot1.created_at = datetime.now(UTC)
        mock_snapshot1.status = "completed"
        mock_snapshot1.algorithm_version = "algo_v1"
        mock_snapshot1.symbols = '["BTC"]'
        mock_snapshot1.timeframes = '["1H"]'
        mock_snapshot1.rows_calculated = 1000

        mock_snapshot2 = Mock()
        mock_snapshot2.snapshot_id = "snap_002"
        mock_snapshot2.created_at = datetime.now(UTC)
        mock_snapshot2.status = "in_progress"
        mock_snapshot2.algorithm_version = "algo_v1"
        mock_snapshot2.symbols = '["ETH"]'
        mock_snapshot2.timeframes = '["4H"]'
        mock_snapshot2.rows_calculated = 500

        mock_result = AsyncMock()
        mock_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[mock_snapshot1, mock_snapshot2]))
        )
        mock_session.execute.return_value = mock_result

        snapshots = await manager.list_snapshots(mock_session, limit=50)

        assert len(snapshots) == 2
        assert snapshots[0]["snapshot_id"] == "snap_001"
        assert snapshots[1]["snapshot_id"] == "snap_002"

    @pytest.mark.asyncio
    async def test_list_snapshots_with_filters(self, mock_session):
        """Test listing snapshots with filters."""
        manager = SnapshotManager()

        mock_result = AsyncMock()
        mock_result.scalars = Mock(return_value=Mock(all=Mock(return_value=[])))
        mock_session.execute.return_value = mock_result

        snapshots = await manager.list_snapshots(
            mock_session, limit=10, status="completed", algorithm_version="algo_v1"
        )

        assert len(snapshots) == 0
        mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_calculation_snapshot_convenience_function(mock_session):
    """Test convenience function for creating snapshots."""
    with patch("src.features.versioning.snapshot_manager") as mock_manager:
        mock_manager.create_snapshot = AsyncMock(return_value="snap_test_001")

        snapshot_id = await create_calculation_snapshot(
            mock_session,
            symbols=["BTC-USDT-SWAP"],
            timeframes=["1H"],
            features=["rsi_14"],
            volatility_normalize=True,
        )

        assert snapshot_id == "snap_test_001"
        mock_manager.create_snapshot.assert_called_once()


class TestSnapshotWorkflow:
    """Test complete snapshot workflow."""

    @pytest.mark.asyncio
    async def test_complete_workflow(self, mock_session, snapshot_config):
        """Test complete snapshot creation -> update -> completion workflow."""
        manager = SnapshotManager()

        # Step 1: Create snapshot
        snapshot_id = await manager.create_snapshot(mock_session, snapshot_config)
        assert snapshot_id is not None

        # Step 2: Update progress
        await manager.update_snapshot_progress(mock_session, snapshot_id, 5000)

        # Step 3: Complete snapshot
        await manager.complete_snapshot(mock_session, snapshot_id, 10000, 45.5)

        # Verify all methods were called
        assert mock_session.add.call_count == 1
        assert mock_session.commit.call_count == 3  # create + update + complete
        assert mock_session.execute.call_count == 2  # update + complete

    @pytest.mark.asyncio
    async def test_failed_workflow(self, mock_session, snapshot_config):
        """Test snapshot creation -> failure workflow."""
        manager = SnapshotManager()

        # Step 1: Create snapshot
        snapshot_id = await manager.create_snapshot(mock_session, snapshot_config)

        # Step 2: Mark as failed
        await manager.fail_snapshot(
            mock_session, snapshot_id, "Calculation failed due to missing data"
        )

        # Verify all methods were called
        assert mock_session.add.call_count == 1
        assert mock_session.commit.call_count == 2  # create + fail
        assert mock_session.execute.call_count == 1  # fail


@pytest.mark.integration
class TestSnapshotManagerIntegration:
    """Integration tests with real database (requires test DB)."""

    @pytest.mark.skip(reason="Requires test database setup")
    @pytest.mark.asyncio
    async def test_real_snapshot_creation(self):
        """Test snapshot creation with real database."""
        # This test would require actual database connection
        # Skip by default, run manually with proper setup
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
