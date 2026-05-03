from __future__ import annotations


def test_upsert_package_exports_match_facade() -> None:
    from src.features.infrastructure import upsert as pkg, upsert_builder as legacy

    assert legacy._get_dynamic_batch_size is pkg._get_dynamic_batch_size
    assert legacy.build_and_execute_upsert is pkg.build_and_execute_upsert
    assert legacy.build_upsert_statement is pkg.build_upsert_statement
    assert legacy.execute_upsert is pkg.execute_upsert
    assert legacy.DEFAULT_MIN_BATCH_SIZE == pkg.DEFAULT_MIN_BATCH_SIZE
    assert legacy.DEFAULT_MAX_BATCH_SIZE == pkg.DEFAULT_MAX_BATCH_SIZE
    assert legacy.TARGET_SQL_PARAMS == pkg.TARGET_SQL_PARAMS
