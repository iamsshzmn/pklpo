from __future__ import annotations

from pathlib import Path


def test_airflow_python_dags_do_not_embed_database_credentials() -> None:
    offenders: list[str] = []
    for path in Path("ops/airflow/dags").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        if any(
            secret in source
            for secret in (
                "strongpassword",
                "pklpo_user:",
                "postgresql+asyncpg://pklpo_user",
            )
        ):
            offenders.append(path.as_posix())

    assert offenders == []
