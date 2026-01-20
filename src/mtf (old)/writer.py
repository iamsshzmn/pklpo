from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text

from src.database import get_async_session


async def save_mtf_result(
    symbol: str,
    consensus: int,
    input_data: dict[str, Any],
    timeframe: str = "15m",
) -> None:
    """Insert MTF result into dedicated table mtf_signals.

    Храним только данные MTF, чтобы не смешивать с расчётами позиций.
    """
    async for session in get_async_session():
        insert = text(
            """
            INSERT INTO mtf_signals (
                id, symbol, calculated_at,
                input_data, signal_consensus, signal_age_bars, signal_timeframe
            ) VALUES (
                :id, :symbol, :ts,
                CAST(:input_data AS JSONB), :consensus, 0, :tf
            )
            ON CONFLICT (id) DO NOTHING
            """
        )
        await session.execute(
            insert,
            {
                "id": str(uuid.uuid4()),
                "symbol": symbol,
                "ts": datetime.utcnow(),
                "input_data": json.dumps(input_data),
                "consensus": int(consensus),
                "tf": timeframe,
            },
        )
        await session.commit()
        break
