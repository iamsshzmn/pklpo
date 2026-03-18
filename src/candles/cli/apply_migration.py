"""CLI для применения SQL миграций.

Использование:
    python -m src.market_meta.cli.apply_migration 006 --dry-run
    python -m src.market_meta.cli.apply_migration 006 --apply
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine, text


def main() -> None:
    """Применяет SQL миграцию."""
    parser = argparse.ArgumentParser(description="Применение SQL миграций")
    parser.add_argument("migration", help="Номер миграции (например: 006)")
    parser.add_argument("--apply", action="store_true", help="Применить миграцию")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="URL базы данных (по умолчанию из DATABASE_URL)",
    )
    args = parser.parse_args()

    if not args.database_url:
        print("Ошибка: DATABASE_URL не задан")
        print("Установите переменную окружения или передайте --database-url")
        return

    # Ищем файл миграции
    migrations_dir = Path(__file__).parent.parent / "migrations"
    migration_files = list(migrations_dir.glob(f"{args.migration}*.sql"))

    if not migration_files:
        print(f"Миграция {args.migration} не найдена в {migrations_dir}")
        return

    migration_file = migration_files[0]
    sql_content = migration_file.read_text(encoding="utf-8")

    print(f"Миграция: {migration_file.name}")
    print("-" * 50)
    print(sql_content)
    print("-" * 50)

    if not args.apply:
        print("\n[DRY-RUN] Добавьте --apply для применения")
        return

    engine = create_engine(args.database_url)
    with engine.begin() as conn:
        # Выполняем SQL (без BEGIN/COMMIT — они в файле)
        # Убираем BEGIN/COMMIT так как begin() уже создаёт транзакцию
        clean_sql = sql_content.replace("BEGIN;", "").replace("COMMIT;", "")
        conn.execute(text(clean_sql))

    print("\n[OK] Миграция применена успешно")


if __name__ == "__main__":
    main()
