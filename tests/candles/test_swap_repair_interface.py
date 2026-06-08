from __future__ import annotations

from src.cli.main import create_parser


def test_swap_repair_command_is_registered() -> None:
    parser = create_parser()

    args = parser.parse_args(
        [
            "swap-repair",
            "--start",
            "2026-04-01T00:00:00Z",
            "--end",
            "2026-04-01T01:00:00Z",
        ]
    )

    assert args.command == "swap-repair"
    assert args.mode == "detect-only"
    assert args.repair_strategy == "gap-repair"
    assert args.padding_bars == 0
