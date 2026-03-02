"""
Генерация отчётов о результатах бэктестинга.

Создаёт структурированный Markdown или HTML-отчёт с секциями:
  - Конфигурация запуска (RunContext, параметры модели)
  - Метрики производительности (SR, DSR, MaxDD, hit-rate, turnover)
  - Важность признаков (топ-N по MDA/MDI)
  - CPCV метрики по путям (распределение SR)
  - Кривые капитала (in-sample / out-of-sample PnL)

Все отчёты привязаны к run_id через RunContext для воспроизводимости.

Использование::

    ctx = RunContext.create({"bars_mode": "dollar", "triple_pt": 0.02})
    config = ReportConfig(
        run_context=ctx,
        returns=pnl_array,
        sharpe=1.45,
        dsr=0.82,
        feature_importance=importance_series,
        cpcv_metrics=metrics_df,
    )
    html = generate_report(config, fmt="html")
    Path("reports/report.html").write_text(html)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from src.core.run_context import RunContext


@dataclass
class ReportConfig:
    """
    Конфигурация входных данных для генерации отчёта.

    Attributes:
        run_context:       RunContext запуска (run_id, version, params_hash).
        returns:           Массив периодических доходностей (для кривой капитала).
        sharpe:            Коэффициент Шарпа (аннуализированный).
        dsr:               Deflated Sharpe Ratio.
        dsr_p_value:       p-value из DSR (вероятность случайности SR).
        max_drawdown:      Максимальная просадка (отрицательное число, e.g. -0.15).
        hit_rate:          Доля выигрышных сделок (0..1).
        turnover:          Оборот (средне-дневной, если применимо).
        feature_importance: pd.Series[feature_name -> importance] из MDI/MDA.
        cpcv_metrics:      DataFrame из CombinatorialPurgedCV.get_path_metrics().
        model_params:      Словарь параметров модели (base_model, cv, feature_selection).
        n_top_features:    Число топ-признаков для отображения в отчёте.
    """

    run_context: RunContext
    returns: np.ndarray | pd.Series | None = None
    sharpe: float | None = None
    dsr: float | None = None
    dsr_p_value: float | None = None
    max_drawdown: float | None = None
    hit_rate: float | None = None
    turnover: float | None = None
    feature_importance: pd.Series | None = None
    cpcv_metrics: pd.DataFrame | None = None
    model_params: dict[str, Any] | None = None
    n_top_features: int = 20


def generate_report(
    config: ReportConfig,
    fmt: Literal["markdown", "html"] = "markdown",
) -> str:
    """
    Генерирует отчёт о результатах бэктестинга.

    Args:
        config: ReportConfig с метриками и метаданными.
        fmt:    Формат вывода: "markdown" или "html".

    Returns:
        Строка с отчётом в заданном формате.
    """
    md = _build_markdown(config)
    if fmt == "html":
        return _markdown_to_html(md, config)
    return md


def _build_markdown(config: ReportConfig) -> str:
    """Строит Markdown-отчёт из ReportConfig."""
    ctx = config.run_context
    lines: list[str] = []

    # ---------------------------------------------------------------------------
    # Заголовок
    # ---------------------------------------------------------------------------
    lines += [
        "# Backtest Report",
        "",
        f"**Run ID:** `{ctx.run_id}`",
        f"**Version:** {ctx.algo_version}",
        f"**Params Hash:** `{ctx.params_hash[:16]}...`",
        f"**Created:** {ctx.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
    ]

    # ---------------------------------------------------------------------------
    # Конфигурация
    # ---------------------------------------------------------------------------
    lines += [
        "## Configuration",
        "",
    ]
    if config.model_params:
        lines += [
            "| Parameter | Value |",
            "|-----------|-------|",
        ]
        for k, v in config.model_params.items():
            lines.append(f"| {k} | {v} |")
        lines.append("")
    else:
        lines += ["*Параметры модели не заданы.*", ""]

    # ---------------------------------------------------------------------------
    # Performance Metrics
    # ---------------------------------------------------------------------------
    lines += [
        "## Performance Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
    ]

    def _fmt(val: float | None, decimals: int = 4, pct: bool = False) -> str:
        if val is None:
            return "—"
        if pct:
            return f"{val * 100:.2f}%"
        return f"{val:.{decimals}f}"

    lines += [
        f"| Sharpe Ratio | {_fmt(config.sharpe, 4)} |",
        f"| DSR | {_fmt(config.dsr, 4)} |",
        f"| DSR p-value | {_fmt(config.dsr_p_value, 4)} |",
        f"| Max Drawdown | {_fmt(config.max_drawdown, 4, pct=True)} |",
        f"| Hit Rate | {_fmt(config.hit_rate, 4, pct=True)} |",
        f"| Turnover | {_fmt(config.turnover, 4)} |",
        "",
    ]

    if config.returns is not None:
        rets = np.asarray(config.returns, dtype=float)
        rets = rets[np.isfinite(rets)]
        if len(rets) > 0:
            cum_return = float(np.prod(1.0 + rets) - 1.0)
            lines += [
                "### Returns Summary",
                "",
                f"- **Periods:** {len(rets)}",
                f"- **Cumulative Return:** {cum_return * 100:.2f}%",
                f"- **Mean Period Return:** {float(np.mean(rets)) * 100:.4f}%",
                f"- **Std Period Return:** {float(np.std(rets, ddof=1)) * 100:.4f}%",
                "",
            ]

    # ---------------------------------------------------------------------------
    # Feature Importance
    # ---------------------------------------------------------------------------
    lines += ["## Feature Importance", ""]

    if config.feature_importance is not None and len(config.feature_importance) > 0:
        top_n = config.feature_importance.head(config.n_top_features)
        lines += [
            f"Top {len(top_n)} features (by importance):",
            "",
            "| Rank | Feature | Importance |",
            "|------|---------|------------|",
        ]
        for rank, (feat, imp) in enumerate(top_n.items(), 1):
            lines.append(f"| {rank} | {feat} | {float(imp):.6f} |")
        lines.append("")
    else:
        lines += ["*Данные о важности признаков не заданы.*", ""]

    # ---------------------------------------------------------------------------
    # CPCV Path Metrics
    # ---------------------------------------------------------------------------
    lines += ["## CPCV Path Metrics", ""]

    if config.cpcv_metrics is not None and len(config.cpcv_metrics) > 0:
        df = config.cpcv_metrics
        lines += [
            f"**Paths:** {len(df)}",
            f"**Score Mean:** {float(df['score'].mean()):.4f}",
            f"**Score Std:** {float(df['score'].std()):.4f}",
            f"**Score Min/Max:** {float(df['score'].min()):.4f} / {float(df['score'].max()):.4f}",
            "",
            "| Path | Score | N Train | N Test |",
            "|------|-------|---------|--------|",
        ]
        for _, row in df.iterrows():
            lines.append(
                f"| {int(row['path_id'])} | {float(row['score']):.4f} | "
                f"{int(row['n_train'])} | {int(row['n_test'])} |"
            )
        lines.append("")
    else:
        lines += ["*CPCV метрики не заданы.*", ""]

    return "\n".join(lines)


def _markdown_to_html(md: str, config: ReportConfig) -> str:
    """
    Конвертирует Markdown в базовый HTML.

    Обрабатывает: заголовки (#, ##, ###), таблицы (|col|col|), текст.
    """
    ctx = config.run_context
    html_lines = [
        "<!DOCTYPE html>",
        "<html lang='ru'>",
        "<head>",
        f"  <title>Backtest Report — {ctx.run_id[:8]}</title>",
        "  <meta charset='utf-8'>",
        "  <style>",
        "    body { font-family: monospace; max-width: 960px; margin: 40px auto; padding: 0 20px; }",
        "    h1 { border-bottom: 3px solid #2e7d32; }",
        "    h2 { border-bottom: 1px solid #388e3c; margin-top: 2em; }",
        "    table { border-collapse: collapse; width: 100%; margin: 1em 0; }",
        "    th, td { border: 1px solid #ccc; padding: 8px 12px; text-align: left; }",
        "    th { background-color: #2e7d32; color: white; }",
        "    tr:nth-child(even) { background-color: #f5f5f5; }",
        "    code { background: #eee; padding: 2px 4px; border-radius: 3px; }",
        "    strong { color: #1b5e20; }",
        "  </style>",
        "</head>",
        "<body>",
    ]

    in_table = False
    for line in md.split("\n"):
        stripped = line.strip()

        if stripped.startswith("### "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith("## "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("# "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped[1:-1].split("|")]
            # Separator row (---|---): skip
            if all(set(c.replace("-", "").replace(":", "").replace(" ", "")) == set() for c in cells):
                continue
            if not in_table:
                html_lines.append("<table>")
                in_table = True
                html_lines.append(
                    "<tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>"
                )
            else:
                html_lines.append(
                    "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
                )
        elif stripped.startswith("- "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            text = stripped[2:].replace("**", "<strong>", 1).replace("**", "</strong>", 1)
            html_lines.append(f"<li>{text}</li>")
        elif stripped.startswith("**") and stripped.endswith("**"):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            text = stripped[2:-2]
            html_lines.append(f"<p><strong>{text}</strong></p>")
        elif stripped:
            if in_table:
                html_lines.append("</table>")
                in_table = False
            # Inline formatting
            text = stripped
            # **bold** → <strong>bold</strong>
            while "**" in text:
                text = text.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
            # `code` → <code>code</code>
            while "`" in text:
                text = text.replace("`", "<code>", 1).replace("`", "</code>", 1)
            html_lines.append(f"<p>{text}</p>")
        else:
            if in_table:
                html_lines.append("</table>")
                in_table = False

    if in_table:
        html_lines.append("</table>")

    html_lines += ["</body>", "</html>"]
    return "\n".join(html_lines)
