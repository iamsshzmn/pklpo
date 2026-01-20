#!/usr/bin/env python3
"""
Аудит индикаторных колонок по логам и схеме БД.

Источник истины:
- Лог smoke_validate: METRICS (present_features/missing_features/extra_features)
- Лог features_run: строки "🔍 <feature>: x/1000"
- Схема канона из SchemaManager (indicators_schema.yml)
- Факт наличия колонок в БД (information_schema)

Вывод: список к восстановлению и к удалению (dry-run).
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.features.schema.schema_manager import SchemaManager  # noqa: E402

DOCS_DIR = Path("docs")


def _find_latest(path_glob: str) -> Path | None:
    paths = sorted(
        DOCS_DIR.glob(path_glob), key=lambda p: p.stat().st_mtime, reverse=True
    )
    return paths[0] if paths else None


def parse_smoke_metrics(smoke_log: Path) -> tuple[set[str], set[str], set[str]]:
    present: set[str] = set()
    missing: set[str] = set()
    extra: set[str] = set()
    metrics_line: str | None = None
    content = smoke_log.read_text(encoding="utf-8", errors="ignore")
    # Ищем строку с METRICS, может быть разбита на несколько строк в логе
    idx = content.find("[features_calc] METRICS {")
    if idx >= 0:
        # Берём от начала JSON до конца (ищем закрывающую скобку на том же уровне)
        json_start = content.find("{", idx)
        if json_start >= 0:
            brace_count = 0
            end_pos = json_start
            for i, char in enumerate(content[json_start:], start=json_start):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i + 1
                        break
            metrics_line = content[json_start:end_pos]
    if not metrics_line:
        return present, missing, extra
    # Логи могут содержать нестрогий JSON (одинарные кавычки). Фоллбек на ast.literal_eval.
    try:
        data = json.loads(metrics_line)
    except json.JSONDecodeError:
        try:
            data = ast.literal_eval(metrics_line)
        except Exception:
            return present, missing, extra
    cov = data.get("coverage_analysis", {})
    present = set(cov.get("present_features", []) or [])
    missing = set(cov.get("missing_features", []) or [])
    extra = set(cov.get("extra_features", []) or [])
    return present, missing, extra


def parse_features_run(features_log: Path) -> set[str]:
    computed: set[str] = set()
    rx = re.compile(r"\|\s+🔍\s+([a-zA-Z0-9_]+):\s+\d+/\d+")
    for line in features_log.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = rx.search(line)
        if m:
            computed.add(m.group(1))
    return computed


async def load_db_columns(database_url: str) -> set[str]:
    eng = create_async_engine(database_url, future=True)
    async with eng.begin() as conn:
        res = await conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='indicators'
                """
            )
        )
        return {row[0] for row in res.fetchall()}


def decide_actions(
    present: set[str],
    missing: set[str],
    extra: set[str],
    computed: set[str],
    db_cols: set[str],
    canonical: set[str],
) -> tuple[list[str], list[str]]:
    to_restore: list[str] = []
    to_drop: list[str] = []

    # К восстановлению: missing ∩ (computed ∪ canonical) и отсутствует в БД
    for name in sorted(missing):
        if (name in computed or name in canonical) and name not in db_cols:
            to_restore.append(name)

    # К удалению: есть в БД, не канон, не present, не computed
    for col in sorted(db_cols):
        if col in {"symbol", "timeframe", "timestamp", "calculated_at"}:
            continue
        if (col not in canonical) and (col not in present) and (col not in computed):
            to_drop.append(col)

    return to_restore, to_drop


def main() -> int:
    ap = argparse.ArgumentParser(description="Аудит колонок indicators по логам")
    ap.add_argument(
        "--database-url",
        default=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://pklpo_user:strongpassword@localhost:5432/pklpo",
        ),
    )
    ap.add_argument(
        "--smoke-log",
        help="Путь к логу smoke_validate. Если не задан, берётся последний из docs/*smoke*",
    )
    ap.add_argument(
        "--features-log",
        help="Путь к логу features_run. Если не задан, берётся последний из docs/*features_run*",
    )
    args = ap.parse_args()

    smoke = (
        Path(args.smoke_log)
        if args.smoke_log
        else _find_latest("dag_id=features_calc*_smoke_validate_features_attempt=1.log")
    )
    feat = (
        Path(args.features_log)
        if args.features_log
        else _find_latest("dag_id=features_calc*_features_run_attempt=1.log")
    )
    if not smoke or not smoke.exists() or not feat or not feat.exists():
        print(
            "[ERROR] Не найдены логи. Укажите --smoke-log и --features-log, либо положите файлы в docs/."
        )
        print(
            "Пример: --smoke-log docs/dag_id=..._smoke_validate_features_attempt=1.log --features-log docs/dag_id=..._features_run_attempt=1.log"
        )
        return 2

    present, missing, extra = parse_smoke_metrics(smoke)
    computed = parse_features_run(feat)

    schema = SchemaManager()
    canonical = schema.get_all_columns()

    import asyncio

    db_cols = asyncio.run(load_db_columns(args.database_url))

    to_restore, to_drop = decide_actions(
        present, missing, extra, computed, db_cols, canonical
    )

    print("\n=== AUDIT SUMMARY ===")
    print(
        f"Smoke present: {len(present)} | missing: {len(missing)} | extra: {len(extra)}"
    )
    print(
        f"Features computed: {len(computed)} | DB cols: {len(db_cols)} | Canonical: {len(canonical)}"
    )
    print("\n-> ВОССТАНОВИТЬ (отсутствуют в БД, но рассчитываются/канон):")
    for n in to_restore or ["<пусто>"]:
        print(f"  - {n}")
    print("\n-> УДАЛИТЬ (в БД, не канон, не present, не computed):")
    for n in to_drop or ["<пусто>"]:
        print(f"  - {n}")
    print("====================\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
