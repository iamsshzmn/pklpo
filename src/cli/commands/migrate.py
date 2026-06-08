import logging

from src.db.migration_runner import run_all
from src.logging import setup_logging

logger = logging.getLogger(__name__)


def register(subparsers):
    p = subparsers.add_parser(
        "migrate", help="Р’С‹РїРѕР»РЅРёС‚СЊ РјРёРіСЂР°С†РёРё Р±Р°Р·С‹ РґР°РЅРЅС‹С…"
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="РџРѕРєР°Р·Р°С‚СЊ РїР»Р°РЅ РјРёРіСЂР°С†РёР№ Р±РµР· РїСЂРёРјРµРЅРµРЅРёСЏ",
    )
    p.set_defaults(_handler=handle)


async def handle(args):
    setup_logging("app.log")
    logger.info("рџ“‹ Р—Р°РїСѓСЃРє РјРёРіСЂР°С†РёР№ Р±Р°Р·С‹ РґР°РЅРЅС‹С…...")
    await run_all(dry_run=args.dry_run)
    logger.info("вњ… Р’СЃРµ РјРёРіСЂР°С†РёРё РІС‹РїРѕР»РЅРµРЅС‹")
