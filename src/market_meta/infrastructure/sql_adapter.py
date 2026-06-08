from __future__ import annotations

from sqlalchemy import text

from src.utils.session_utils import get_db_session


class InstrumentSqlRepository:
    """Queries the instruments table to check symbol existence."""

    async def instrument_exists(self, symbol: str) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                text("SELECT 1 FROM instruments WHERE symbol = :symbol LIMIT 1"),
                {"symbol": symbol},
            )
            return result.fetchone() is not None

    async def find_missing_symbols(self, symbols: list[str]) -> list[str]:
        """Return symbols from the given list that are absent from the instruments table."""
        if not symbols:
            return []
        async with get_db_session() as session:
            result = await session.execute(
                text("SELECT symbol FROM instruments WHERE symbol = ANY(:symbols)"),
                {"symbols": symbols},
            )
            found = {row[0] for row in result.fetchall()}
        return [s for s in symbols if s not in found]
