from __future__ import annotations

TF_TO_MS: dict[str, int] = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1H": 3_600_000,
    "4H": 14_400_000,
    "12H": 43_200_000,
    "1D": 86_400_000,
    "1W": 604_800_000,
    "1M": 2_592_000_000,
}

TF_TO_SEC: dict[str, int] = {tf: ms // 1000 for tf, ms in TF_TO_MS.items()}
