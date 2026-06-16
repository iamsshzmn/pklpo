import json
import logging

from src.candles.interfaces.swap_sync import sync_swap_candles
from src.logging import generate_run_id, set_log_context
from src.pklpo_platform.distributed_lock import LockConflict, RedisLockError, job_lock

logger = logging.getLogger(__name__)


def register(subparsers):
    p = subparsers.add_parser("swap-sync", help="Синхронизация swap свечей")
    p.add_argument("--symbols", nargs="+", help="Символы для синхронизации")
    p.add_argument("--timeframes", nargs="+", help="Таймфреймы для синхронизации")
    p.add_argument("--config", help="Путь к JSON конфигу для синхронизации")
    p.set_defaults(_handler=handle)


async def handle(args):
    config = None
    if getattr(args, "config", None):
        try:
            with open(args.config, encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            logger.warning(
                "Не удалось загрузить конфиг %s: %s. Используем значения по умолчанию",
                args.config,
                e,
            )

    symbols = getattr(args, "symbols", None)
    timeframes = getattr(args, "timeframes", None)
    config = dict(config or {})
    run_id = str(config.get("run_id") or generate_run_id())
    config["run_id"] = run_id

    # Scope the lock to the symbol list fingerprint so multi-symbol runs don't
    # block each other when called with disjoint symbol sets.
    lock_scope = ",".join(sorted(symbols)) if symbols else "all"

    try:
        with set_log_context(run_id=run_id, component="swap_sync"):
            async with job_lock("swap_sync", symbol=lock_scope, component="swap_sync"):
                logger.info("Запуск этапа: синхронизация swap свечей")
                stats = await sync_swap_candles(
                    symbols=symbols, timeframes=timeframes, config=config
                )
                logger.info("Этап swap синхронизации завершён")
                logger.info(
                    "Символов: %d, свечей: %d, ошибок: %d",
                    stats["total_symbols"],
                    stats["total_candles_synced"],
                    stats["errors_count"],
                )
    except LockConflict as exc:
        raise SystemExit(f"[lock_conflict] swap-sync skipped: {exc}") from exc
    except RedisLockError as exc:
        raise SystemExit(
            f"[lock_error] Redis unavailable, aborting sync (fail-closed): {exc}"
        ) from exc
