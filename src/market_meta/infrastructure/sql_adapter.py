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
