#!/usr/bin/env python3
"""
Standalone helper for loading instruments from OKX API into the database.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.candles.infrastructure.adapters import build_market_data_adapter
from src.logging import get_logger, setup_logging
from src.models import Instrument
from src.utils.session_utils import get_db_session

logger = get_logger("candles.load_instruments")


def extract_currencies_from_symbol(symbol):
    """
    Extract base and quote currencies from an instrument symbol.
    Example: BTC-USDT-SWAP -> (BTC, USDT)
    """
    if not symbol:
        return None, None

    parts = symbol.split("-")
    if len(parts) >= 2:
        base_ccy = parts[0]
        quote_ccy = parts[1]
        return base_ccy, quote_ccy

    return None, None


async def save_instruments_to_db(instruments: list, inst_type: str) -> tuple[int, int]:
    """
    Save instruments to DB.

    Args:
        instruments: Instrument list returned by API.
        inst_type: Instrument type.

    Returns:
        Tuple of (inserted_count, updated_count).
    """
    async with get_db_session() as session:
        new_count = 0
        updated_count = 0
        symbols = [item.get("instId") for item in instruments if item.get("instId")]
        existing_inst_ids: set[str] = set()
        if symbols:
            existing_result = await session.execute(
                select(Instrument.inst_id).where(Instrument.inst_id.in_(symbols))
            )
            existing_inst_ids = {row[0] for row in existing_result.fetchall()}

        for item in instruments:
            # Extract currencies from symbol when API does not provide them.
            symbol = item.get("instId")
            base_ccy = item.get("baseCcy")
            quote_ccy = item.get("quoteCcy")

            if not base_ccy or not quote_ccy:
                extracted_base, extracted_quote = extract_currencies_from_symbol(symbol)
                base_ccy = base_ccy or extracted_base
                quote_ccy = quote_ccy or extracted_quote

            stmt = (
                pg_insert(Instrument)
                .values(
                    symbol=symbol,
                    inst_id=symbol,
                    base_ccy=base_ccy,
                    quote_ccy=quote_ccy,
                    inst_type=item.get("instType"),
                    state=item.get("state"),
                    list_time=(
                        int(item.get("listTime", 0)) if item.get("listTime") else None
                    ),
                    contract_val=(
                        float(item.get("ctVal", 0)) if item.get("ctVal") else None
                    ),
                    settle_ccy=item.get("settleCcy"),
                    ct_type=item.get("ctType"),
                    min_sz=(
                        float(item.get("minSz", 0)) if item.get("minSz") else None
                    ),
                    max_sz=(
                        float(item.get("maxSz", 0)) if item.get("maxSz") else None
                    ),
                    min_notional=(
                        float(item.get("minNotional", 0))
                        if item.get("minNotional")
                        else None
                    ),
                )
                .on_conflict_do_update(
                    index_elements=[Instrument.inst_id],
                    set_={
                        "base_ccy": base_ccy,
                        "quote_ccy": quote_ccy,
                        "inst_type": item.get("instType"),
                        "state": item.get("state"),
                        "list_time": (
                            int(item.get("listTime", 0))
                            if item.get("listTime")
                            else None
                        ),
                        "contract_val": (
                            float(item.get("ctVal", 0)) if item.get("ctVal") else None
                        ),
                        "settle_ccy": item.get("settleCcy"),
                        "ct_type": item.get("ctType"),
                        "min_sz": (
                            float(item.get("minSz", 0)) if item.get("minSz") else None
                        ),
                        "max_sz": (
                            float(item.get("maxSz", 0)) if item.get("maxSz") else None
                        ),
                        "min_notional": (
                            float(item.get("minNotional", 0))
                            if item.get("minNotional")
                            else None
                        ),
                    },
                )
            )
            await session.execute(stmt)
            # rowcount is not reliable to distinguish INSERT vs UPDATE for upsert.
            # Use existence check captured before upsert execution.
            if symbol not in existing_inst_ids:
                new_count += 1
                existing_inst_ids.add(symbol)
            else:
                updated_count += 1

        await session.commit()
        return new_count, updated_count


async def load_instruments() -> None:
    """Load instruments from OKX API into DB."""
    try:
        logger.info("Starting instrument load from OKX API")

        # Load only SWAP instruments.
        inst_types = ["SWAP"]
        total_new = 0
        total_updated = 0

        async with build_market_data_adapter() as client:
            for inst_type in inst_types:
                try:
                    logger.info("Loading %s instruments...", inst_type)
                    instruments = await client.get_instruments(inst_type)

                    if instruments:
                        logger.info("Fetched %s %s instruments", len(instruments), inst_type)

                        new_count, updated_count = await save_instruments_to_db(
                            instruments, inst_type
                        )
                        total_new += new_count
                        total_updated += updated_count

                        logger.info(
                            "%s: inserted=%s, updated=%s",
                            inst_type,
                            new_count,
                            updated_count,
                        )
                    else:
                        logger.warning("No %s instruments were returned", inst_type)

                except Exception as e:
                    logger.error(
                        "Failed to load %s instruments: %s",
                        inst_type,
                        e,
                        exc_info=True,
                    )
                    raise

        logger.info(
            "Instrument load finished: inserted=%s, updated=%s",
            total_new,
            total_updated,
        )
    except Exception as e:
        logger.error("Critical failure while loading instruments: %s", e, exc_info=True)
        raise


def register(subparsers):
    """Register CLI command."""
    p = subparsers.add_parser(
        "load-instruments", help="Load instruments from OKX API"
    )
    p.add_argument(
        "--force", action="store_true", help="Force refresh of all instruments"
    )
    p.set_defaults(_handler=handle)


async def handle(args):
    """CLI command handler."""
    await load_instruments()


async def main():
    """Main entrypoint for running this module directly."""
    setup_logging(level="INFO")

    logger.info("Starting load_instruments module")
    await load_instruments()
    logger.info("load_instruments module finished")


if __name__ == "__main__":
    asyncio.run(main())
