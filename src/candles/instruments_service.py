from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.candles.ports import InstrumentCatalogQueryPort

PRIORITY_SYMBOLS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]


def resolve_instruments_cache_file(cache_dir: Path | None = None) -> Path:
    """Resolve path to instruments cache file and ensure directory exists."""
    target_dir = cache_dir
    if target_dir is None:
        env_dir = os.getenv("INSTRUMENTS_CACHE_DIR")
        target_dir = Path(env_dir) if env_dir else Path(tempfile.gettempdir())
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        target_dir = Path(tempfile.gettempdir())
        target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "instruments_list.json"


async def refresh_instruments_list(
    *,
    repository: InstrumentCatalogQueryPort,
    logger: Any,
    cache_dir: Path | None = None,
) -> list[str]:
    """
    Refresh instruments list in cache file.

    Keeps BTC/ETH first and appends remaining symbols alphabetically.
    Returns resulting list.
    """
    instruments_file = resolve_instruments_cache_file(cache_dir)

    current_symbols: list[str] = []
    if instruments_file.exists():
        try:
            with open(instruments_file, encoding="utf-8") as f:
                current_symbols = json.load(f)
            logger.debug("Loaded current cached list: %s symbols", len(current_symbols))
        except Exception as exc:
            logger.warning("Failed to load current cached list: %s", exc)

    logger.info("Loading swap symbols and instrument counters from repository")
    counts = await repository.get_instrument_counts()
    db_symbols = await repository.list_swap_symbols()

    logger.info("All instruments in DB: %s", int(counts.get("all", 0)))
    logger.info("SWAP instruments in DB: %s", int(counts.get("swap", 0)))
    logger.info("USDT instruments in DB: %s", int(counts.get("usdt", 0)))
    logger.info("Found %s SWAP USDT symbols in DB", len(db_symbols))
    if db_symbols:
        logger.info("First 5 symbols: %s", db_symbols[:5])
    else:
        logger.warning("No SWAP USDT symbols found in DB")

    new_symbols = [s for s in PRIORITY_SYMBOLS if s in db_symbols]
    new_symbols.extend(sorted(s for s in db_symbols if s not in PRIORITY_SYMBOLS))

    current_set = set(current_symbols)
    new_set = set(new_symbols)
    added = new_set - current_set
    removed = current_set - new_set

    if added:
        logger.info("Added symbols: %s", sorted(added))
    if removed:
        logger.info("Removed symbols: %s", sorted(removed))

    if added or removed:
        try:
            with open(instruments_file, "w", encoding="utf-8") as f:
                json.dump(new_symbols, f, indent=2, ensure_ascii=False)
            logger.info("Instrument list updated and saved to %s", instruments_file)
        except Exception as exc:
            logger.error("Failed to save instrument list: %s", exc)
            raise
    else:
        logger.debug("Instrument list is up to date")

    logger.info("Instrument list update stats:")
    logger.info("  Total symbols: %s", len(new_symbols))
    logger.info(
        "  Priority symbols: %s",
        len([s for s in new_symbols if s in PRIORITY_SYMBOLS]),
    )
    logger.info(
        "  Regular symbols: %s",
        len([s for s in new_symbols if s not in PRIORITY_SYMBOLS]),
    )
    if added:
        logger.info("  Added: %s", len(added))
    if removed:
        logger.info("  Removed: %s", len(removed))

    return new_symbols
