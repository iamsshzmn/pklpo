"""Validate swap_ohlcv_p constraints partition-by-partition.

This migration is intentionally cancellable and non-destructive. It records dirty
partitions in ops.swap_ohlcv_constraint_validation_audit and only runs
VALIDATE CONSTRAINT when the matching preflight returns zero rows.

Rollback guidance:
    A failed VALIDATE leaves the constraint NOT VALID. To remove the surface,
    drop the constraints from swap_ohlcv_p using the snippets in
    migrate_add_swap_ohlcv_constraints.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from src.utils.session_utils import get_db_session

CREATE_OPS_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS ops
"""

CREATE_AUDIT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ops.swap_ohlcv_constraint_validation_audit (
    partition_name text NOT NULL,
    constraint_name text NOT NULL,
    status text NOT NULL,
    violations_sample jsonb,
    checked_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (partition_name, constraint_name)
)
"""

LIST_PARTITIONS_SQL = """
SELECT child.oid::regclass::text AS partition_name
FROM pg_inherits i
JOIN pg_class parent ON parent.oid = i.inhparent
JOIN pg_class child ON child.oid = i.inhrelid
JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
WHERE parent.relname = 'swap_ohlcv_p'
  AND parent_ns.nspname = ANY (current_schemas(false))
ORDER BY child.oid::regclass::text
"""

UPSERT_AUDIT_SQL = """
INSERT INTO ops.swap_ohlcv_constraint_validation_audit (
    partition_name,
    constraint_name,
    status,
    violations_sample,
    checked_at
)
VALUES (
    :partition_name,
    :constraint_name,
    :status,
    CAST(:violations_sample AS jsonb),
    now()
)
ON CONFLICT (partition_name, constraint_name) DO UPDATE
SET status = EXCLUDED.status,
    violations_sample = EXCLUDED.violations_sample,
    checked_at = now()
"""


@dataclass(frozen=True)
class ConstraintPreflight:
    constraint_name: str
    query_template: str


CONSTRAINT_PREFLIGHTS: tuple[ConstraintPreflight, ...] = (
    ConstraintPreflight(
        "chk_swap_ohlcv_p_timestamp_nonneg",
        """
        SELECT symbol, timeframe, timestamp
        FROM {partition}
        WHERE timestamp < 0
        LIMIT 100
        """,
    ),
    ConstraintPreflight(
        "chk_swap_ohlcv_p_prices_positive",
        """
        SELECT symbol, timeframe, timestamp, open, high, low, close
        FROM {partition}
        WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
           OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
        LIMIT 100
        """,
    ),
    ConstraintPreflight(
        "chk_swap_ohlcv_p_volume_nonneg",
        """
        SELECT symbol, timeframe, timestamp, volume
        FROM {partition}
        WHERE volume IS NULL OR volume < 0
        LIMIT 100
        """,
    ),
    ConstraintPreflight(
        "chk_swap_ohlcv_p_geometry",
        """
        SELECT symbol, timeframe, timestamp, open, high, low, close, volume
        FROM {partition}
        WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
           OR high < low
           OR high < GREATEST(open, close)
           OR low > LEAST(open, close)
        LIMIT 100
        """,
    ),
    ConstraintPreflight(
        "chk_swap_ohlcv_p_timeframe_supported",
        """
        SELECT DISTINCT timeframe
        FROM {partition}
        WHERE timeframe NOT IN ('1m','5m','15m','30m','1H','4H','12H','1D','1W','1M')
        LIMIT 100
        """,
    ),
)


def _quote_relation_name(relation_name: str) -> str:
    return ".".join(f'"{part.replace(chr(34), chr(34) * 2)}"' for part in relation_name.split("."))


def _rows_to_dicts(rows: Any) -> list[dict[str, Any]]:
    sample: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            sample.append(dict(row))
            continue
        mapping = getattr(row, "_mapping", None)
        if mapping is not None:
            sample.append(dict(mapping))
            continue
        if isinstance(row, tuple):
            sample.append({f"column_{index}": value for index, value in enumerate(row)})
            continue
        sample.append({"value": row})
    return sample[:100]


async def _audit(
    session: Any,
    *,
    partition_name: str,
    constraint_name: str,
    status: str,
    violations_sample: list[dict[str, Any]] | None,
) -> None:
    await session.execute(
        text(UPSERT_AUDIT_SQL),
        {
            "partition_name": partition_name,
            "constraint_name": constraint_name,
            "status": status,
            "violations_sample": json.dumps(violations_sample or [], default=str),
        },
    )


async def migrate_validate_swap_ohlcv_constraints() -> None:
    """Validate clean swap_ohlcv_p partitions and audit dirty partitions."""
    async with get_db_session() as session:
        try:
            await session.execute(text(CREATE_OPS_SCHEMA_SQL))
            await session.execute(text(CREATE_AUDIT_TABLE_SQL))
            partitions_result = await session.execute(text(LIST_PARTITIONS_SQL))
            partitions = [row[0] for row in partitions_result.fetchall()]
            dirty_constraints: set[str] = set()

            for partition_name in partitions:
                partition_sql = _quote_relation_name(partition_name)
                violations_by_constraint: dict[str, list[dict[str, Any]]] = {}

                for preflight in CONSTRAINT_PREFLIGHTS:
                    result = await session.execute(
                        text(preflight.query_template.format(partition=partition_sql))
                    )
                    violations_by_constraint[preflight.constraint_name] = _rows_to_dicts(
                        result.mappings().all()
                    )

                for preflight in CONSTRAINT_PREFLIGHTS:
                    violations = violations_by_constraint[preflight.constraint_name]
                    if violations:
                        dirty_constraints.add(preflight.constraint_name)
                        await _audit(
                            session,
                            partition_name=partition_name,
                            constraint_name=preflight.constraint_name,
                            status="dirty",
                            violations_sample=violations,
                        )
                        continue

                    await session.execute(
                        text(
                            f"ALTER TABLE {partition_sql} "
                            f"VALIDATE CONSTRAINT {preflight.constraint_name}"
                        )
                    )
                    await _audit(
                        session,
                        partition_name=partition_name,
                        constraint_name=preflight.constraint_name,
                        status="validated",
                        violations_sample=[],
                    )

            if partitions:
                for preflight in CONSTRAINT_PREFLIGHTS:
                    if preflight.constraint_name in dirty_constraints:
                        continue
                    await session.execute(
                        text(
                            "ALTER TABLE swap_ohlcv_p "
                            f"VALIDATE CONSTRAINT {preflight.constraint_name}"
                        )
                    )

            await session.commit()
        except Exception:
            await session.rollback()
            raise
