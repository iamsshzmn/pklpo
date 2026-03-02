"""Helper для UPSERT операций с combination_features."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..logging_config import get_combinations_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_combinations_logger("upsert")


async def build_and_execute_upsert(
    session: AsyncSession,
    model_class: Any,
    records: list[dict[str, Any]],
    db_cols: set[str],
    pk: tuple[str, ...],
    required_fields: set[str],
) -> int:
    """
    Построить и выполнить UPSERT для combination_features.

    Упрощённая версия без сложной нормализации (JSONB поля уже готовы).
    """
    if not records:
        return 0

    # Фильтруем записи по колонкам БД
    filtered_records = []
    for record in records:
        filtered = {k: v for k, v in record.items() if k in db_cols}
        filtered_records.append(filtered)

    if not filtered_records:
        logger.warning("No valid records after filtering")
        return 0

    # Создаём INSERT statement
    stmt = pg_insert(model_class).values(filtered_records)

    # Строим update_dict (все поля кроме PK)
    update_dict = {}
    first_record = filtered_records[0]
    non_pk_fields = [k for k in first_record if k not in pk]

    for field in non_pk_fields:
        try:
            update_dict[field] = stmt.excluded[field]
        except (KeyError, AttributeError):
            logger.warning(f"Field '{field}' not available in stmt.excluded")
            continue

    if not update_dict:
        logger.warning("No fields available for UPSERT update")
        return 0

    # Добавляем on_conflict_do_update
    stmt = stmt.on_conflict_do_update(index_elements=list(pk), set_=update_dict)

    # Выполняем
    try:
        await session.execute(stmt)
        saved = len(filtered_records)
        logger.info(f"UPSERT executed: {saved} records")
        return saved
    except Exception as e:
        logger.error(f"UPSERT failed: {e}")
        raise
