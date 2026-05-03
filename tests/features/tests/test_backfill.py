"""
Tests for backfill module.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from src.features.application.backfill import (
    BackfillConfig,
    BackfillResult,
    FeaturesBackfillManager,
    create_backfill_rollback_plan,
    execute_backfill_operation,
    get_feature_flags,
    set_feature_flag,
)


class TestBackfillConfig:
    """Test BackfillConfig dataclass."""

    def test_backfill_config_creation(self):
        """Test creating BackfillConfig."""
        start_date = datetime(2023, 1, 1, tzinfo=UTC)
        end_date = datetime(2023, 1, 2, tzinfo=UTC)

        config = BackfillConfig(
            start_date=start_date,
            end_date=end_date,
            symbols=["BTC-USDT-SWAP"],
            timeframes=["1H", "4H"],
            batch_size=1000,
            parallel_workers=4,
            enable_volatility_normalize=True,
            enable_fallback_insert=True,
            dry_run=False,
        )

        assert config.start_date == start_date
        assert config.end_date == end_date
        assert config.symbols == ["BTC-USDT-SWAP"]
        assert config.timeframes == ["1H", "4H"]
        assert config.batch_size == 1000
        assert config.parallel_workers == 4
        assert config.enable_volatility_normalize is True
        assert config.enable_fallback_insert is True
        assert config.dry_run is False


class TestBackfillResult:
    """Test BackfillResult dataclass."""

    def test_backfill_result_creation(self):
        """Test creating BackfillResult."""
        result = BackfillResult(
            total_processed=1000,
            successful=950,
            failed=50,
            duration_seconds=120.5,
            errors=["Error 1", "Error 2"],
            warnings=["Warning 1"],
        )

        assert result.total_processed == 1000
        assert result.successful == 950
        assert result.failed == 50
        assert result.duration_seconds == 120.5
        assert result.errors == ["Error 1", "Error 2"]
        assert result.warnings == ["Warning 1"]


class TestFeaturesBackfillManager:
    """Test FeaturesBackfillManager class."""

    def test_init(self):
        """Test manager initialization."""
        manager = FeaturesBackfillManager()
        assert manager.logger is not None
        assert "volatility_normalize" in manager.feature_flags
        assert "fallback_insert" in manager.feature_flags
        assert "batch_processing" in manager.feature_flags

    def test_set_feature_flag(self):
        """Test setting feature flag."""
        manager = FeaturesBackfillManager()

        with patch.object(manager.logger, "info") as mock_info:
            manager.set_feature_flag("volatility_normalize", False)

            assert manager.feature_flags["volatility_normalize"] is False
            mock_info.assert_called_once()

    def test_set_feature_flag_unknown(self):
        """Test setting unknown feature flag."""
        manager = FeaturesBackfillManager()

        with patch.object(manager.logger, "warning") as mock_warning:
            manager.set_feature_flag("unknown_flag", True)

            mock_warning.assert_called_once()

    def test_get_feature_flags(self):
        """Test getting feature flags."""
        manager = FeaturesBackfillManager()

        flags = manager.get_feature_flags()

        assert isinstance(flags, dict)
        assert "volatility_normalize" in flags
        assert "fallback_insert" in flags
        # Should return a copy
        assert flags is not manager.feature_flags

    def test_estimate_backfill_scope(self):
        """Test estimating backfill scope."""
        manager = FeaturesBackfillManager()

        start_date = datetime(2023, 1, 1, tzinfo=UTC)
        end_date = datetime(2023, 1, 3, tzinfo=UTC)  # 2 days

        config = BackfillConfig(
            start_date=start_date,
            end_date=end_date,
            symbols=["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
            timeframes=["1H", "4H"],
            batch_size=1000,
        )

        with patch.object(manager.logger, "info") as mock_info:
            scope = manager.estimate_backfill_scope(config)

            assert scope["date_range_days"] == 2
            assert scope["symbols_count"] == 2
            assert scope["timeframes_count"] == 2
            assert "total_estimated_records" in scope
            assert "estimated_duration_hours" in scope
            assert "memory_estimate_mb" in scope

            mock_info.assert_called_once()

    def test_execute_backfill_dry_run(self):
        """Test executing backfill in dry run mode."""
        manager = FeaturesBackfillManager()

        start_date = datetime(2023, 1, 1, tzinfo=UTC)
        end_date = datetime(2023, 1, 2, tzinfo=UTC)

        config = BackfillConfig(
            start_date=start_date,
            end_date=end_date,
            symbols=["BTC-USDT-SWAP"],
            timeframes=["1H"],
            dry_run=True,
        )

        with patch.object(manager, "estimate_backfill_scope") as mock_estimate:
            mock_estimate.return_value = {
                "total_estimated_records": 1000,
                "estimated_duration_hours": 1.0,
            }

            with patch("src.features.backfill.get_current_version") as mock_version:
                mock_version.return_value = MagicMock()

                with patch.object(manager.logger, "info"):
                    result = manager.execute_backfill(config)

                    assert result.total_processed == 1000
                    assert result.successful == 1000
                    assert result.failed == 0
                    assert len(result.warnings) > 0
                    assert "Dry run mode" in result.warnings[0]

    def test_execute_backfill_validation_error(self):
        """Test backfill with validation error."""
        manager = FeaturesBackfillManager()

        start_date = datetime(2023, 1, 2, tzinfo=UTC)
        end_date = datetime(2023, 1, 1, tzinfo=UTC)  # Invalid: end before start

        config = BackfillConfig(
            start_date=start_date,
            end_date=end_date,
            symbols=["BTC-USDT-SWAP"],
            timeframes=["1H"],
        )

        with patch.object(manager.logger, "error"):
            result = manager.execute_backfill(config)

            assert result.failed > 0
            assert len(result.errors) > 0
            assert "Start date must be before end date" in result.errors[0]

    def test_get_records_per_day(self):
        """Test getting records per day."""
        manager = FeaturesBackfillManager()

        assert manager._get_records_per_day("1m") == 1440
        assert manager._get_records_per_day("5m") == 288
        assert manager._get_records_per_day("15m") == 96
        assert manager._get_records_per_day("1H") == 24
        assert manager._get_records_per_day("4H") == 6
        assert manager._get_records_per_day("1D") == 1
        assert manager._get_records_per_day("unknown") == 1

    def test_create_rollback_plan(self):
        """Test creating rollback plan."""
        manager = FeaturesBackfillManager()

        start_date = datetime(2023, 1, 1, tzinfo=UTC)
        end_date = datetime(2023, 1, 2, tzinfo=UTC)

        config = BackfillConfig(
            start_date=start_date,
            end_date=end_date,
            symbols=["BTC-USDT-SWAP"],
            timeframes=["1H"],
        )

        with patch.object(manager.logger, "info") as mock_info:
            plan = manager.create_rollback_plan(config)

            assert "operation_id" in plan
            assert "config" in plan
            assert "rollback_steps" in plan
            assert "safety_checks" in plan
            assert len(plan["rollback_steps"]) > 0
            assert plan["operation_id"].startswith("backfill_")

            mock_info.assert_called_once()

    def test_execute_rollback(self):
        """Test executing rollback."""
        manager = FeaturesBackfillManager()

        rollback_plan = {
            "operation_id": "test_operation",
            "rollback_steps": [{"step": 1, "action": "test_action", "sql": "SELECT 1"}],
        }

        with patch.object(manager.logger, "info") as mock_info:
            result = manager.execute_rollback(rollback_plan)

            assert result["operation_id"] == "test_operation"
            assert "steps_completed" in result
            assert "steps_failed" in result
            assert "errors" in result
            assert "warnings" in result

            mock_info.assert_called()


class TestGlobalFunctions:
    """Test global functions."""

    def test_execute_backfill_operation(self):
        """Test execute_backfill_operation function."""
        with patch("src.features.backfill.backfill_manager") as mock_manager:
            mock_result = MagicMock()
            mock_manager.execute_backfill.return_value = mock_result

            config = BackfillConfig(
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC) + timedelta(days=1),
                symbols=["BTC-USDT-SWAP"],
                timeframes=["1H"],
            )

            result = execute_backfill_operation(config)

            assert result == mock_result
            mock_manager.execute_backfill.assert_called_once_with(config, None)

    def test_create_backfill_rollback_plan(self):
        """Test create_backfill_rollback_plan function."""
        with patch("src.features.backfill.backfill_manager") as mock_manager:
            mock_plan = {"test": "plan"}
            mock_manager.create_rollback_plan.return_value = mock_plan

            config = BackfillConfig(
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC) + timedelta(days=1),
                symbols=["BTC-USDT-SWAP"],
                timeframes=["1H"],
            )

            plan = create_backfill_rollback_plan(config)

            assert plan == mock_plan
            mock_manager.create_rollback_plan.assert_called_once_with(config)

    def test_set_feature_flag(self):
        """Test set_feature_flag function."""
        with patch("src.features.backfill.backfill_manager") as mock_manager:
            set_feature_flag("test_flag", True)

            mock_manager.set_feature_flag.assert_called_once_with("test_flag", True)

    def test_get_feature_flags(self):
        """Test get_feature_flags function."""
        with patch("src.features.backfill.backfill_manager") as mock_manager:
            mock_flags = {"test": True}
            mock_manager.get_feature_flags.return_value = mock_flags

            flags = get_feature_flags()

            assert flags == mock_flags
            mock_manager.get_feature_flags.assert_called_once()
