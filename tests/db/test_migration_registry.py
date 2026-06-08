from src.db.migration_registry import get_migrations


def test_bootstrap_state_migration_is_registered_after_runtime_ops_migrations() -> None:
    migrations = get_migrations()
    ids = [migration.id for migration in migrations]

    assert "350_ops_swap_ohlcv_bootstrap_state" in ids
    assert ids.index("350_ops_swap_ohlcv_bootstrap_state") > ids.index(
        "340_swap_ohlcv_retention_policy"
    )

    migration = migrations[ids.index("350_ops_swap_ohlcv_bootstrap_state")]
    assert migration.func.__name__ == "migrate_create_ops_swap_ohlcv_bootstrap_state"


def test_swap_ohlcv_protection_migrations_are_registered_after_350() -> None:
    migrations = get_migrations()
    ids = [migration.id for migration in migrations]

    expected = [
        "360_swap_ohlcv_constraints",
        "370_validate_swap_ohlcv_constraints",
        "380_swap_ohlcv_alignment_trigger",
    ]

    start = ids.index("360_swap_ohlcv_constraints")
    assert ids[start : start + len(expected)] == expected
    assert ids.index("360_swap_ohlcv_constraints") > ids.index(
        "350_ops_swap_ohlcv_bootstrap_state"
    )

    funcs = {migration.id: migration.func.__name__ for migration in migrations}
    assert funcs["360_swap_ohlcv_constraints"] == "migrate_add_swap_ohlcv_constraints"
    assert (
        funcs["370_validate_swap_ohlcv_constraints"]
        == "migrate_validate_swap_ohlcv_constraints"
    )
    assert (
        funcs["380_swap_ohlcv_alignment_trigger"]
        == "migrate_add_swap_ohlcv_alignment_trigger"
    )
