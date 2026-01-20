from __future__ import annotations

from sqlalchemy import text

from src.database import get_async_session

SUPPORTED_COMBINATIONS = [
    "bbands_kc_ttm",
    "ichimoku_macd_rsi",
    "macd_bbands",
    "macd_ichimoku",
    "macd_rsi",
    "macd_rsi_bbands",
    "obv_macd",
    "rsi_cmf",
    "rsi_obv",
    "rsi_vwap_vp",
]


async def compute_combination_votes(symbol: str) -> dict[str, int]:
    """Compute +1/-1/0 votes per combination for the latest bar per combo.

    This function uses a simple heuristic for now:
    - If trading_action or recommendation suggests buy/long → +1
    - If suggests sell/short → -1
    - Else 0
    Later can be extended to explicit rule logic per combo from docs/combos.md.
    """
    votes: dict[str, int] = {name: 0 for name in SUPPORTED_COMBINATIONS}
    async for session in get_async_session():
        q = text(
            """
            SELECT DISTINCT ON (combination_name) combination_name, trading_action, recommendation
            FROM combination_results
            WHERE symbol = :symbol
            ORDER BY combination_name, ts DESC
            """
        )
        rows = (await session.execute(q, {"symbol": symbol})).fetchall()
        for r in rows:
            name = str(r.combination_name)
            if name not in votes:
                continue
            text_blob = " ".join(
                [
                    str(r.trading_action or ""),
                    str(r.recommendation or ""),
                ]
            ).lower()
            if any(k in text_blob for k in ["buy", "long", "bull"]):
                votes[name] = 1
            elif any(k in text_blob for k in ["sell", "short", "bear"]):
                votes[name] = -1
            else:
                votes[name] = 0
        break
    return votes
