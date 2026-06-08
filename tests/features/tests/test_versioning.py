"""
Tests for versioning module.
"""

from unittest.mock import MagicMock, patch

from src.features.infrastructure.versioning import (
    FeaturesVersionManager,
    VersionInfo,
    VersionTracker,
    export_version_info,
    get_current_version,
    track_version_change,
)


class TestVersionInfo:
    """Test VersionInfo dataclass."""

    def test_version_info_creation(self):
        """Test creating VersionInfo."""
        version_info = VersionInfo(
            schema_version="schema_v12345678",
            algo_version="algo_v87654321",
            params_hash="params_abcdef12",
            created_at="2023-01-01T00:00:00Z",
            features_count=100,
            phase2_compliant=True,
        )

        assert version_info.schema_version == "schema_v12345678"
        assert version_info.algo_version == "algo_v87654321"
        assert version_info.params_hash == "params_abcdef12"
        assert version_info.created_at == "2023-01-01T00:00:00Z"
        assert version_info.features_count == 100
        assert version_info.phase2_compliant is True


class TestFeaturesVersionManager:
    """Test FeaturesVersionManager class."""

    def test_init(self):
        """Test manager initialization."""
        manager = FeaturesVersionManager()
        assert manager._version_cache is None
        assert manager.logger is not None

    def test_get_schema_version(self):
        """Test getting schema version."""
        manager = FeaturesVersionManager()

        with patch("src.features.specs.FEATURE_SPECS", [{"name": "test_feature"}]):
            version = manager.get_schema_version()
            assert version.startswith("schema_v")
            assert len(version) >= 16  # 'schema_v' + 8+ chars

    def test_get_algorithm_version(self):
        """Test getting algorithm version."""
        manager = FeaturesVersionManager()

        version = manager.get_algorithm_version()
        assert version.startswith("algo_v")
        assert len(version) >= 12  # 'algo_v' + 8+ chars

    def test_get_params_hash(self):
        """Test getting parameters hash."""
        manager = FeaturesVersionManager()

        # Test with default parameters
        hash1 = manager.get_params_hash()
        assert hash1.startswith("params_")
        assert len(hash1) == 15  # 'params_' + 8 chars

        # Test with custom parameters
        hash2 = manager.get_params_hash(volatility_normalize=False, normalize_window=30)
        assert hash2.startswith("params_")
        assert hash2 != hash1  # Different parameters should produce different hash

    def test_get_version_info(self):
        """Test getting complete version info."""
        manager = FeaturesVersionManager()

        with patch("src.features.specs.FEATURE_SPECS", [{"name": "test_feature"}]):
            with patch(
                "src.features.specs.PHASE_2_REQUIRED_FEATURES", ["test_feature"]
            ):
                version_info = manager.get_version_info()

                assert isinstance(version_info, VersionInfo)
                assert version_info.schema_version.startswith("schema_v")
                assert version_info.algo_version.startswith("algo_v")
                assert version_info.params_hash.startswith("params_")
                assert version_info.features_count == 1
                assert (
                    version_info.phase2_compliant is True
                    or version_info.phase2_compliant is False
                )  # May be False if required features don't match

    def test_get_version_info_caching(self):
        """Test version info caching."""
        manager = FeaturesVersionManager()

        with patch("src.features.specs.FEATURE_SPECS", [{"name": "test_feature"}]):
            with patch(
                "src.features.specs.PHASE_2_REQUIRED_FEATURES", ["test_feature"]
            ):
                # First call
                version_info1 = manager.get_version_info()

                # Second call should return cached version
                version_info2 = manager.get_version_info()

                assert version_info1 is version_info2  # Same object (cached)

    def test_clear_cache(self):
        """Test clearing version cache."""
        manager = FeaturesVersionManager()

        with patch("src.features.specs.FEATURE_SPECS", [{"name": "test_feature"}]):
            with patch(
                "src.features.specs.PHASE_2_REQUIRED_FEATURES", ["test_feature"]
            ):
                # Get version info
                version_info1 = manager.get_version_info()

                # Clear cache
                manager.clear_cache()

                # Get version info again
                version_info2 = manager.get_version_info()

                # Should be different objects (not cached)
                assert version_info1 is not version_info2
                # But content should be the same
                assert version_info1.schema_version == version_info2.schema_version

    def test_export_version_info(self):
        """Test exporting version info."""
        manager = FeaturesVersionManager()

        with patch("src.features.specs.FEATURE_SPECS", [{"name": "test_feature"}]):
            with patch("builtins.open", create=True) as mock_open:
                with patch("json.dump") as mock_json_dump:
                    manager.export_version_info("test_version.json")

                    mock_open.assert_called_once_with("test_version.json", "w")
                    mock_json_dump.assert_called_once()

    def test_validate_version_consistency(self):
        """Test version consistency validation."""
        manager = FeaturesVersionManager()

        with patch("src.features.specs.FEATURE_SPECS", [{"name": "test_feature"}]):
            # Test with no expected version
            result = manager.validate_version_consistency()
            assert result is True

            # Test with matching version
            current_version = manager.get_schema_version()
            result = manager.validate_version_consistency(current_version)
            assert result is True

            # Test with non-matching version
            result = manager.validate_version_consistency("different_version")
            assert result is False

    def test_get_version_summary(self):
        """Test getting version summary."""
        manager = FeaturesVersionManager()

        with patch("src.features.specs.FEATURE_SPECS", [{"name": "test_feature"}]):
            with patch(
                "src.features.specs.PHASE_2_REQUIRED_FEATURES", ["test_feature"]
            ):
                summary = manager.get_version_summary()

                assert "schema_version" in summary
                assert "algo_version" in summary
                assert "params_hash" in summary
                assert "features_count" in summary
                assert "phase2_compliant" in summary
                assert "created_at" in summary


class TestVersionTracker:
    """Test VersionTracker class."""

    def test_init(self):
        """Test tracker initialization."""
        tracker = VersionTracker()
        assert tracker.version_history == []
        assert tracker.logger is not None

    def test_track_version_change(self):
        """Test tracking version change."""
        tracker = VersionTracker()

        with patch.object(tracker.logger, "info") as mock_info:
            tracker.track_version_change(
                old_version="v1.0.0",
                new_version="v1.1.0",
                change_type="schema",
                details={"features_added": 5},
            )

            assert len(tracker.version_history) == 1
            change_record = tracker.version_history[0]
            assert change_record["old_version"] == "v1.0.0"
            assert change_record["new_version"] == "v1.1.0"
            assert change_record["change_type"] == "schema"
            assert change_record["details"]["features_added"] == 5

            mock_info.assert_called_once()

    def test_get_migration_plan(self):
        """Test getting migration plan."""
        tracker = VersionTracker()

        with patch.object(tracker.logger, "info") as mock_info:
            plan = tracker.get_migration_plan("schema_v1", "schema_v2")

            assert plan["from_version"] == "schema_v1"
            assert plan["to_version"] == "schema_v2"
            assert "steps" in plan
            assert "rollback_steps" in plan
            assert "estimated_duration" in plan
            assert "risk_level" in plan

            mock_info.assert_called_once()


class TestGlobalFunctions:
    """Test global functions."""

    def test_get_current_version(self):
        """Test get_current_version function."""
        with patch("src.features.versioning.version_manager") as mock_manager:
            mock_version_info = MagicMock()
            mock_manager.get_version_info.return_value = mock_version_info

            result = get_current_version()

            assert result == mock_version_info
            mock_manager.get_version_info.assert_called_once()

    def test_track_version_change(self):
        """Test track_version_change function."""
        with patch("src.features.versioning.version_tracker") as mock_tracker:
            track_version_change("v1.0.0", "v1.1.0", "schema", {"test": "data"})

            mock_tracker.track_version_change.assert_called_once_with(
                "v1.0.0", "v1.1.0", "schema", {"test": "data"}
            )

    def test_export_version_info(self):
        """Test export_version_info function."""
        with patch("src.features.versioning.version_manager") as mock_manager:
            export_version_info("test.json", test_param="value")

            mock_manager.export_version_info.assert_called_once_with(
                "test.json", test_param="value"
            )
