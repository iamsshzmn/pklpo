from __future__ import annotations

from itertools import pairwise
from typing import Any

from sqlalchemy import text

from src.candles.application.repair.ports import ListingAnchorMetadata
from src.candles.domain.candle_validation import (
    CandleValidationError,
    validate_chunk_for_write,
)
from src.candles.domain.okx_calendar import StorageCalendar
from src.candles.domain.repair import (
    CoverageReconciliation,
    RepairWindow,
    detect_gap_tasks,
)
from src.candles.domain.repair_timeframes import (
    expected_next_open,
    floor_to_timeframe,
    list_expected_timestamps,
)
from src.candles.domain.timeframes import TF_TO_MS
from src.candles.infrastructure.ohlcv_write_lock import ohlcv_symbol_write_lock
from src.candles.repository import (
    SwapCandlesRepository,
    _chunk_window,
    _log_candle_validation_failure,
)
from src.config.settings import get_settings
from src.utils.session_utils import get_db_session


class RepairCandlesRepository(SwapCandlesRepository):
    def __init__(self) -> None:
        super().__init__()
        self._listing_metadata_cache: dict[str, ListingAnchorMetadata | None] = {}

    async def get_listing_anchor_metadata(
        self,
        *,
        symbol: str,
    ) -> ListingAnchorMetadata | None:
        if symbol in self._listing_metadata_cache:
            return self._listing_metadata_cache[symbol]

        async def _operation() -> ListingAnchorMetadata | None:
            async with get_db_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT list_time, metadata_refreshed_at_ms
                        FROM instruments
                        WHERE symbol = :symbol
                        LIMIT 1
                        """
                    ),
                    {"symbol": symbol},
                )
                row = result.fetchone()
            if row is None:
                return None
            list_time = int(row[0]) if row[0] is not None else None
            metadata_refreshed_at_ms = int(row[1]) if row[1] is not None else None
            return ListingAnchorMetadata(
                list_time_ts_ms=list_time,
                metadata_refreshed_at_ms=metadata_refreshed_at_ms,
            )

        result = await self._run_with_db_retry(_operation)
        self._listing_metadata_cache[symbol] = result
        return result

    async def get_listing_time_ts_ms(self, *, symbol: str) -> int | None:
        metadata = await self.get_listing_anchor_metadata(symbol=symbol)
        if metadata is None:
            return None
        return metadata.list_time_ts_ms

    async def get_coverage_bounds(
        self,
        *,
        symbol: str,
        timeframe: str,
        end_ts_ms: int,
    ) -> tuple[int | None, int | None]:
        async def _operation() -> tuple[int | None, int | None]:
            async with get_db_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT MIN(timestamp), MAX(timestamp)
                        FROM swap_ohlcv_p
                        WHERE symbol = :symbol
                          AND timeframe = :timeframe
                          AND timestamp < :end_ts_ms
                        """
                    ),
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "end_ts_ms": end_ts_ms,
                    },
                )
                row = result.one()
            min_ts = int(row[0]) if row[0] is not None else None
            max_ts = int(row[1]) if row[1] is not None else None
            return min_ts, max_ts

        return await self._run_with_db_retry(_operation)

    async def find_first_gap_start_ts_ms(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> int | None:
        if timeframe == "1M":
            timestamps = await self.list_timestamps(
                symbol=symbol,
                timeframe=timeframe,
                start_ts_ms=start_ts_ms,
                end_ts_ms=end_ts_ms,
            )
            for current_ts, next_ts in pairwise(timestamps):
                gap_start = expected_next_open(current_ts, timeframe)
                if next_ts > gap_start:
                    return gap_start
            return None

        step_ms = TF_TO_MS[timeframe]

        async def _operation() -> int | None:
            async with get_db_session() as session:
                result = await session.execute(
                    text(
                        """
                        WITH ordered AS (
                            SELECT
                                timestamp,
                                LEAD(timestamp) OVER (ORDER BY timestamp) AS next_ts
                            FROM swap_ohlcv_p
                            WHERE symbol = :symbol
                              AND timeframe = :timeframe
                              AND timestamp >= :start_ts_ms
                              AND timestamp < :end_ts_ms
                        )
                        SELECT timestamp + :step_ms AS gap_start_ts_ms
                        FROM ordered
                        WHERE next_ts IS NOT NULL
                          AND next_ts > timestamp + :step_ms
                        ORDER BY timestamp
                        LIMIT 1
                        """
                    ),
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "start_ts_ms": start_ts_ms,
                        "end_ts_ms": end_ts_ms,
                        "step_ms": step_ms,
                    },
                )
                gap_start = result.scalar()
            return int(gap_start) if gap_start is not None else None

        return await self._run_with_db_retry(_operation)

    async def list_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[int]:
        async def _operation() -> list[int]:
            async with get_db_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT timestamp
                        FROM swap_ohlcv_p
                        WHERE symbol = :symbol
                          AND timeframe = :timeframe
                          AND timestamp >= :start_ts_ms
                          AND timestamp < :end_ts_ms
                        ORDER BY timestamp
                        """
                    ),
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "start_ts_ms": start_ts_ms,
                        "end_ts_ms": end_ts_ms,
                    },
                )
                rows = result.fetchall()
            return [int(row[0]) for row in rows]

        return await self._run_with_db_retry(_operation)

    async def list_existing_valid_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[int]:
        async def _operation() -> list[int]:
            async with get_db_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT timestamp
                        FROM swap_ohlcv_p
                        WHERE symbol = :symbol
                          AND timeframe = :timeframe
                          AND timestamp >= :start_ts_ms
                          AND timestamp < :end_ts_ms
                          AND open IS NOT NULL
                          AND high IS NOT NULL
                          AND low IS NOT NULL
                          AND close IS NOT NULL
                          AND volume IS NOT NULL
                          AND open > 0
                          AND high > 0
                          AND low > 0
                          AND close > 0
                          AND volume >= 0
                          AND high >= low
                          AND open >= low
                          AND open <= high
                          AND close >= low
                          AND close <= high
                        ORDER BY timestamp
                        """
                    ),
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "start_ts_ms": start_ts_ms,
                        "end_ts_ms": end_ts_ms,
                    },
                )
                rows = result.fetchall()
            return [int(row[0]) for row in rows]

        return await self._run_with_db_retry(_operation)

    async def count_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> int:
        """Deprecated raw row count; use count_valid_candles for coverage."""
        async def _operation() -> int:
            async with get_db_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM swap_ohlcv_p
                        WHERE symbol = :symbol
                          AND timeframe = :timeframe
                          AND timestamp >= :start_ts_ms
                          AND timestamp < :end_ts_ms
                        """
                    ),
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "start_ts_ms": start_ts_ms,
                        "end_ts_ms": end_ts_ms,
                    },
                )
                return int(result.scalar() or 0)

        return await self._run_with_db_retry(_operation)

    async def count_valid_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> CoverageReconciliation:
        valid_timestamps = await self.list_existing_valid_timestamps(
            symbol=symbol,
            timeframe=timeframe,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
        )
        raw_timestamps = await self.list_timestamps(
            symbol=symbol,
            timeframe=timeframe,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
        )
        window = RepairWindow(start_ts_ms=start_ts_ms, end_ts_ms=end_ts_ms)
        calendar = StorageCalendar()
        expected_opens = set(
            list_expected_timestamps(
                start_ts_ms,
                end_ts_ms,
                timeframe,
                calendar=calendar,
            )
        )
        valid_expected_timestamps = {
            ts for ts in valid_timestamps if start_ts_ms <= ts < end_ts_ms
        } & expected_opens
        gap_tasks = detect_gap_tasks(
            timestamps=sorted(valid_expected_timestamps),
            timeframe=timeframe,
            window=window,
            calendar=calendar,
        )
        return CoverageReconciliation(
            expected_bars=len(expected_opens),
            valid_bars=len(valid_expected_timestamps),
            missing_bars=sum(task.missing_bars for task in gap_tasks),
            invalid_extra_rows=max(
                0,
                len(raw_timestamps) - len(valid_expected_timestamps),
            ),
        )

    async def selective_upsert_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
        window: RepairWindow | None = None,
        calendar: StorageCalendar | None = None,
    ) -> int:
        if not candles:
            return 0
        calendar = calendar or StorageCalendar()
        if get_settings().candles.strict_write_validation:
            write_window = window or _chunk_window(
                candles,
                timeframe=timeframe,
                calendar=calendar,
            )
            try:
                validate_chunk_for_write(
                    candles,
                    symbol=symbol,
                    timeframe=timeframe,
                    calendar=calendar,
                    window=write_window,
                )
            except CandleValidationError as exc:
                _log_candle_validation_failure(
                    exc,
                    symbol=symbol,
                    timeframe=timeframe,
                )
                raise

        rows = [
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": candle["timestamp"],
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "volume": candle["volume"],
                "vol_ccy": candle.get("vol_ccy"),
                "vol_usd": candle.get("vol_usd"),
                "fetched_at": candle["fetched_at"],
            }
            for candle in candles
        ]

        stmt = text(
            """
            INSERT INTO swap_ohlcv_p (
                symbol,
                timeframe,
                timestamp,
                open,
                high,
                low,
                close,
                volume,
                vol_ccy,
                vol_usd,
                fetched_at
            )
            VALUES (
                :symbol,
                :timeframe,
                :timestamp,
                :open,
                :high,
                :low,
                :close,
                :volume,
                :vol_ccy,
                :vol_usd,
                :fetched_at
            )
            ON CONFLICT (symbol, timeframe, timestamp)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                vol_ccy = EXCLUDED.vol_ccy,
                vol_usd = EXCLUDED.vol_usd,
                fetched_at = EXCLUDED.fetched_at
            """
        )

        async def _operation() -> int:
            async with get_db_session() as session:
                try:
                    async with ohlcv_symbol_write_lock(
                        session,
                        symbol=symbol,
                        timeframe=timeframe,
                    ):
                        result = await session.execute(stmt, rows)
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
            return result.rowcount if result.rowcount >= 0 else len(rows)

        return int(await self._run_with_db_retry(_operation))

    async def list_missing_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
        interval_ms: int,
    ) -> list[int]:
        if timeframe == "1M":
            return await self._list_missing_1m(
                symbol=symbol, start_ts_ms=start_ts_ms, end_ts_ms=end_ts_ms
            )

        async def _operation() -> list[int]:
            async with get_db_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT gs.ts
                        FROM generate_series(
                            :start_ts_ms::bigint,
                            :end_ts_ms::bigint - :interval_ms::bigint,
                            :interval_ms::bigint
                        ) AS gs(ts)
                        LEFT JOIN swap_ohlcv_p c
                            ON c.symbol = :symbol
                            AND c.timeframe = :timeframe
                            AND c.timestamp = gs.ts
                        WHERE c.timestamp IS NULL
                        ORDER BY gs.ts
                        """
                    ),
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "start_ts_ms": start_ts_ms,
                        "end_ts_ms": end_ts_ms,
                        "interval_ms": interval_ms,
                    },
                )
                rows = result.fetchall()
            return [int(row[0]) for row in rows]

        return await self._run_with_db_retry(_operation)

    async def _list_missing_1m(
        self,
        *,
        symbol: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[int]:
        existing = set(
            await self.list_timestamps(
                symbol=symbol,
                timeframe="1M",
                start_ts_ms=start_ts_ms,
                end_ts_ms=end_ts_ms,
            )
        )
        missing: list[int] = []
        ts = floor_to_timeframe(start_ts_ms, "1M")
        while ts < end_ts_ms:
            if ts not in existing:
                missing.append(ts)
            ts = expected_next_open(ts, "1M")
        return missing

    async def count_missing_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> int:
        if start_ts_ms >= end_ts_ms:
            return 0
        if timeframe == "1M":
            missing = await self._list_missing_1m(
                symbol=symbol, start_ts_ms=start_ts_ms, end_ts_ms=end_ts_ms
            )
            return len(missing)

        interval_ms = TF_TO_MS[timeframe]

        async def _operation() -> int:
            async with get_db_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM generate_series(
                            CAST(:start_ts_ms AS bigint),
                            CAST(:end_ts_ms AS bigint) - CAST(:interval_ms AS bigint),
                            CAST(:interval_ms AS bigint)
                        ) AS gs(ts)
                        LEFT JOIN swap_ohlcv_p c
                            ON c.symbol = :symbol
                            AND c.timeframe = :timeframe
                            AND c.timestamp = gs.ts
                        WHERE c.timestamp IS NULL
                        """
                    ),
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "start_ts_ms": start_ts_ms,
                        "end_ts_ms": end_ts_ms,
                        "interval_ms": interval_ms,
                    },
                )
                return int(result.scalar() or 0)

        return int(await self._run_with_db_retry(_operation))

    async def list_corrupted_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[int]:
        async def _operation() -> list[int]:
            async with get_db_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT timestamp
                        FROM swap_ohlcv_p
                        WHERE symbol = :symbol
                          AND timeframe = :timeframe
                          AND timestamp >= :start_ts_ms
                          AND timestamp < :end_ts_ms
                          AND (
                              open IS NULL OR high IS NULL OR low IS NULL
                              OR close IS NULL OR volume IS NULL
                              OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                              OR volume < 0
                              OR high < low
                              OR open < low OR open > high
                              OR close < low OR close > high
                          )
                        ORDER BY timestamp
                        """
                    ),
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "start_ts_ms": start_ts_ms,
                        "end_ts_ms": end_ts_ms,
                    },
                )
                rows = result.fetchall()
            return [int(row[0]) for row in rows]

        return await self._run_with_db_retry(_operation)
