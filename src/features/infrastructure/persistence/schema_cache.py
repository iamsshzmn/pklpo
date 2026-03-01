"""
Schema caching for indicator persistence.

Caches DB schema reflection results to avoid repeated queries within
the same session/request. Uses weak references to auto-cleanup.

Extracted from inserter.py (Stage 2 refactoring).
"""

from dataclasses import dataclass, field
from typing import Any

from src.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SchemaInfo:
    """Cached schema information."""
    db_columns: set[str] = field(default_factory=set)
    indicators_table: Any = None
    numeric_columns: set[str] = field(default_factory=set)


class SchemaCache:
    """
    Session-scoped cache for database schema information.

    Avoids repeated `reflect_indicators_table()` and `load_db_columns()`
    calls within the same session.
    """

    def __init__(self):
        # WeakValueDictionary auto-removes entries when session is garbage collected
        self._cache: dict[int, SchemaInfo] = {}

    def _get_session_key(self, session) -> int:
        """Get unique key for session."""
        return id(session)

    def get(self, session) -> SchemaInfo | None:
        """
        Get cached schema info for session.

        Args:
            session: SQLAlchemy async session

        Returns:
            Cached SchemaInfo or None if not cached
        """
        key = self._get_session_key(session)
        return self._cache.get(key)

    def set(
        self,
        session,
        db_columns: set[str],
        indicators_table,
        numeric_columns: set[str],
    ) -> SchemaInfo:
        """
        Cache schema info for session.

        Args:
            session: SQLAlchemy async session
            db_columns: Set of column names in the database
            indicators_table: Reflected SQLAlchemy table
            numeric_columns: Set of numeric column names

        Returns:
            Created SchemaInfo
        """
        key = self._get_session_key(session)
        info = SchemaInfo(
            db_columns=db_columns,
            indicators_table=indicators_table,
            numeric_columns=numeric_columns,
        )
        self._cache[key] = info
        logger.debug(f"Cached schema info for session {key}: {len(db_columns)} columns")
        return info

    def invalidate(self, session) -> None:
        """
        Invalidate cache for session.

        Args:
            session: SQLAlchemy async session
        """
        key = self._get_session_key(session)
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Invalidated schema cache for session {key}")

    def clear(self) -> None:
        """Clear all cached schema info."""
        self._cache.clear()
        logger.debug("Cleared all schema cache")

    def __len__(self) -> int:
        """Return number of cached sessions."""
        return len(self._cache)


# Global cache instance
_schema_cache = SchemaCache()


def get_schema_cache() -> SchemaCache:
    """Get the global schema cache instance."""
    return _schema_cache


async def get_or_load_schema(
    session,
    load_db_columns_func,
    reflect_table_func,
    get_numeric_columns_func,
) -> SchemaInfo:
    """
    Get cached schema or load from database.

    Args:
        session: SQLAlchemy async session
        load_db_columns_func: Async function to load DB columns
        reflect_table_func: Async function to reflect indicators table
        get_numeric_columns_func: Function to extract numeric columns from table

    Returns:
        SchemaInfo with db_columns, indicators_table, and numeric_columns
    """
    cache = get_schema_cache()

    # Try cache first
    cached = cache.get(session)
    if cached is not None:
        logger.debug("Using cached schema info")
        return cached

    # Load from database
    logger.debug("Loading schema info from database...")
    db_columns = await load_db_columns_func(session)
    indicators_table = await reflect_table_func(session)
    numeric_columns = get_numeric_columns_func(indicators_table)

    # Cache for future use
    return cache.set(session, db_columns, indicators_table, numeric_columns)
