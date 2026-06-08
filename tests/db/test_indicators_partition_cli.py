from __future__ import annotations

from argparse import Namespace

import pytest

from src.cli.commands import indicators_partitions


@pytest.mark.asyncio
async def test_cli_defaults_to_dry_run(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_preview(**kwargs: object) -> dict[str, object]:
        assert kwargs["months_back"] == 1
        assert kwargs["months_ahead"] == 3
        return {"created_count": 0, "missing_before_run": ["p1"]}

    async def fake_apply(**kwargs: object) -> dict[str, object]:
        raise AssertionError("apply path should not be used")

    monkeypatch.setattr(
        indicators_partitions,
        "preview_indicators_partition_maintenance",
        fake_preview,
    )
    monkeypatch.setattr(
        indicators_partitions,
        "run_indicators_partition_maintenance",
        fake_apply,
    )

    exit_code = await indicators_partitions.handle(
        Namespace(
            months_back=1,
            months_ahead=3,
            reference_dt=None,
            apply=False,
            skip_parent_pk_check=False,
            validate=False,
        )
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Mode: dry-run" in captured.out
    assert '"missing_before_run": [' in captured.out


@pytest.mark.asyncio
async def test_cli_apply_and_validate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_preview(**kwargs: object) -> dict[str, object]:
        raise AssertionError("preview path should not be used")

    async def fake_apply(**kwargs: object) -> dict[str, object]:
        assert kwargs["require_parent_pk"] is False
        return {"created_count": 2}

    async def fake_validate(**kwargs: object) -> dict[str, object]:
        return {"actual_months_ahead": 3}

    monkeypatch.setattr(
        indicators_partitions,
        "preview_indicators_partition_maintenance",
        fake_preview,
    )
    monkeypatch.setattr(
        indicators_partitions,
        "run_indicators_partition_maintenance",
        fake_apply,
    )
    monkeypatch.setattr(
        indicators_partitions,
        "run_indicators_partition_validation",
        fake_validate,
    )

    exit_code = await indicators_partitions.handle(
        Namespace(
            months_back=2,
            months_ahead=4,
            reference_dt="2026-03-07T00:00:00Z",
            apply=True,
            skip_parent_pk_check=True,
            validate=True,
        )
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Mode: apply" in captured.out
    assert "Validation:" in captured.out
