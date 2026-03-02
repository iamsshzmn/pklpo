"""
CLI команда metrics: вывод и экспорт quant-метрик бэктеста.

Использование:
    python -m src.cli.main metrics show --run-id <uuid>
    python -m src.cli.main metrics show --run-id <uuid> --export html > report.html
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def format_metrics_table(config: Any) -> str:
    """
    Форматирует ключевые метрики из ReportConfig в текстовую таблицу.

    Args:
        config: ReportConfig с полями sharpe, dsr, max_drawdown, hit_rate, turnover.

    Returns:
        Строка с таблицей метрик.
    """
    rows = [
        ("Metric", "Value"),
        ("-" * 25, "-" * 12),
    ]

    def _v(val: float | None, decimals: int = 4, pct: bool = False) -> str:
        if val is None:
            return "—"
        if pct:
            return f"{val * 100:.2f}%"
        return f"{val:.{decimals}f}"

    rows += [
        ("Sharpe Ratio", _v(config.sharpe, 4)),
        ("DSR", _v(config.dsr, 4)),
        ("DSR p-value", _v(config.dsr_p_value, 4)),
        ("Max Drawdown", _v(config.max_drawdown, 4, pct=True)),
        ("Hit Rate", _v(config.hit_rate, 4, pct=True)),
        ("Turnover", _v(config.turnover, 4)),
    ]

    lines = []
    for label, value in rows:
        lines.append(f"{label:<25} {value:<12}")

    return "\n".join(lines)


def register(subparsers: Any) -> None:
    """Регистрация команды metrics в CLI."""
    p = subparsers.add_parser(
        "metrics",
        help="Вывод и экспорт quant-метрик бэктеста",
    )
    sub = p.add_subparsers(dest="metrics_cmd", required=True)

    # metrics show
    show_p = sub.add_parser(
        "show",
        help="Показать таблицу метрик для заданного run-id",
    )
    show_p.add_argument(
        "--run-id",
        required=True,
        help="Run ID из RunContext (UUID v4)",
    )
    show_p.add_argument(
        "--export",
        choices=["html", "markdown"],
        default=None,
        help="Экспорт отчёта в HTML или Markdown (вывод в stdout)",
    )
    show_p.set_defaults(func=_cmd_show)


def _cmd_show(args: Any) -> int:
    """
    Обработчик команды `metrics show`.

    Загружает RunContext по run_id и выводит метрики.
    """
    from src.backtest.report import ReportConfig, generate_report
    from src.core.run_context import RunContext

    run_id = args.run_id
    logger.info("Загрузка метрик для run_id=%s", run_id)

    # Восстанавливаем RunContext по run_id
    ctx = RunContext.from_run_id(run_id)

    config = ReportConfig(run_context=ctx)

    if args.export:
        report = generate_report(config, fmt=args.export)
        print(report)
    else:
        table = format_metrics_table(config)
        print(f"\nMetrics for run_id: {run_id}")
        print(table)

    return 0
