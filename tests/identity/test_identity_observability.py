from __future__ import annotations

from datetime import UTC, datetime

import pytest


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def test_identity_observer_metric_labels_are_allowlisted() -> None:
    from src.identity.observability import (
        ALLOWED_IDENTITY_METRIC_LABELS,
        IdentityBuildObserver,
    )

    observer = IdentityBuildObserver()
    labels = observer.metric_labels(
        status="failed",
        error_type="RuntimeError",
        series_id="TON-USDT-SWAP",
        timeframe="*",
        forbidden_text="raw sql and stack trace",
    )

    assert set(labels) == ALLOWED_IDENTITY_METRIC_LABELS
    assert labels == {
        "series_id": "TON-USDT-SWAP",
        "timeframe": "*",
        "component": "identity_build",
        "status": "failed",
        "error_type": "RuntimeError",
    }


def test_identity_prometheus_metrics_use_only_allowed_labels() -> None:
    from src.identity.observability import (
        ALLOWED_IDENTITY_METRIC_LABELS,
        IDENTITY_PROMETHEUS_METRICS,
    )

    assert set(IDENTITY_PROMETHEUS_METRICS) == {
        "pklpo_identity_build_duration_seconds",
        "pklpo_identity_build_rows_total",
        "pklpo_identity_build_errors_total",
        "pklpo_identity_build_gap_count",
    }
    for metric in IDENTITY_PROMETHEUS_METRICS.values():
        assert set(metric["labels"]) <= ALLOWED_IDENTITY_METRIC_LABELS
        assert "exception" not in metric["labels"]
        assert "message" not in metric["labels"]
        assert "sql" not in metric["labels"]


def test_error_message_hash_is_stable_and_does_not_expose_message() -> None:
    from src.identity.observability import error_message_hash

    message = "database password leaked in raw exception"

    assert error_message_hash(message) == error_message_hash(message)
    assert error_message_hash(message) != message
    assert "password" not in error_message_hash(message)


@pytest.mark.asyncio
async def test_identity_build_job_emits_success_observability() -> None:
    from src.identity.application.build_job import IdentityBuildJob
    from src.identity.domain import IdentityBuildInputs, RawInstrument
    from src.identity.observability import IdentityBuildObserver

    class _Repository:
        async def load_inputs(self, as_of):
            return IdentityBuildInputs(
                instruments=[
                    RawInstrument(symbol="BTC-USDT-SWAP", venue="OKX", inst_type="SWAP")
                ],
                successions=[],
                gap_classifications=[],
            )

        async def publish_snapshot(self, snapshot, context):
            return None

        async def enqueue_recalc(self, series_ids, context):
            return None

    observer = IdentityBuildObserver()
    result = await IdentityBuildJob(_Repository(), observer=observer).run(
        as_of=_ts("2026-07-03T00:00:00+00:00"),
        run_id="run-success",
        algo_version="test",
        params_hash="hash",
    )

    assert result.series_count == 1
    assert [event["stage"] for event in observer.events] == ["start", "finish"]
    assert observer.events[-1]["status"] == "success"
    assert observer.events[-1]["run_id"] == "run-success"
    assert observer.metrics[-1]["labels"]["status"] == "success"
    assert observer.metrics[-1]["rows_written"] == 1


@pytest.mark.asyncio
async def test_identity_build_job_hashes_failure_for_logs_metrics_and_audit() -> None:
    from src.identity.application.build_job import IdentityBuildJob
    from src.identity.observability import IdentityBuildObserver

    class _Repository:
        def __init__(self) -> None:
            self.failures = []

        async def load_inputs(self, as_of):
            raise RuntimeError("raw sql password stack trace")

        async def publish_snapshot(self, snapshot, context):
            raise AssertionError("not reached")

        async def enqueue_recalc(self, series_ids, context):
            raise AssertionError("not reached")

        async def record_failure(self, context, error_type, error_hash):
            self.failures.append((context, error_type, error_hash))

    observer = IdentityBuildObserver()
    repository = _Repository()

    with pytest.raises(RuntimeError):
        await IdentityBuildJob(repository, observer=observer).run(
            as_of=_ts("2026-07-03T00:00:00+00:00"),
            run_id="run-failed",
            algo_version="test",
            params_hash="hash",
        )

    assert observer.events[-1]["status"] == "failed"
    assert observer.events[-1]["error_type"] == "RuntimeError"
    assert observer.events[-1]["error_message_hash"] != "raw sql password stack trace"
    assert "password" not in observer.events[-1]["error_message_hash"]
    assert observer.metrics[-1]["labels"] == {
        "series_id": "*",
        "timeframe": "*",
        "component": "identity_build",
        "status": "failed",
        "error_type": "RuntimeError",
    }
    assert repository.failures[0][1] == "RuntimeError"
    assert repository.failures[0][2] == observer.events[-1]["error_message_hash"]


def test_continuous_build_observer_metric_labels_are_allowlisted() -> None:
    """§17.4 'continuous build' row: same bounded-label discipline as
    identity build, but under its own component label so the two jobs are
    never conflated in a Grafana/Loki query."""
    from src.identity.observability import (
        ALLOWED_CONTINUOUS_BUILD_METRIC_LABELS,
        ContinuousBuildObserver,
    )

    observer = ContinuousBuildObserver()
    labels = observer.metric_labels(
        status="failed",
        error_type="RuntimeError",
        series_id="TON-USDT-SWAP",
        timeframe="*",
        forbidden_text="raw sql and stack trace",
    )

    assert set(labels) == ALLOWED_CONTINUOUS_BUILD_METRIC_LABELS
    assert labels == {
        "series_id": "TON-USDT-SWAP",
        "timeframe": "*",
        "component": "continuous_build",
        "status": "failed",
        "error_type": "RuntimeError",
    }


def test_continuous_build_prometheus_metrics_use_only_allowed_labels() -> None:
    from src.identity.observability import (
        ALLOWED_CONTINUOUS_BUILD_METRIC_LABELS,
        CONTINUOUS_BUILD_PROMETHEUS_METRICS,
    )

    assert set(CONTINUOUS_BUILD_PROMETHEUS_METRICS) == {
        "pklpo_continuous_build_duration_seconds",
        "pklpo_continuous_build_rows_total",
        "pklpo_continuous_build_errors_total",
        "pklpo_continuous_build_segment_count",
        "pklpo_continuous_build_gap_count",
    }
    for metric in CONTINUOUS_BUILD_PROMETHEUS_METRICS.values():
        assert set(metric["labels"]) <= ALLOWED_CONTINUOUS_BUILD_METRIC_LABELS
        assert "exception" not in metric["labels"]
        assert "message" not in metric["labels"]
        assert "sql" not in metric["labels"]
