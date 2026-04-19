from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.candles.infrastructure.adapters import build_market_data_adapter
from src.candles.load_instruments import save_instruments_to_db

if TYPE_CHECKING:
    from src.candles.ports import InstrumentCatalogQueryPort
    from src.market_meta.ports import InstrumentRepositoryPort

PRIORITY_SYMBOLS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]


def resolve_repo_instruments_file() -> Path:
    """Return the repo-local curated instruments list for default sync runs."""
    return Path(__file__).resolve().with_name("instruments_list.json")


def resolve_instruments_cache_file(cache_dir: Path | None = None) -> Path:
    """Resolve the runtime instrument cache file and ensure its directory exists.

    Runtime cache lives under ``INSTRUMENTS_CACHE_DIR`` (or the explicit
    ``cache_dir`` override). It is separate from the curated repo-local
    ``src/candles/instruments_list.json`` list used by application-layer
    symbol selection policy.
    """
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


def load_symbols_from_file(instruments_file: Path, *, logger: Any | None = None) -> list[str]:
    """Load a symbol list from JSON file, returning [] on invalid content."""
    if not instruments_file.exists():
        return []

    try:
        with open(instruments_file, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        if logger is not None:
            logger.warning("Failed to read symbols from %s (%s)", instruments_file, exc)
        return []

    if not isinstance(payload, list):
        if logger is not None:
            logger.warning("Invalid symbols payload in %s: expected list", instruments_file)
        return []

    symbols: list[str] = []
    for item in payload:
        if item is None:
            continue
        normalized = item.strip() if isinstance(item, str) else str(item).strip()
        if normalized and normalized.lower() not in {"none", "null"}:
            symbols.append(normalized)
    return symbols


async def refresh_instruments_list(
    *,
    repository: InstrumentCatalogQueryPort,
    logger: Any,
    cache_dir: Path | None = None,
) -> list[str]:
    """
    Refresh the runtime instruments cache file from the repository.

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
        # Auto-update is intentionally disabled to keep the instrument list fixed.
        # try:
        #     with open(instruments_file, "w", encoding="utf-8") as f:
        #         json.dump(new_symbols, f, indent=2, ensure_ascii=False)
        #     logger.info("Instrument list updated and saved to %s", instruments_file)
        # except Exception as exc:
        #     logger.error("Failed to save instrument list: %s", exc)
        #     raise
        logger.info(
            "Instrument list changes detected, but auto-update is disabled for %s",
            instruments_file,
        )
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


async def ensure_symbols_registered(
    symbols: list[str],
    *,
    repository: InstrumentRepositoryPort,
    logger: Any,
) -> None:
    """Register any curated symbols absent from the instruments table.

    Fetches missing symbols from OKX API and upserts them.
    Raises ValueError if a symbol is not on OKX — indicates typo or delisted instrument.
    """
    missing = await repository.find_missing_symbols(symbols)
    if not missing:
        logger.info("ensure_symbols_registered: all %d symbols already registered", len(symbols))
        return

    logger.info(
        "ensure_symbols_registered: %d symbols missing from instruments table: %s",
        len(missing),
        missing,
    )

    async with build_market_data_adapter() as client:
        okx_instruments = await client.get_instruments("SWAP")

    okx_by_symbol = {item["instId"]: item for item in okx_instruments if item.get("instId")}
    not_on_okx = [s for s in missing if s not in okx_by_symbol]
    if not_on_okx:
        raise ValueError(
            f"Cannot register symbols — not found on OKX (typo or delisted): {not_on_okx}. "
            "Remove them from src/candles/instruments_list.json or check the symbol name."
        )

    to_save = [okx_by_symbol[s] for s in missing]
    new_count, updated_count = await save_instruments_to_db(to_save, "SWAP")
    logger.info(
        "ensure_symbols_registered: registered %d symbols (inserted=%d, updated=%d)",
        len(missing),
        new_count,
        updated_count,
    )
