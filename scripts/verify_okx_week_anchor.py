"""
Verify OKX 1W candle alignment against the configured week_anchor_ts_ms.

Usage (requires OKX API credentials in .env):
    python scripts/verify_okx_week_anchor.py

What it does:
1. Fetches the last 26 closed 1W candles for BTC-USDT-SWAP from OKX history API.
2. Checks each candle timestamp against: (ts - anchor) % 7_days_ms == 0
   All timestamps must satisfy this for the anchor to be correct.
3. Prints the recommended anchor value and exit code.

Exit codes: 0 = anchor verified, 1 = mismatch found or API error.

NOTE: This is an operational verification script, not part of the unit test suite.
Run manually as part of Phase 8 (OKX week anchor validation).
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.candles.ccxt_okx_adapter import CcxtOKXAdapter
from src.config.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1_000
INSTRUMENT = "BTC-USDT-SWAP"
SAMPLE_BARS = 26  # 26 weeks = 6 months; enough to detect systematic misalignment


async def _verify() -> int:
    try:
        settings = get_settings()
        anchor = int(settings.okx.week_anchor_ts_ms or 0)
        logger.info(
            "Configured anchor: %d = %s",
            anchor,
            datetime.fromtimestamp(anchor / 1000, UTC).isoformat(),
        )

        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        start_ms = now_ms - SAMPLE_BARS * SEVEN_DAYS_MS

        adapter = CcxtOKXAdapter(settings=settings.okx)
        try:
            candles = await adapter.get_history_candles(
                inst_id=INSTRUMENT,
                bar="1W",
                start_ts_ms=start_ms,
                end_ts_ms=now_ms,
            )
        finally:
            await adapter.close()

        if not candles:
            logger.error("No 1W candles returned from OKX API")
            return 1

        logger.info("Fetched %d 1W candles for %s", len(candles), INSTRUMENT)
        mismatches = []
        for candle in candles:
            ts = int(candle["ts"])
            remainder = (ts - anchor) % SEVEN_DAYS_MS
            ok = remainder == 0
            marker = "OK" if ok else f"MISMATCH remainder={remainder}"
            print(f"  {datetime.fromtimestamp(ts / 1000, UTC).isoformat()}  [{marker}]")
            if not ok:
                mismatches.append(ts)

        if mismatches:
            corrected = int(candles[0]["ts"])
            corrected_dt = datetime.fromtimestamp(corrected / 1000, UTC)
            logger.warning(
                "MISMATCH FOUND in %d bars. Suggested corrected anchor: %d = %s",
                len(mismatches),
                corrected,
                corrected_dt.isoformat(),
            )
            print(
                f"\nUpdate DEFAULT_WEEK_ANCHOR_TS_MS = {corrected} in src/config/settings.py"
            )
            return 1

        logger.info(
            "Anchor %d VERIFIED — all %d 1W bars align correctly", anchor, len(candles)
        )
        print("\nNo changes needed in src/config/settings.py")
        return 0

    except Exception:
        logger.error("Anchor verification failed", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_verify()))
