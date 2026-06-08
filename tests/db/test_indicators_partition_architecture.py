from __future__ import annotations

from pathlib import Path


def test_dag_depends_on_db_interface_not_platform_ops() -> None:
    dag_source = Path(
        "D:/projects/pklpo/ops/airflow/dags/indicators_partition_maintenance.py"
    ).read_text(encoding="utf-8")

    assert "src.db.indicators_partition.interfaces.indicators_partition_maintenance" in dag_source
    assert "src.platform_ops" not in dag_source


def test_application_module_has_no_airflow_or_sqlalchemy_imports() -> None:
    application_source = Path(
        "D:/projects/pklpo/src/db/indicators_partition/application/indicators_partition_maintenance.py"
    ).read_text(encoding="utf-8")

    assert "sqlalchemy" not in application_source
    assert "airflow" not in application_source


def test_infrastructure_module_has_no_interface_imports() -> None:
    infrastructure_source = Path(
        "D:/projects/pklpo/src/db/indicators_partition/infrastructure/postgres_indicators_partition_maintenance.py"
    ).read_text(encoding="utf-8")

    assert ".interfaces" not in infrastructure_source
    assert "src.db.indicators_partition.interfaces" not in infrastructure_source


def test_bootstrap_migration_uses_interfaces_not_infrastructure() -> None:
    source = Path(
        "D:/projects/pklpo/src/db/migrations/migrate_create_indicators_partitioned.py"
    ).read_text(encoding="utf-8")

    assert "indicators_partition.infrastructure" not in source
    assert "PostgresIndicatorsPartitionMaintenanceAdapter" not in source
