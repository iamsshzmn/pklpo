"""
CLI command label: bar labeling using triple-barrier method + uniqueness sample weights.

Usage:
    python -m src.cli.main label --symbols BTC-USDT-SWAP --pt 0.02 --sl 0.01 --max-h 48
    python -m src.cli.main label --symbols BTC-USDT-SWAP ETH-USDT-SWAP \\
        --pt 0.015 --sl 0.01 --max-h 24 --decay 0.8
    python -m src.cli.main label --symbols BTC-USDT-SWAP --dry-run
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import text

from src.core.run_context import RunContext
from src.ml.labeling.sample_weights import get_uniqueness_weights
from src.ml.labeling.triple_barrier import triple_barrier_labels
from src.ml.models import BarrierConfig

logger = logging.getLogger(__name__)


def register(subparsers) -> None:  # type: ignore[no-untyped-def]
    """Register the label command in the CLI."""
    p = subparsers.add_parser(
        "label",
        help="Bar labeling using triple-barrier method (AFML Ch.3) + uniqueness weights",
    )
    p.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="Symbols to process (e.g.: BTC-USDT-SWAP ETH-USDT-SWAP)",
    )
    p.add_argument(
        "--timeframe",
        default="1m",
        help="Source data timeframe (default: 1m)",
    )
    p.add_argument(
        "--pt",
        dest="profit_take",
        type=float,
        default=0.02,
        help="Profit take threshold as fraction of price (default: 0.02 = 2%%)",
    )
    p.add_argument(
        "--sl",
        dest="stop_loss",
        type=float,
        default=0.01,
        help="Stop loss threshold as fraction of price (default: 0.01 = 1%%)",
    )
    p.add_argument(
        "--max-h",
        dest="max_horizon",
        type=int,
        default=48,
        help="Maximum horizon in bars until vertical barrier (default: 48)",
    )
    p.add_argument(
        "--decay",
        type=float,
        default=1.0,
        help="Time-decay for sample weights, (0, 1] (default: 1.0 = no decay)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Row limit from DB (default: all data)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show parameters without running labeling",
    )
    p.set_defaults(_handler=handle)


async def handle(args) -> None:  # type: ignore[no-untyped-def]
    """Handler for the label command."""
    if args.dry_run:
        _show_plan(args)
        return

    ctx = RunContext.create(
        params={
            "profit_take": args.profit_take,
            "stop_loss": args.stop_loss,
            "max_horizon": args.max_horizon,
            "decay": args.decay,
            "timeframe": args.timeframe,
        }
    )
    logger.info("RunContext: run_id=%s", ctx.run_id)

    config = BarrierConfig(
        profit_take=args.profit_take,
        stop_loss=args.stop_loss,
        max_horizon=args.max_horizon,
    )

    total_labels = 0
    for symbol in args.symbols:
        df = await _load_ohlcv(symbol, args.timeframe, args.limit)
        if df is None or len(df) == 0:
            logger.warning("No data for %s %s", symbol, args.timeframe)
            continue

        labels_df = triple_barrier_labels(df, config)
        weights = get_uniqueness_weights(
            t1=labels_df["t1"],
            close=df["close"],
            decay_factor=args.decay,
        )
        total_labels += len(labels_df)
        _log_label_summary(symbol, args.timeframe, labels_df, weights, config)

    logger.info(
        "label completed: %d symbols, %d labels total (run_id=%s)",
        len(args.symbols),
        total_labels,
        ctx.run_id[:8],
    )


async def _load_ohlcv(
    symbol: str, timeframe: str, limit: int | None
) -> pd.DataFrame | None:
    """Load OHLCV data from the database."""
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
        df.index = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.index.name = "timestamp"
        df = df.drop(columns=["timestamp"])
        return df.astype(float)

    except Exception as e:
        logger.error("Error loading data for %s %s: %s", symbol, timeframe, e)
        return None


def _log_label_summary(
    symbol: str,
    timeframe: str,
    labels_df: pd.DataFrame,
    weights: pd.Series,
    config: BarrierConfig,
) -> None:
    """Log labeling statistics."""
    n = len(labels_df)
    if n == 0:
        logger.warning("%s %s: no labels formed", symbol, timeframe)
        return

    counts = labels_df["label"].value_counts()
    n_pt = int(counts.get(1, 0))
    n_sl = int(counts.get(-1, 0))
    n_vert = int(counts.get(0, 0))
    avg_weight = float(weights.mean()) if len(weights) > 0 else 0.0

    logger.info(
        "%s %s: %d labels | PT=%d (%.1f%%) SL=%d (%.1f%%) VERT=%d (%.1f%%) | "
        "avg_weight=%.4f | pt=%.3f sl=%.3f max_h=%d",
        symbol,
        timeframe,
        n,
        n_pt, 100.0 * n_pt / n,
        n_sl, 100.0 * n_sl / n,
        n_vert, 100.0 * n_vert / n,
        avg_weight,
        config.profit_take,
        config.stop_loss,
        config.max_horizon,
    )


def _show_plan(args) -> None:  # type: ignore[no-untyped-def]
    """Show plan without executing (dry-run)."""
    logger.info("label dry-run:")
    logger.info("  Symbols:      %s", args.symbols)
    logger.info("  Timeframe:    %s", args.timeframe)
    logger.info("  Profit take:  %.3f (%.1f%%)", args.profit_take, args.profit_take * 100)
    logger.info("  Stop loss:    %.3f (%.1f%%)", args.stop_loss, args.stop_loss * 100)
    logger.info("  Max horizon:  %d bars", args.max_horizon)
    logger.info("  Time decay:   %.2f", args.decay)
    logger.info("  Row limit:    %s", args.limit or "all data")
