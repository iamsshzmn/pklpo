import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def _table_exists(session, table: str) -> bool:
    q = text(
        """
        SELECT to_regclass(:tbl) IS NOT NULL
    """
    )
    res = await session.execute(q, {"tbl": table})
    return bool(res.scalar())


async def _columns_exist(session, table: str, columns: list[str]) -> list[str]:
    q = text(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = :table
        """
    )
    res = await session.execute(q, {"table": table})
    existing = {r[0] for r in res.fetchall()}
    return [c for c in columns if c not in existing]


async def _validate_flexible_columns(
    session, table: str, column_groups: list[list[str]]
) -> list[str]:
    """
    Проверяет наличие хотя бы одной колонки из каждой группы альтернатив.
    Например: [['instid', 'instId'], ['timestamp', 'ts']]
    """
    q = text(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = :table
        """
    )
    res = await session.execute(q, {"table": table})
    existing = {r[0] for r in res.fetchall()}

    missing_groups = []
    for group in column_groups:
        if not any(col in existing for col in group):
            missing_groups.append(f"ни одна из: {group}")

    return missing_groups


async def validate_schema_expectations() -> tuple[bool, list[str]]:
    """
    Basic pre/post validation of expected tables/columns.
    Returns (ok, issues)
    """
    issues: list[str] = []
    async with get_db_session() as session:
        # Проверяем существование таблиц
        expected_tables = [
            "instruments",
            "ohlcv",
            "indicators",
            "signals",
            "score_results",
        ]
        for table in expected_tables:
            if not await _table_exists(session, table):
                issues.append(f"missing table: {table}")

        # Проверяем обязательные колонки (без альтернатив)
        simple_columns = {
            "instruments": ["symbol"],
            "ohlcv": ["symbol", "timeframe", "open", "high", "low", "close", "volume"],
            "indicators": ["symbol", "timeframe"],
            "signals": ["symbol", "timeframe"],
            "score_results": ["id", "score_raw"],
        }

        for table, cols in simple_columns.items():
            if await _table_exists(session, table):
                missing_cols = await _columns_exist(session, table, cols)
                if missing_cols:
                    issues.append(f"{table}: missing columns {missing_cols}")

        # Проверяем колонки с альтернативными именами
        flexible_columns = {
            "instruments": [["instid", "instId"]],
            "ohlcv": [["timestamp", "ts"]],
            "indicators": [["timestamp", "ts"]],
            "signals": [["timestamp", "ts"]],
        }

        for table, column_groups in flexible_columns.items():
            if await _table_exists(session, table):
                missing_groups = await _validate_flexible_columns(
                    session, table, column_groups
                )
                if missing_groups:
                    issues.append(f"{table}: missing columns {missing_groups}")

    ok = len(issues) == 0
    if ok:
        logger.info("✅ schema validation passed")
    else:
        for i in issues:
            logger.warning(f"⚠️ schema validation: {i}")
    return ok, issues
