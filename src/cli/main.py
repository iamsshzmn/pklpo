import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure project root on path
sys.path.append(str(Path(__file__).resolve().parents[2]))

logger = logging.getLogger(__name__)


def _install_logging(verbose: bool, quiet: bool) -> None:
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("🔍 Включен подробный режим логирования (DEBUG)")
    elif quiet:
        logging.getLogger().setLevel(logging.ERROR)
        logger.info("🔇 Включен тихий режим (только ошибки)")


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pklpo", description="PKLPO CLI")
    parser.add_argument(
        "--verbose", "-V", action="store_true", help="Подробный вывод (DEBUG)"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Тихий режим (только ошибки)"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Register subcommands
    from src.candles import load_instruments as cmd_load_instruments
    from src.cli.commands import (
        bars as cmd_bars,
        cleanup as cmd_cleanup,
        features as cmd_features,
        indicators_partitions as cmd_indicators_partitions,
        label as cmd_label,
        metrics as cmd_metrics,
        migrate as cmd_migrate,
        pipeline as cmd_pipeline,
        swap_repair as cmd_swap_repair,
        swap_sync as cmd_swap,
        train as cmd_train,
        update_list as cmd_update_list,
    )
    from src.market_selection.interfaces import commands as cmd_market_selection

    # from src.cli.commands import mtf as cmd_mtf
    # from src.cli.commands import mtf_migrate as cmd_mtf_migrate
    # from src.cli.commands import signals as cmd_signals
    # from src.cli.commands import risk_migrate as cmd_risk_migrate
    # from src.cli.commands import risk as cmd_risk

    cmd_migrate.register(subparsers)
    cmd_bars.register(subparsers)
    cmd_load_instruments.register(subparsers)
    cmd_swap.register(subparsers)
    cmd_swap_repair.register(subparsers)
    cmd_pipeline.register(subparsers)
    cmd_features.register(subparsers)
    cmd_update_list.register(subparsers)
    cmd_cleanup.register(subparsers)
    cmd_market_selection.register(subparsers)
    cmd_label.register(subparsers)
    cmd_train.register(subparsers)
    cmd_metrics.register(subparsers)
    cmd_indicators_partitions.register(subparsers)
    # cmd_mtf.register(subparsers)
    # cmd_mtf_migrate.register(subparsers)
    # cmd_signals.register(subparsers)
    # cmd_risk_migrate.register(subparsers)
    # cmd_risk.register(subparsers)

    return parser


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    _install_logging(getattr(args, "verbose", False), getattr(args, "quiet", False))

    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.print_help()
        return

    if asyncio.iscoroutinefunction(handler):
        asyncio.run(handler(args))
    else:
        result = handler(args)
        if asyncio.iscoroutine(result):
            asyncio.run(result)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )
    main()
