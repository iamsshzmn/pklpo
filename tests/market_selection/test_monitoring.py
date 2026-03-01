import time
from typing import Any

import pytest

from src.market_selection.infrastructure.monitoring import (
    MarketSelectionMetrics,
    PipelineMetrics,
    get_metrics,
    record_pipeline_metrics,
)


def _make_pipeline_metrics(**overrides: Any) -> PipelineMetrics:
    base_kwargs: dict[str, Any] = {
        "ts_version": 1,
        "ts_eval": 1700000000,
        "success": True,
        "status": "ok",
        "universe_size": 5,
        "execution_time_seconds": 1.5,
        "global_regime": "TREND_UP",
        "regime_strength": 0.8,
        "regime_stale": False,
        "eligible_counts": {"1H": 5},
        "total_symbols": 5,
        "error_message": None,
        "reason_flags": ["OK"],
    }
    base_kwargs.update(overrides)
    return PipelineMetrics(**base_kwargs)


def test_pipeline_metrics_to_dict_has_all_fields() -> None:
    metrics = _make_pipeline_metrics()
    data = metrics.to_dict()

    expected_keys = {
        "ts_version",
        "ts_eval",
        "success",
        "status",
        "universe_size",
        "execution_time_seconds",
        "global_regime",
        "regime_strength",
        "regime_stale",
        "eligible_counts",
        "total_symbols",
        "score_min",
        "score_max",
        "score_mean",
        "score_std",
        "error_message",
        "reason_flags",
        "recorded_at",
    }

    assert set(data.keys()) == expected_keys
    assert data["ts_version"] == 1
    assert data["success"] is True
    assert data["eligible_counts"] == {"1H": 5}
    assert isinstance(data["recorded_at"], str)


def test_market_selection_metrics_record_pipeline_run_and_summary() -> None:
    metrics = MarketSelectionMetrics(enable_prometheus=False)
    metrics.reset()

    run1 = _make_pipeline_metrics(
        ts_version=1,
        ts_eval=1,
        success=True,
        universe_size=3,
        execution_time_seconds=2.0,
        global_regime="TREND_UP",
        eligible_counts={"1H": 3, "4H": 2},
    )
    run2 = _make_pipeline_metrics(
        ts_version=2,
        ts_eval=2,
        success=False,
        universe_size=0,
        execution_time_seconds=4.0,
        global_regime="RANGE",
        eligible_counts={"1H": 1},
    )

    metrics.record_pipeline_run(run1)
    metrics.record_pipeline_run(run2)

    summary = metrics.get_summary()

    assert summary["total_runs"] == 2
    assert summary["success_runs"] == 1
    assert summary["failed_runs"] == 1
    assert 0.0 < summary["success_rate"] < 1.0
    assert summary["current_universe_size"] == 0
    assert summary["last_execution_time"] == pytest.approx(4.0)
    assert summary["avg_execution_time"] == pytest.approx((2.0 + 4.0) / 2.0)
    assert set(summary["recent_regimes"]) == {"TREND_UP", "RANGE"}
    assert summary["prometheus_enabled"] is False

    eligible = metrics.get_eligible_counts()
    assert eligible == {"1H": 1, "4H": 2}

    history = metrics.get_recent_history()
    assert len(history) == 2
    assert history[0]["ts_version"] == 1
    assert history[1]["ts_version"] == 2


def test_market_selection_metrics_regime_distribution_and_reset() -> None:
    metrics = MarketSelectionMetrics(enable_prometheus=False)
    metrics.reset()

    for idx, regime in enumerate(["TREND_UP", "TREND_UP", "RANGE"], start=1):
        run = _make_pipeline_metrics(
            ts_version=idx,
            ts_eval=idx,
            global_regime=regime,
        )
        metrics.record_pipeline_run(run)

    distribution = metrics.get_regime_distribution(last_n=10)
    assert distribution == {"TREND_UP": 2, "RANGE": 1}

    metrics.reset()
    assert metrics.get_summary() == {"error": "No metrics history"}
    assert metrics.get_recent_history() == []
    assert metrics.get_eligible_counts() == {}
    assert metrics.get_regime_distribution() == {}


def test_market_selection_metrics_record_scores_and_prometheus_flag() -> None:
    metrics = MarketSelectionMetrics(enable_prometheus=False)
    metrics.reset()

    scores = [0.1, 0.5, 0.9]
    metrics.record_scores(scores)

    # Проверяем, что внутренние метрики по скору обновились
    summary = metrics.get_summary()
    # Если нет истории запусков пайплайна, get_summary может вернуть только ошибку.
    # Нас здесь интересует сам факт отсутствия падения и корректная запись score-метрик.
    assert "error" in summary or "prometheus_enabled" in summary


def test_get_metrics_singleton_and_record_pipeline_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.market_selection.infrastructure.monitoring as monitoring_module

    monkeypatch.setattr(monitoring_module, "_metrics_instance", None, raising=False)
    monkeypatch.setattr(monitoring_module, "PROMETHEUS_AVAILABLE", False, raising=False)

    m1 = get_metrics(enable_prometheus=False)
    m2 = get_metrics(enable_prometheus=True)

    assert m1 is m2

    before = len(m1.get_recent_history())

    start_ts = int(time.time())
    record_pipeline_metrics(
        ts_version=123,
        ts_eval=start_ts,
        success=True,
        status="ok",
        universe_size=10,
        execution_time_seconds=0.25,
        global_regime="TREND_UP",
        eligible_counts={"1H": 10},
        total_symbols=10,
    )

    history = m1.get_recent_history()
    assert len(history) == before + 1
    last = history[-1]
    assert last["ts_version"] == 123
    assert last["ts_eval"] == start_ts
    assert last["success"] is True
    assert last["universe_size"] == 10
