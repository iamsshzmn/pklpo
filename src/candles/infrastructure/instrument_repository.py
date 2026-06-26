"""SQL repository for instrument metadata."""

from __future__ import annotations

from sqlalchemy import bindparam, text

from src.utils.session_utils import get_db_session


class InstrumentSqlRepository:
    """Instrument catalog queries backed by the ``instruments`` table."""

    async def find_missing_symbols(self, symbols: list[str]) -> list[str]:
        unique_symbols = [symbol for symbol in dict.fromkeys(symbols) if symbol]
        if not unique_symbols:
            return []

        stmt = text(
            """
            SELECT inst_id
            FROM instruments
            WHERE inst_id IN :symbols
            """
        ).bindparams(bindparam("symbols", expanding=True))
        async with get_db_session() as session:
            result = await session.execute(stmt, {"symbols": unique_symbols})

        existing = {str(row[0]) for row in result.fetchall()}
        return [symbol for symbol in unique_symbols if symbol not in existing]

    async def instrument_exists(self, symbol: str) -> bool:
        if not symbol:
            return False
        missing = await self.find_missing_symbols([symbol])
        return not missing
