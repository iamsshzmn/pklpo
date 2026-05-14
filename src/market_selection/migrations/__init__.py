"""Market Selection database migrations."""

import logging
import re
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent


_DOLLAR_QUOTE_PATTERN = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$")


def _split_sql_statements(sql: str) -> list[str]:
    """Split SQL script into statements, ignoring SQL comments."""
    statements: list[str] = []
    current: list[str] = []

    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False
    dollar_quote_tag: str | None = None

    i = 0
    while i < len(sql):
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < len(sql) else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
                current.append(char)
            i += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if dollar_quote_tag is not None:
            if sql.startswith(dollar_quote_tag, i):
                current.append(dollar_quote_tag)
                i += len(dollar_quote_tag)
                dollar_quote_tag = None
                continue
            current.append(char)
            i += 1
            continue

        if not in_single_quote and not in_double_quote:
            if char == "-" and next_char == "-":
                in_line_comment = True
                i += 2
                continue

            if char == "/" and next_char == "*":
                in_block_comment = True
                i += 2
                continue

            dollar_match = _DOLLAR_QUOTE_PATTERN.match(sql, i)
            if dollar_match:
                dollar_quote_tag = dollar_match.group(0)
                current.append(dollar_quote_tag)
                i += len(dollar_quote_tag)
                continue

        if char == "'" and not in_double_quote:
            if in_single_quote and next_char == "'":
                current.append("''")
                i += 2
                continue
            in_single_quote = not in_single_quote
            current.append(char)
            i += 1
            continue

        if char == '"' and not in_single_quote:
            if in_double_quote and next_char == '"':
                current.append('""')
                i += 2
                continue
            in_double_quote = not in_double_quote
            current.append(char)
            i += 1
            continue

        if char == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            i += 1
            continue

        current.append(char)
        i += 1

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)

    return statements


async def run_market_selection_migrations(session: AsyncSession) -> None:
    """
    Run all Market Selection SQL migrations in order.

    Migrations are idempotent (IF NOT EXISTS used throughout).
    """
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    try:
        async with session.begin():
            for migration_file in migration_files:
                logger.info(
                    "market_selection_migration migration_file=%s status=start",
                    migration_file.name,
                )
                sql = migration_file.read_text(encoding="utf-8")
                statements = _split_sql_statements(sql)

                for statement in statements:
                    await session.execute(text(statement))

                logger.info(
                    "market_selection_migration migration_file=%s status=success",
                    migration_file.name,
                )
    except Exception:
        logger.exception(
            "market_selection_migration migration_file=%s status=failed",
            migration_file.name if "migration_file" in locals() else "unknown",
        )
        raise

    logger.info("All Market Selection migrations completed")


async def check_tables_exist(session: AsyncSession) -> dict[str, bool]:
    """Check which market_selection tables exist."""
    tables = [
        "market_scores_tf",
        "market_universe",
        "market_universe_versions",
        "market_regime_history",
    ]

    result = {}
    for table in tables:
        query = text(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = :table_name
            )
        """
        )
        row = await session.execute(query, {"table_name": table})
        result[table] = bool(row.scalar())

    return result
