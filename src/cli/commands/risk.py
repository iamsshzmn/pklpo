"""
CLI команды для risk: статус/enable/disable guard, set-limit, show-limits, cleanup
Поддерживает загрузку переменных из .env и сборку DATABASE_URL из POSTGRES_*.
"""

import argparse
import asyncio
import os

from dotenv import load_dotenv

from src.risk.database.client import RiskDatabaseClient


def _load_env_files(env_files: list[str] | None) -> None:
    if env_files:
        for path in env_files:
            load_dotenv(dotenv_path=path, override=False)
    else:
        load_dotenv(override=False)


def _build_database_url_from_env() -> str | None:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    user = os.environ.get("POSTGRES_USER") or os.environ.get("DB_USER")
    password = os.environ.get("POSTGRES_PASSWORD") or os.environ.get("DB_PASSWORD")
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("POSTGRES_DB") or os.environ.get("DB_NAME")
    if user and password and dbname:
        return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    return None


def register(subparsers):
    parser = subparsers.add_parser("risk", help="Команды управления risk модулем")
    parser.add_argument(
        "--env-file", action="append", help="Путь к .env (можно несколько флагов)"
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="URL базы данных (перекрывает env)",
    )

    risk_sub = parser.add_subparsers(dest="risk_cmd", required=True)

    # status
    p_status = risk_sub.add_parser("status", help="Показать статус guards и лимитов")
    p_status.set_defaults(risk_handler=_handle_status)

    # enable-guard / disable-guard
    for action in ("enable-guard", "disable-guard"):
        p = risk_sub.add_parser(action, help=f"{action} по имени и типу")
        p.add_argument("--name", required=True)
        p.add_argument(
            "--type",
            required=True,
            choices=[
                "circuit_breaker",
                "killswitch",
                "dq_guard",
                "sla_guard",
                "health_guard",
            ],
        )
        p.set_defaults(risk_handler=_handle_toggle_guard, _toggle_action=action)

    # bootstrap-guards from env
    p_boot = risk_sub.add_parser(
        "bootstrap-guards",
        help="Включить/создать guard из ENV (RISK_GUARDS=type:name;type:name)",
    )
    p_boot.set_defaults(risk_handler=_handle_bootstrap_guards)

    # set-limit
    p_set_limit = risk_sub.add_parser("set-limit", help="Создать/обновить лимит")
    p_set_limit.add_argument("--name", required=True)
    p_set_limit.add_argument(
        "--type",
        required=True,
        choices=["daily_loss", "weekly_loss", "max_concurrent", "max_corr", "cooldown"],
    )
    p_set_limit.add_argument("--value", required=True)
    p_set_limit.add_argument("--time-window")
    p_set_limit.add_argument("--enabled", action="store_true")
    p_set_limit.set_defaults(risk_handler=_handle_set_limit)

    # show-limits
    p_show_limits = risk_sub.add_parser("show-limits", help="Показать лимиты")
    p_show_limits.set_defaults(risk_handler=_handle_show_limits)

    # cleanup
    p_cleanup = risk_sub.add_parser("cleanup", help="Очистить старые данные risk")
    p_cleanup.add_argument("--alerts", type=int, default=90)
    p_cleanup.add_argument("--metrics", type=int, default=90)
    p_cleanup.add_argument("--violations", type=int, default=180)
    p_cleanup.add_argument("--health", type=int, default=30)
    p_cleanup.add_argument("--sizing", type=int, default=30)
    p_cleanup.add_argument("--guard-state", type=int, default=90)
    p_cleanup.add_argument("--batch", type=int, default=10000)
    p_cleanup.set_defaults(risk_handler=_handle_cleanup)

    parser.set_defaults(_handler=_handle_entry)


async def _handle_entry(args):
    _load_env_files(args.env_file)
    db_url = args.database_url or _build_database_url_from_env()
    if not db_url:
        print(
            "DATABASE_URL не найден и не удалось собрать из POSTGRES_*/DB_* переменных",
            flush=True,
        )
        raise SystemExit(1)

    # делегируем обработчику подкоманды
    await args.risk_handler(db_url, args)


async def _handle_status(db_url: str, args):
    client = RiskDatabaseClient(db_url)
    await client.initialize()
    try:
        async with client._pool.acquire() as conn:
            guards = await conn.fetch(
                "SELECT * FROM risk.active_guards ORDER BY updated_at DESC LIMIT 50"
            )
            limits = await conn.fetch(
                "SELECT name, type, value, time_window, enabled, updated_at FROM risk.limits ORDER BY updated_at DESC LIMIT 50"
            )
        print("Active guards:")
        for g in guards:
            print(f"- {g['name']} [{g['type']}] status={g['status']}")
        print("Limits:")
        for limit in limits:
            print(
                f"- {limit['name']} [{limit['type']}] value={limit['value']} window={limit['time_window']} enabled={limit['enabled']}"
            )
    finally:
        await client.close()


async def _handle_toggle_guard(db_url: str, args):
    name = args.name
    type_ = args.type
    status = "active" if args._toggle_action == "enable-guard" else "disabled"
    client = RiskDatabaseClient(db_url)
    await client.initialize()
    try:
        guard_id = await client.upsert_guard(
            name=name, type_=type_, status=status, config={}
        )
        await client.add_guard_state(
            guard_id=guard_id, state="enabled" if status == "active" else "disabled"
        )
        print(f"Guard '{name}' ({type_}) set to {status}")
    finally:
        await client.close()


async def _handle_bootstrap_guards(db_url: str, args):
    client = RiskDatabaseClient(db_url)
    await client.initialize()
    try:
        guards = os.environ.get("RISK_GUARDS", "")
        for item in [x for x in guards.split(";") if x.strip()]:
            try:
                type_, name = item.split(":", 1)
            except ValueError:
                continue
            gid = await client.upsert_guard(
                name=name, type_=type_, status="active", config={}
            )
            await client.add_guard_state(
                guard_id=gid,
                state="enabled",
                trigger_count=0,
                context={"source": "bootstrap"},
            )
            print(f"Bootstrapped guard: {name} ({type_})")
    finally:
        await client.close()


async def _handle_set_limit(db_url: str, args):
    from decimal import Decimal

    client = RiskDatabaseClient(db_url)
    await client.initialize()
    try:
        lid = await client.upsert_limit(
            name=args.name,
            type_=args.type,
            value=Decimal(str(args.value)),
            time_window=args.time_window,
            enabled=bool(args.enabled),
            metadata={},
        )
        print(f"Limit '{args.name}' upserted: {lid}")
    finally:
        await client.close()


async def _handle_show_limits(db_url: str, args):
    client = RiskDatabaseClient(db_url)
    await client.initialize()
    try:
        async with client._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT name, type, value, time_window, enabled FROM risk.limits ORDER BY name"
            )
        for r in rows:
            print(
                f"- {r['name']} [{r['type']}] value={r['value']} window={r['time_window']} enabled={r['enabled']}"
            )
    finally:
        await client.close()


async def _handle_cleanup(db_url: str, args):
    client = RiskDatabaseClient(db_url)
    await client.initialize()
    try:
        async with client._pool.acquire() as conn:
            deleted = await conn.fetchval(
                "SELECT risk.cleanup_old_data($1,$2,$3,$4,$5,$6,$7)",
                args.alerts,
                args.metrics,
                args.violations,
                args.health,
                args.sizing,
                args.__getattribute__("guard_state"),
                args.batch,
            )
        print(f"Cleanup deleted rows: {deleted}")
    finally:
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Risk CLI")
    register(parser.add_subparsers())
    ns = parser.parse_args()
    asyncio.run(_handle_entry(ns))
