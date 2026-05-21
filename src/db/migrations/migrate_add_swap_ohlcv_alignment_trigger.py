"""Create the optional swap_ohlcv_p timestamp alignment trigger.

The trigger is created idempotently and left disabled by default. Enable only
after alignment preflight is clean:
    ALTER TABLE swap_ohlcv_p ENABLE TRIGGER trg_swap_ohlcv_p_align_check;

Rollback snippets:
    ALTER TABLE swap_ohlcv_p DISABLE TRIGGER trg_swap_ohlcv_p_align_check;
    DROP TRIGGER IF EXISTS trg_swap_ohlcv_p_align_check ON swap_ohlcv_p;
    DROP FUNCTION IF EXISTS public.swap_ohlcv_p_align_check();
"""

from __future__ import annotations

from sqlalchemy import text

from src.config.settings import get_settings
from src.utils.session_utils import get_db_session

CREATE_ALIGN_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.swap_ohlcv_p_align_check()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    tf_ms      bigint;
    monday_ms constant bigint := 345600000;
    dt         timestamp;
BEGIN
    CASE NEW.timeframe
        WHEN '1m'  THEN tf_ms := 60000;
        WHEN '5m'  THEN tf_ms := 300000;
        WHEN '15m' THEN tf_ms := 900000;
        WHEN '30m' THEN tf_ms := 1800000;
        WHEN '1H'  THEN tf_ms := 3600000;
        WHEN '4H'  THEN tf_ms := 14400000;
        WHEN '12H' THEN tf_ms := 43200000;
        WHEN '1D'  THEN tf_ms := 86400000;
        WHEN '1W'  THEN
            IF ((NEW.timestamp - monday_ms) % 604800000) <> 0 THEN
                RAISE EXCEPTION
                    'swap_ohlcv_p.timestamp % not Monday-UTC aligned for 1W',
                    NEW.timestamp;
            END IF;
            RETURN NEW;
        WHEN '1M'  THEN
            dt := to_timestamp(NEW.timestamp / 1000.0) AT TIME ZONE 'UTC';
            IF EXTRACT(day FROM dt) <> 1
               OR EXTRACT(hour FROM dt) <> 0
               OR EXTRACT(minute FROM dt) <> 0
               OR EXTRACT(second FROM dt) <> 0 THEN
                RAISE EXCEPTION
                    'swap_ohlcv_p.timestamp % not month-start UTC for 1M',
                    NEW.timestamp;
            END IF;
            RETURN NEW;
        ELSE
            RAISE EXCEPTION 'swap_ohlcv_p unsupported timeframe %', NEW.timeframe;
    END CASE;

    IF (NEW.timestamp % tf_ms) <> 0 THEN
        RAISE EXCEPTION 'swap_ohlcv_p.timestamp % not aligned to %ms (% tf)',
            NEW.timestamp, tf_ms, NEW.timeframe;
    END IF;
    RETURN NEW;
END;
$$
"""

CREATE_ALIGN_TRIGGER_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'trg_swap_ohlcv_p_align_check'
          AND tgrelid = 'swap_ohlcv_p'::regclass
    ) THEN
        CREATE TRIGGER trg_swap_ohlcv_p_align_check
            BEFORE INSERT OR UPDATE OF timestamp, timeframe ON swap_ohlcv_p
            FOR EACH ROW EXECUTE FUNCTION public.swap_ohlcv_p_align_check();
    END IF;
END;
$$
"""

DISABLE_ALIGN_TRIGGER_SQL = """
ALTER TABLE swap_ohlcv_p DISABLE TRIGGER trg_swap_ohlcv_p_align_check
"""

ENABLE_ALIGN_TRIGGER_SQL = """
ALTER TABLE swap_ohlcv_p ENABLE TRIGGER trg_swap_ohlcv_p_align_check
"""


async def migrate_add_swap_ohlcv_alignment_trigger() -> None:
    """Create the alignment trigger and leave it disabled for opt-in rollout."""
    async with get_db_session() as session:
        try:
            await session.execute(text(CREATE_ALIGN_FUNCTION_SQL))
            await session.execute(text(CREATE_ALIGN_TRIGGER_SQL))
            await session.execute(text(DISABLE_ALIGN_TRIGGER_SQL))
            if get_settings().candles.db_alignment_trigger_enabled:
                await session.execute(text(ENABLE_ALIGN_TRIGGER_SQL))
            await session.commit()
        except Exception:
            await session.rollback()
            raise
