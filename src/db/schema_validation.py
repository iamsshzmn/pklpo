import logging

from sqlalchemy import text

from src.models import INDICATORS_TABLE_NAME
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


async def _resolve_table(session, candidates: list[str]) -> str | None:
    for table in candidates:
        if await _table_exists(session, table):
            return table
    return None


async def _is_partitioned_table(session, table: str) -> bool:
    q = text(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_partitioned_table pt
            JOIN pg_class c ON c.oid = pt.partrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = :table
        )
        """
    )
    res = await session.execute(q, {"table": table})
    return bool(res.scalar())


async def validate_schema_expectations() -> tuple[bool, list[str]]:
    """
    Basic pre/post validation of expected tables/columns.
    Returns (ok, issues)
    """
    issues: list[str] = []
    async with get_db_session() as session:
        table_groups = {
            "instruments": ["instruments"],
            "market_candles": ["swap_ohlcv_p", "ohlcv_p", "ohlcv"],
            "features": [INDICATORS_TABLE_NAME],
            "market_meta": ["market_data_ext"],
            "market_selection_scores": ["market_scores_tf"],
            "market_selection_universe": ["market_universe"],
            "market_selection_versions": ["market_universe_versions"],
            "market_selection_regime": ["market_regime_history"],
            "signals": ["signals"],
            "score_results": ["score_results"],
        }
        resolved_tables: dict[str, str] = {}

        for label, candidates in table_groups.items():
            table = await _resolve_table(session, candidates)
            if table is None:
                issues.append(f"missing table group {label}: expected one of {candidates}")
                continue
            resolved_tables[label] = table

        market_candles_table = resolved_tables.get("market_candles")
        if market_candles_table == "swap_ohlcv_p" and not await _is_partitioned_table(
            session, "swap_ohlcv_p"
        ):
            issues.append("swap_ohlcv_p exists but is not a partitioned parent table")

        simple_columns = {
            resolved_tables.get("instruments", "instruments"): ["symbol"],
            resolved_tables.get("market_candles", "ohlcv"): [
                "symbol",
                "timeframe",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
            resolved_tables.get("features", INDICATORS_TABLE_NAME): [
                "symbol",
                "timeframe",
            ],
            resolved_tables.get("market_meta", "market_data_ext"): [
                "symbol",
                "timestamp",
            ],
            resolved_tables.get("market_selection_scores", "market_scores_tf"): [
                "symbol",
                "timeframe",
                "ts_eval",
                "config_hash",
            ],
            resolved_tables.get("market_selection_universe", "market_universe"): [
                "ts_version",
                "symbol",
                "final_score",
                "rank",
            ],
            resolved_tables.get(
                "market_selection_versions", "market_universe_versions"
            ): ["ts_version", "ts_eval", "status", "config_hash"],
            resolved_tables.get("market_selection_regime", "market_regime_history"): [
                "ts_eval",
                "global_regime",
                "global_strength",
                "config_hash",
            ],
            resolved_tables.get("signals", "signals"): ["symbol", "timeframe"],
            resolved_tables.get("score_results", "score_results"): ["id", "score_raw"],
        }

        for table, cols in simple_columns.items():
            if await _table_exists(session, table):
                missing_cols = await _columns_exist(session, table, cols)
                if missing_cols:
                    issues.append(f"{table}: missing columns {missing_cols}")

        flexible_columns = {
            resolved_tables.get("instruments", "instruments"): [
                ["inst_id", "instid", "instId"]
            ],
            resolved_tables.get("market_candles", "ohlcv"): [["timestamp", "ts"]],
            resolved_tables.get("features", INDICATORS_TABLE_NAME): [
                ["timestamp", "ts"]
            ],
            resolved_tables.get("signals", "signals"): [["timestamp", "ts"]],
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
        logger.info("schema validation passed")
    else:
        for issue in issues:
            logger.warning("schema validation: %s", issue)
    return ok, issues
