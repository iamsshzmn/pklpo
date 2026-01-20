from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import text

from src.database import get_async_session

SUPPORTED_TFS_CONTEXT = ["1Dutc", "4H", "1H"]
SUPPORTED_TFS_TRIGGER = ["15m", "5m"]


@dataclass(frozen=True)
class IndicatorPoint:
    timeframe: str
    ts: int
    ema_fast: float | None
    ema_slow: float | None
    adx: float | None
    vol_std_n: float | None


async def fetch_latest_indicators(
    symbol: str, timeframes: list[str]
) -> dict[str, IndicatorPoint]:
    """Fetch last row per timeframe from indicators for the symbol.

    Expects indicator columns: ema21 (fast), ema50/ema55/ema200 (slow fallback), adx14, atr14 as volatility fallback.
    Uses a simple std proxy from ATR if explicit vol_std_n is not stored.
    """
    results: dict[str, IndicatorPoint] = {}
    async for session in get_async_session():
        for tf in timeframes:
            q = text(
                """
                SELECT timeframe, ts, ema21, ema50, ema200, adx14, atr14
                FROM indicators
                WHERE symbol = :symbol AND timeframe = :tf
                ORDER BY ts DESC
                LIMIT 1
                """
            )
            row = (await session.execute(q, {"symbol": symbol, "tf": tf})).fetchone()
            if not row:
                continue
            ema_fast = _coalesce_float([row.ema21])
            ema_slow = _coalesce_float([row.ema50, row.ema200])
            adx = _coalesce_float([row.adx14])
            vol_std_n = _coalesce_float([row.atr14])
            results[str(row.timeframe)] = IndicatorPoint(
                timeframe=str(row.timeframe),
                ts=int(row.ts),
                ema_fast=ema_fast,
                ema_slow=ema_slow,
                adx=adx,
                vol_std_n=vol_std_n,
            )
        break
    return results


def detect_data_lag(
    latest_ts: int | None, now_utc: int | None, expected_seconds: int
) -> bool:
    """Return True if data lag exceeds 2 bars for given timeframe interval."""
    if latest_ts is None or now_utc is None:
        return True
    lag = now_utc - latest_ts
    return lag > 2 * expected_seconds


def compute_trend_score(point: IndicatorPoint) -> tuple[float | None, bool]:
    """Compute per-timeframe trend score according to spec.

    raw = tanh((EMAfast - EMAslow) / vol_std_N)
    score = raw * (ADX / 100)
    valid = abs(score) >= 0.3
    Returns (score, valid). If inputs are missing, returns (None, False).
    """
    if (
        point.ema_fast is None
        or point.ema_slow is None
        or point.adx is None
        or point.vol_std_n is None
    ):
        return None, False
    if point.vol_std_n == 0:
        return None, False
    raw = math.tanh(
        (float(point.ema_fast) - float(point.ema_slow)) / float(point.vol_std_n)
    )
    score = raw * (float(point.adx) / 100.0)
    return score, abs(score) >= 0.3


def _coalesce_float(values: list[float | None]) -> float | None:
    for v in values:
        if v is not None:
            try:
                return float(v)
            except Exception:
                continue
    return None
