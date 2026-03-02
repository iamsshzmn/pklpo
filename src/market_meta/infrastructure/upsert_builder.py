"""Единый билдер для upsert SET clause.

Гарантирует одинаковую политику защиты от NULL-затирания
в normalize и aggregate операциях.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.sql import func

if TYPE_CHECKING:
    from sqlalchemy import Column
    from sqlalchemy.dialects.postgresql import Insert


def build_upsert_set_clause(
    stmt: Insert,
    table_columns: list[Column],
    coalesce_fields: frozenset[str],
    skip_fields: frozenset[str] | None = None,
) -> dict[str, any]:
    """Строит SET clause для ON CONFLICT DO UPDATE.

    Политика DO_NOT_OVERWRITE_NON_NULL_WITH_NULL:
    - data_columns: COALESCE(excluded.col, target.col) — защита от NULL
    - meta_columns: excluded.col — всегда перезаписываем
    - updated_at: NOW()

    Args:
        stmt: PostgreSQL INSERT statement с excluded.
        table_columns: Список колонок таблицы.
        coalesce_fields: Поля, защищённые от NULL-затирания.
        skip_fields: Поля, которые не включать в SET (PK, created_at, бизнес-ключи).

    Returns:
        Словарь {column_name: expression} для set_.
    """
    if skip_fields is None:
        skip_fields = frozenset()

    update_dict: dict[str, any] = {}

    for col in table_columns:
        if col.name in skip_fields:
            continue

        if col.name == "updated_at":
            update_dict[col.name] = func.now()
        elif col.name in coalesce_fields:
            # COALESCE: не затираем существующее значение NULL'ом
            update_dict[col.name] = func.coalesce(
                stmt.excluded[col.name], col
            )
        else:
            # Остальные поля (включая метаданные) перезаписываем
            update_dict[col.name] = stmt.excluded[col.name]

    return update_dict


# Стандартные наборы полей для market_data_ext
MARKET_DATA_EXT_COALESCE_FIELDS = frozenset({
    "open_interest",
    "oi_change_24h",
    "oi_change_pct_24h",
    "funding_rate",
    "next_funding_time",
    "funding_interval_hours",
    "bid_imbalance",
    "ask_imbalance",
    "spread_bps",
})

MARKET_DATA_EXT_SKIP_FIELDS = frozenset({
    "id",
    "created_at",
    "symbol",
    "timeframe",
    "bar_timestamp",
})
