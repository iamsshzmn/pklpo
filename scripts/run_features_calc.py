"""Запуск расчёта features для BTC-USDT-SWAP."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from argparse import Namespace

from src.cli.commands.features import handle


async def main():
    """Запуск расчёта features."""
    args = Namespace(
        symbols=["BTC-USDT-SWAP"],
        timeframes=["1m", "5m", "15m", "30m", "1H", "4H", "12H", "1D", "1W", "1M"],
        specs=None,  # Все индикаторы
        normalize=True,
        normalize_window=20,
        limit=None,  # Все данные
        refill_incomplete=False,
        refill_null=None,
        features_debug=True,
        debug=True,
        backend="auto",
        dry_run=False,
    )

    await handle(args)


if __name__ == "__main__":
    asyncio.run(main())
