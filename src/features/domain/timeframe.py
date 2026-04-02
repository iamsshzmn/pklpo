from __future__ import annotations

_TIMEFRAME_TO_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1H": 3600,
    "4H": 14400,
    "12H": 43200,
    "1D": 86400,
    "1W": 604800,
    "1M": 2592000,
}


def timeframe_to_seconds(timeframe: str, default: int = 60) -> int:
    return _TIMEFRAME_TO_SECONDS.get(timeframe, default)
