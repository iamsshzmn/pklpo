"""
CLI команда build-bars: генерация долларовых баров из OHLCV данных.

Использование:
    python -m src.cli.main build-bars --symbols BTC-USDT-SWAP --dollar-value 200000
    python -m src.cli.main build-bars --symbols BTC-USDT-SWAP ETH-USDT-SWAP \\
        --dollar-value 100000 --volume-unit contracts --contract-val 0.01
    python -m src.cli.main build-bars --symbols BTC-USDT-SWAP --dry-run
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import text

from src.core.bars import BarsConfig, build_dollar_bars
from src.core.run_context import RunContext

logger = logging.getLogger(__name__)


def register(subparsers) -> None:  # type: ignore[no-untyped-def]
    """Регистрация команды build-bars в CLI."""
    p = subparsers.add_parser(
        "build-bars",
        help="Генерация долларовых баров из OHLCV данных",
    )
    p.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="Символы для обработки (например: BTC-USDT-SWAP ETH-USDT-SWAP)",
    )
    p.add_argument(
        "--timeframe",
        default="1m",
        help="Таймфрейм источника данных (default: 1m)",
    )
    p.add_argument(
        "--dollar-value",
        type=float,
        default=200_000.0,
        help="Целевой оборот на бар в USD (default: 200000)",
    )
    p.add_argument(
        "--volume-unit",
        choices=["base", "quote", "contracts"],
        default="base",
        help="Единица измерения volume: base/quote/contracts (default: base)",
    )
    p.add_argument(
        "--contract-val",
        type=float,
        default=1.0,
        help="Стоимость контракта в base currency (только для --volume-unit contracts)",
    )
    p.add_argument(
        "--min-trades",
        type=int,
        default=1,
        help="Минимальное число строк для закрытия бара (default: 1)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Лимит строк из БД для обработки (default: все данные)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Показать план без генерации баров",
    )
    p.set_defaults(_handler=handle)


async def handle(args) -> None:  # type: ignore[no-untyped-def]
    """Обработчик команды build-bars."""
    if args.dry_run:
        _show_plan(args)
        return

    ctx = RunContext.create(
        params={
            "dollar_value": args.dollar_value,
            "volume_unit": args.volume_unit,
            "contract_val": args.contract_val,
            "timeframe": args.timeframe,
        }
    )
    logger.info("RunContext: %s", ctx)

    config = BarsConfig(
        dollar_value=args.dollar_value,
        volume_unit=args.volume_unit,  # type: ignore[arg-type]
        contract_val=args.contract_val,
        min_trades=args.min_trades,
        bars_source="fallback_minute",
    )

    total_bars = 0
    for symbol in args.symbols:
        df = await _load_ohlcv(symbol, args.timeframe, args.limit)
        if df is None or len(df) == 0:
            logger.warning("Нет данных для %s %s", symbol, args.timeframe)
            continue

        bars = build_dollar_bars(df, config)
        total_bars += len(bars)

        _log_bars_summary(symbol, args.timeframe, df, bars, config)

    logger.info(
        "build-bars завершён: %d символов, %d баров всего (run_id=%s)",
        len(args.symbols),
        total_bars,
        ctx.run_id[:8],
    )


async def _load_ohlcv(
    symbol: str, timeframe: str, limit: int | None
) -> pd.DataFrame | None:
    """Загрузить OHLCV данные из БД."""
    from src.utils.session_utils import get_db_session

    try:
        async with get_db_session() as session:
            limit_clause = f"LIMIT {limit}" if limit else ""
            query = text(f"""
                SELECT timestamp, open, high, low, close, volume
                FROM swap_ohlcv_p
                WHERE symbol = :symbol AND timeframe = :timeframe
                ORDER BY timestamp ASC
                {limit_clause}
            """)
            result = await session.execute(
                query, {"symbol": symbol, "timeframe": timeframe}
            )
            rows = result.fetchall()

        if not rows:
            return None

        df = pd.DataFrame(
            rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        # Конвертируем timestamp (ms) в DatetimeIndex UTC
        df.index = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.index.name = "timestamp"
        df = df.drop(columns=["timestamp"])
        df = df.astype(float)
        return df

    except Exception as e:
        logger.error("Ошибка загрузки данных для %s %s: %s", symbol, timeframe, e)
        return None


def _log_bars_summary(
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
    bars: pd.DataFrame,
    config: BarsConfig,
) -> None:
    """Вывести статистику сгенерированных баров."""
    if len(bars) == 0:
        logger.warning("%s %s: баров не сформировано", symbol, timeframe)
        return

    compression = len(df) / len(bars)
    avg_turnover = bars["turnover"].mean()
    avg_duration = bars["duration_s"].mean()
    avg_trades = bars["trades_count"].mean()

    logger.info(
        "%s %s: %d строк -> %d баров (сжатие %.1fx) | "
        "avg_turnover=%.0f USD | avg_duration=%.0fs | avg_trades=%.1f | "
        "volume_unit=%s",
        symbol,
        timeframe,
        len(df),
        len(bars),
        compression,
        avg_turnover,
        avg_duration,
        avg_trades,
        config.volume_unit,
    )


def _show_plan(args) -> None:  # type: ignore[no-untyped-def]
    """Показать план без выполнения (dry-run)."""
    logger.info("build-bars dry-run:")
    logger.info("  Символы:      %s", args.symbols)
    logger.info("  Таймфрейм:    %s", args.timeframe)
    logger.info("  Dollar value: %.0f USD", args.dollar_value)
    logger.info("  Volume unit:  %s", args.volume_unit)
    if args.volume_unit == "contracts":
        logger.info("  Contract val: %.4f", args.contract_val)
    logger.info("  Min trades:   %d", args.min_trades)
    logger.info("  Лимит строк:  %s", args.limit or "все данные")
