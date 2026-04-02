from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from src.logging import LogCategory, Verbosity, get_category_logger, should_log

logger = get_category_logger(LogCategory.INSERT)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def get_numeric_columns(model_class: Any) -> set[str]:
    """Return numeric column names for a SQLAlchemy Table or ORM model."""
    numeric_column_names = set()

    if hasattr(model_class, "columns"):
        for col_name, col in model_class.columns.items():
            from sqlalchemy.types import REAL, BigInteger, Float, Integer, Numeric

            col_type = col.type
            if isinstance(col_type, Numeric | Float | Integer | BigInteger | REAL):
                numeric_column_names.add(col_name)
            elif hasattr(col_type, "__class__"):
                type_str = str(col_type).upper()
                if any(
                    t in type_str
                    for t in (
                        "NUMERIC",
                        "DECIMAL",
                        "DOUBLE PRECISION",
                        "REAL",
                        "FLOAT",
                        "INTEGER",
                        "BIGINT",
                        "SMALLINT",
                    )
                ):
                    numeric_column_names.add(col_name)
    elif hasattr(model_class, "__table__"):
        for col_name, col in model_class.__table__.columns.items():
            from sqlalchemy.types import REAL, BigInteger, Float, Integer, Numeric

            col_type = col.type
            if isinstance(col_type, Numeric | Float | Integer | BigInteger | REAL):
                numeric_column_names.add(col_name)
            elif hasattr(col_type, "__class__"):
                type_str = str(col_type).upper()
                if any(
                    t in type_str
                    for t in (
                        "NUMERIC",
                        "DECIMAL",
                        "DOUBLE PRECISION",
                        "REAL",
                        "FLOAT",
                        "INTEGER",
                        "BIGINT",
                        "SMALLINT",
                    )
                ):
                    numeric_column_names.add(col_name)

    return numeric_column_names


async def load_db_columns(session: AsyncSession, table_name: str) -> set[str]:
    """Load column names for a table from information_schema."""
    query = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name
        AND table_schema = 'public'
    """
    )

    result = await session.execute(query, {"table_name": table_name})
    columns = {row[0] for row in result.all()}

    if should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"Loaded {len(columns)} columns from {table_name}")
    return columns


__all__ = ["get_numeric_columns", "load_db_columns"]
