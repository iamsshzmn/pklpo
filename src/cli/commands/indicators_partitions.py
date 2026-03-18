from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.db.indicators_partition.interfaces import (
    preview_indicators_partition_maintenance,
    run_indicators_partition_maintenance,
    run_indicators_partition_validation,
)

if TYPE_CHECKING:
    import argparse


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "indicators-partitions",
        help="Preview or apply indicators_p partition maintenance",
    )
    parser.add_argument("--months-back", type=int, default=1)
    parser.add_argument("--months-ahead", type=int, default=3)
    parser.add_argument(
        "--reference-dt",
        type=str,
        default=None,
        help="Reference datetime in ISO-8601; defaults to current UTC time",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply partition maintenance; default mode is dry-run preview",
    )
    parser.add_argument(
        "--skip-parent-pk-check",
        action="store_true",
        help="Skip parent PK/UNIQUE prerequisite check during apply",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run horizon validation after preview/apply",
    )
    parser.set_defaults(_handler=handle)


def _parse_reference_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


async def handle(args: argparse.Namespace) -> int:
    reference_dt = _parse_reference_dt(args.reference_dt)

    if args.apply:
        result = await run_indicators_partition_maintenance(
            months_back=args.months_back,
            months_ahead=args.months_ahead,
            reference_dt=reference_dt,
            require_parent_pk=not args.skip_parent_pk_check,
        )
        print("Mode: apply")
        print(json.dumps(result, indent=2))
    else:
        result = await preview_indicators_partition_maintenance(
            months_back=args.months_back,
            months_ahead=args.months_ahead,
            reference_dt=reference_dt,
        )
        print("Mode: dry-run")
        print(json.dumps(result, indent=2))

    if args.validate:
        validation = await run_indicators_partition_validation(
            months_ahead=args.months_ahead,
            reference_dt=reference_dt,
        )
        print("Validation:")
        print(json.dumps(validation, indent=2))

    return 0
