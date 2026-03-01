"""
Тесты для src/backtest/report.py и src/cli/commands/metrics.py.

Все тесты работают без подключения к БД.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.report import ReportConfig, generate_report
from src.cli.commands.metrics import format_metrics_table
from src.core.run_context import RunContext

# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------


def _make_config(
    with_returns: bool = True,
    with_importance: bool = True,
    with_cpcv: bool = True,
    with_model_params: bool = True,
) -> ReportConfig:
    """Создаёт ReportConfig с реалистичными синтетическими данными."""
    ctx = RunContext.create({"bars_mode": "dollar", "triple_pt": 0.02, "cv": "purged"})

    rng = np.random.default_rng(42)
    returns = rng.normal(0.001, 0.02, 252) if with_returns else None

    importance = (
        pd.Series(
            [0.25, 0.20, 0.15, 0.10, 0.08, 0.07, 0.05, 0.04, 0.03, 0.03],
            index=[f"feature_{i}" for i in range(10)],
            name="mda_importance",
        )
        if with_importance
        else None
    )

    cpcv_metrics = (
        pd.DataFrame(
            {
                "path_id": range(15),
                "score": rng.uniform(0.5, 0.7, 15),
                "n_train": [180] * 15,
                "n_test": [40] * 15,
            }
        )
        if with_cpcv
        else None
    )

    model_params = (
        {"base_model": "RandomForestClassifier", "n_estimators": 100, "cv": "PurgedKFold(5)"}
        if with_model_params
        else None
    )

    return ReportConfig(
        run_context=ctx,
        returns=returns,
        sharpe=1.45,
        dsr=0.82,
        dsr_p_value=0.18,
        max_drawdown=-0.12,
        hit_rate=0.56,
        turnover=0.35,
        feature_importance=importance,
        cpcv_metrics=cpcv_metrics,
        model_params=model_params,
        n_top_features=5,
    )


# ---------------------------------------------------------------------------
# Генерация отчёта
# ---------------------------------------------------------------------------


def test_report_generation() -> None:
    """Генерация Markdown-отчёта без ошибок."""
    config = _make_config()
    report = generate_report(config, fmt="markdown")

    assert isinstance(report, str)
    assert len(report) > 100


def test_report_generation_html() -> None:
    """Генерация HTML-отчёта без ошибок."""
    config = _make_config()
    html = generate_report(config, fmt="html")

    assert isinstance(html, str)
    assert len(html) > 100
    assert "<html" in html
    assert "</html>" in html


def test_report_sections() -> None:
    """Все обязательные секции присутствуют в Markdown-отчёте."""
    config = _make_config()
    report = generate_report(config, fmt="markdown")

    required_sections = [
        "## Configuration",
        "## Performance Metrics",
        "## Feature Importance",
        "## CPCV Path Metrics",
    ]
    for section in required_sections:
        assert section in report, f"Секция '{section}' отсутствует в отчёте"


def test_report_run_context() -> None:
    """Отчёт содержит run_id из RunContext."""
    ctx = RunContext.create({"test": "report_run_context"})
    config = ReportConfig(run_context=ctx)
    report = generate_report(config, fmt="markdown")

    assert ctx.run_id in report, "run_id не найден в отчёте"
    assert ctx.algo_version in report


def test_report_html_run_context() -> None:
    """HTML-отчёт содержит run_id из RunContext."""
    ctx = RunContext.create({"test": "html_run_context"})
    config = ReportConfig(run_context=ctx)
    html = generate_report(config, fmt="html")

    assert ctx.run_id in html


def test_report_metrics_values() -> None:
    """Значения метрик корректно отображаются в отчёте."""
    ctx = RunContext.create()
    config = ReportConfig(
        run_context=ctx,
        sharpe=1.2345,
        dsr=0.8765,
        max_drawdown=-0.1234,
        hit_rate=0.567,
    )
    report = generate_report(config, fmt="markdown")

    assert "1.2345" in report
    assert "0.8765" in report
    # max_drawdown отображается как %: -12.34%
    assert "-12.34%" in report
    # hit_rate как %: 56.70%
    assert "56.70%" in report


def test_report_feature_importance() -> None:
    """Топ-N признаков отображаются в отчёте."""
    ctx = RunContext.create()
    importance = pd.Series(
        [0.5, 0.3, 0.2],
        index=["best_feature", "second_feature", "third_feature"],
    )
    config = ReportConfig(
        run_context=ctx,
        feature_importance=importance,
        n_top_features=2,
    )
    report = generate_report(config)

    assert "best_feature" in report
    assert "second_feature" in report
    # n_top_features=2: третий не должен попасть
    assert "third_feature" not in report


def test_report_cpcv_metrics() -> None:
    """CPCV метрики отображаются корректно."""
    ctx = RunContext.create()
    cpcv = pd.DataFrame(
        {
            "path_id": [0, 1, 2],
            "score": [0.61, 0.58, 0.64],
            "n_train": [200, 200, 200],
            "n_test": [50, 50, 50],
        }
    )
    config = ReportConfig(run_context=ctx, cpcv_metrics=cpcv)
    report = generate_report(config)

    assert "Paths:** 3" in report
    assert "0.6100" in report  # первый path score


def test_report_returns_summary() -> None:
    """Returns summary секция отображается при заданных returns."""
    ctx = RunContext.create()
    returns = np.array([0.01, -0.005, 0.02, -0.01, 0.015])
    config = ReportConfig(run_context=ctx, returns=returns)
    report = generate_report(config)

    assert "Returns Summary" in report
    assert "Periods:** 5" in report


def test_report_empty_config() -> None:
    """Отчёт генерируется без ошибок даже при минимальном конфиге."""
    ctx = RunContext.create()
    config = ReportConfig(run_context=ctx)
    report = generate_report(config)

    assert isinstance(report, str)
    assert ctx.run_id in report
    assert "не заданы" in report  # Placeholder для отсутствующих данных


# ---------------------------------------------------------------------------
# CLI: metrics show
# ---------------------------------------------------------------------------


def test_metrics_cli_format_table() -> None:
    """format_metrics_table возвращает таблицу с правильными значениями."""
    ctx = RunContext.create()
    config = ReportConfig(
        run_context=ctx,
        sharpe=1.2300,
        dsr=0.8100,
        max_drawdown=-0.15,
        hit_rate=0.58,
    )
    table = format_metrics_table(config)

    assert isinstance(table, str)
    assert "Sharpe Ratio" in table
    assert "1.2300" in table
    assert "DSR" in table
    assert "0.8100" in table
    assert "-15.00%" in table  # max_drawdown as %
    assert "58.00%" in table   # hit_rate as %


def test_metrics_cli_none_values() -> None:
    """format_metrics_table корректно обрабатывает None значения (отображает —)."""
    ctx = RunContext.create()
    config = ReportConfig(run_context=ctx)  # все метрики = None
    table = format_metrics_table(config)

    # Все значения должны быть —
    assert table.count("—") >= 5


def test_metrics_cmd_registered() -> None:
    """Команда 'metrics' успешно регистрируется в argparse."""
    import argparse

    from src.cli.commands.metrics import register

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers)

    # Должна успешно парсить
    args = parser.parse_args(["metrics", "show", "--run-id", "test-run-id"])
    assert args.run_id == "test-run-id"
