"""
Tests for metrics collection module.
"""

from unittest.mock import patch

import numpy as np
import pandas as pd

from src.features.observability.metrics import (
    BatchMetrics,
    FeatureQualityMetrics,
    FeaturesMetricsCollector,
    Phase2ComplianceMetrics,
    metrics_collector,
)


class TestFeatureQualityMetrics:
    """Test FeatureQualityMetrics dataclass."""

    def test_feature_quality_metrics_creation(self):
        """Test creating FeatureQualityMetrics."""
        metrics = FeatureQualityMetrics(
            feature_name="test_feature",
            fill_rate=85.5,
            non_null_count=85,
            total_count=100,
            has_constant_values=False,
            has_infinite_values=False,
            has_negative_values=True,
            min_value=0.0,
            max_value=100.0,
            mean_value=50.0,
            std_value=25.0,
        )

        assert metrics.feature_name == "test_feature"
        assert metrics.fill_rate == 85.5
        assert metrics.non_null_count == 85
        assert metrics.total_count == 100
        assert metrics.has_constant_values is False
        assert metrics.has_infinite_values is False
        assert metrics.has_negative_values is True
        assert metrics.min_value == 0.0
        assert metrics.max_value == 100.0
        assert metrics.mean_value == 50.0
        assert metrics.std_value == 25.0


class TestBatchMetrics:
    """Test BatchMetrics dataclass."""

    def test_batch_metrics_creation(self):
        """Test creating BatchMetrics."""
        metrics = BatchMetrics(
            batch_size=100,
            processed_count=95,
            error_count=5,
            success_rate=90.0,
            duration_seconds=10.5,
            features_calculated=50,
            features_failed=2,
        )

        assert metrics.batch_size == 100
        assert metrics.processed_count == 95
        assert metrics.error_count == 5
        assert metrics.success_rate == 90.0
        assert metrics.duration_seconds == 10.5
        assert metrics.features_calculated == 50
        assert metrics.features_failed == 2


class TestPhase2ComplianceMetrics:
    """Test Phase2ComplianceMetrics dataclass."""

    def test_phase2_compliance_metrics_creation(self):
        """Test creating Phase2ComplianceMetrics."""
        metrics = Phase2ComplianceMetrics(
            required_features=["ema_8", "sma_20", "rsi_14"],
            present_features=["ema_8", "sma_20"],
            missing_features=["rsi_14"],
            compliance_rate=66.7,
            fill_rates={"ema_8": 95.0, "sma_20": 90.0},
        )

        assert metrics.required_features == ["ema_8", "sma_20", "rsi_14"]
        assert metrics.present_features == ["ema_8", "sma_20"]
        assert metrics.missing_features == ["rsi_14"]
        assert metrics.compliance_rate == 66.7
        assert metrics.fill_rates == {"ema_8": 95.0, "sma_20": 90.0}


class TestFeaturesMetricsCollector:
    """Test FeaturesMetricsCollector class."""

    def test_init(self):
        """Test collector initialization."""
        collector = FeaturesMetricsCollector()
        assert collector.metrics_history == []
        assert collector.logger is not None

    def test_collect_feature_quality(self):
        """Test collecting feature quality metrics."""
        collector = FeaturesMetricsCollector()

        # Create test DataFrame
        df = pd.DataFrame({"test_feature": [1, 2, 3, None, 5, 6, 7, 8, 9, 10]})

        with patch.object(collector.logger, "warning"):
            metrics = collector.collect_feature_quality(df, "test_feature")

            assert metrics.feature_name == "test_feature"
            assert metrics.fill_rate == 90.0  # 9 out of 10 non-null
            assert metrics.non_null_count == 9
            assert metrics.total_count == 10
            assert metrics.has_constant_values is False
            assert metrics.has_infinite_values is False
            assert metrics.has_negative_values is False
            assert metrics.min_value == 1.0
            assert metrics.max_value == 10.0
            assert (
                abs(metrics.mean_value - 5.5) < 0.2
            )  # Allow for floating point precision
            assert metrics.std_value is not None

    def test_collect_feature_quality_missing_column(self):
        """Test collecting feature quality for missing column."""
        collector = FeaturesMetricsCollector()

        df = pd.DataFrame({"other_feature": [1, 2, 3]})
        metrics = collector.collect_feature_quality(df, "missing_feature")

        assert metrics.feature_name == "missing_feature"
        assert metrics.fill_rate == 0.0
        assert metrics.non_null_count == 0
        assert metrics.total_count == 3
        assert metrics.min_value is None
        assert metrics.max_value is None

    def test_collect_feature_quality_constant_values(self):
        """Test collecting feature quality for constant values."""
        collector = FeaturesMetricsCollector()

        df = pd.DataFrame({"constant_feature": [5, 5, 5, 5, 5]})

        with patch.object(collector.logger, "warning") as mock_warning:
            metrics = collector.collect_feature_quality(df, "constant_feature")

            assert metrics.has_constant_values is True
            # Should warn about constant values
            mock_warning.assert_called()

    def test_collect_feature_quality_infinite_values(self):
        """Test collecting feature quality for infinite values."""
        collector = FeaturesMetricsCollector()

        df = pd.DataFrame({"infinite_feature": [1, 2, np.inf, 4, 5]})

        with patch.object(collector.logger, "warning") as mock_warning:
            metrics = collector.collect_feature_quality(df, "infinite_feature")

            assert metrics.has_infinite_values is True
            # Should warn about infinite values
            mock_warning.assert_called()

    def test_collect_batch_metrics(self):
        """Test collecting batch metrics."""
        collector = FeaturesMetricsCollector()

        with patch.object(collector.logger, "log_metrics") as mock_log_metrics:
            with patch.object(collector.logger, "warning") as mock_warning:
                metrics = collector.collect_batch_metrics(
                    batch_size=100,
                    processed_count=95,
                    error_count=5,
                    duration_seconds=10.5,
                    features_calculated=50,
                    features_failed=2,
                )

                assert metrics.batch_size == 100
                assert metrics.processed_count == 95
                assert metrics.error_count == 5
                assert metrics.success_rate == 90.0
                assert metrics.duration_seconds == 10.5
                assert metrics.features_calculated == 50
                assert metrics.features_failed == 2

                # Should log metrics
                mock_log_metrics.assert_called_once()
                # Should warn about errors
                mock_warning.assert_called_once()

    def test_collect_batch_metrics_no_errors(self):
        """Test collecting batch metrics with no errors."""
        collector = FeaturesMetricsCollector()

        with patch.object(collector.logger, "log_metrics"):
            with patch.object(collector.logger, "warning") as mock_warning:
                metrics = collector.collect_batch_metrics(
                    batch_size=100,
                    processed_count=100,
                    error_count=0,
                    duration_seconds=10.5,
                    features_calculated=50,
                    features_failed=0,
                )

                assert metrics.success_rate == 100.0
                # Should not warn about errors
                mock_warning.assert_not_called()

    def test_collect_phase2_compliance(self):
        """Test collecting Phase 2 compliance metrics."""
        collector = FeaturesMetricsCollector()

        # Mock PHASE_2_REQUIRED_FEATURES
        with patch(
            "src.features.metrics.PHASE_2_REQUIRED_FEATURES",
            ["ema_8", "sma_20", "rsi_14"],
        ):
            df = pd.DataFrame(
                {"ema_8": [1, 2, 3], "sma_20": [4, 5, 6], "other_feature": [7, 8, 9]}
            )

            with patch.object(collector.logger, "warning") as mock_warning:
                metrics = collector.collect_phase2_compliance(df)

                assert metrics.required_features == ["ema_8", "sma_20", "rsi_14"]
                assert metrics.present_features == ["ema_8", "sma_20"]
                assert metrics.missing_features == ["rsi_14"]
                assert (
                    abs(metrics.compliance_rate - 66.7) < 0.1
                )  # Allow for floating point precision
                assert "ema_8" in metrics.fill_rates
                assert "sma_20" in metrics.fill_rates

                # Should warn about missing features
                mock_warning.assert_called()

    def test_collect_feature_group_metrics(self):
        """Test collecting feature group metrics."""
        collector = FeaturesMetricsCollector()

        df = pd.DataFrame(
            {
                "ema_8": [1, 2, 3, None, 5],
                "sma_20": [2, 3, 4, 5, 6],
                "rsi_14": [30, 40, 50, 60, 70],
                "atr_14": [0.1, 0.2, 0.3, 0.4, 0.5],
                "obv": [100, 200, 300, 400, 500],
                "macd": [0.1, 0.2, 0.3, 0.4, 0.5],
                "other_feature": [1, 2, 3, 4, 5],
            }
        )

        with patch.object(collector.logger, "log_metrics") as mock_log_metrics:
            group_metrics = collector.collect_feature_group_metrics(df)

            # Check that groups are identified
            assert "moving_averages" in group_metrics
            assert "oscillators" in group_metrics
            assert "volatility" in group_metrics
            assert "volume" in group_metrics
            assert "macd" in group_metrics

            # Check moving averages group
            ma_group = group_metrics["moving_averages"]
            assert ma_group["feature_count"] == 2  # ema_8, sma_20
            assert "ema_8" in ma_group["features"]
            assert "sma_20" in ma_group["features"]
            assert ma_group["avg_fill_rate"] > 0

            # Should log metrics
            mock_log_metrics.assert_called_once()

    def test_generate_summary_report(self):
        """Test generating summary report."""
        collector = FeaturesMetricsCollector()

        # Create test metrics
        feature_metrics = [
            FeatureQualityMetrics(
                feature_name="test1",
                fill_rate=90.0,
                non_null_count=90,
                total_count=100,
                has_constant_values=False,
                has_infinite_values=False,
                has_negative_values=False,
                min_value=1.0,
                max_value=100.0,
                mean_value=50.0,
                std_value=25.0,
            ),
            FeatureQualityMetrics(
                feature_name="test2",
                fill_rate=30.0,  # Low fill rate
                non_null_count=30,
                total_count=100,
                has_constant_values=True,  # Has issues
                has_infinite_values=False,
                has_negative_values=False,
                min_value=1.0,
                max_value=100.0,
                mean_value=50.0,
                std_value=25.0,
            ),
        ]

        batch_metrics = BatchMetrics(
            batch_size=100,
            processed_count=95,
            error_count=5,
            success_rate=90.0,
            duration_seconds=10.5,
            features_calculated=50,
            features_failed=2,
        )

        phase2_metrics = Phase2ComplianceMetrics(
            required_features=["test1", "test2"],
            present_features=["test1"],
            missing_features=["test2"],
            compliance_rate=50.0,
            fill_rates={"test1": 90.0},
        )

        group_metrics = {
            "test_group": {
                "feature_count": 2,
                "avg_fill_rate": 60.0,
                "features": ["test1", "test2"],
            }
        }

        with patch.object(collector.logger, "info") as mock_info:
            summary = collector.generate_summary_report(
                feature_metrics, batch_metrics, phase2_metrics, group_metrics
            )

            assert "timestamp" in summary
            assert "overview" in summary
            assert "batch_processing" in summary
            assert "phase2_compliance" in summary
            assert "feature_groups" in summary
            assert "individual_features" in summary

            # Check overview
            overview = summary["overview"]
            assert overview["total_features"] == 2
            assert overview["features_with_issues"] == 1
            assert overview["avg_fill_rate"] == 60.0
            assert "test2" in overview["problematic_features"]

            # Should store in history
            assert len(collector.metrics_history) == 1

            # Should log summary
            mock_info.assert_called_once()

    def test_export_metrics_json(self):
        """Test exporting metrics to JSON."""
        collector = FeaturesMetricsCollector()

        # Add some test data
        collector.metrics_history = [{"test": "data"}]

        with patch("builtins.open", create=True) as mock_open:
            with patch("json.dump") as mock_json_dump:
                collector.export_metrics("test.json", "json")

                mock_open.assert_called_once_with("test.json", "w")
                mock_json_dump.assert_called_once()

    def test_export_metrics_csv(self):
        """Test exporting metrics to CSV."""
        collector = FeaturesMetricsCollector()

        # Add some test data
        collector.metrics_history = [
            {
                "timestamp": "2023-01-01T00:00:00Z",
                "overview": {"total_features": 10, "avg_fill_rate": 85.0},
                "phase2_compliance": {"compliance_rate": 90.0},
                "batch_processing": {"success_rate": 95.0},
            }
        ]

        with patch("pandas.DataFrame.to_csv") as mock_to_csv:
            collector.export_metrics("test.csv", "csv")

            # Check that DataFrame.to_csv was called
            mock_to_csv.assert_called_once()

    def test_export_metrics_empty_history(self):
        """Test exporting metrics with empty history."""
        collector = FeaturesMetricsCollector()

        with patch.object(collector.logger, "warning") as mock_warning:
            collector.export_metrics("test.json", "json")

            # Should warn about no metrics
            mock_warning.assert_called_once()


class TestGlobalMetricsCollector:
    """Test global metrics collector instance."""

    def test_global_metrics_collector(self):
        """Test that global metrics collector is properly initialized."""
        assert metrics_collector is not None
        assert isinstance(metrics_collector, FeaturesMetricsCollector)
        assert metrics_collector.metrics_history == []
