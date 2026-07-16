from __future__ import annotations

import json
import socket
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.smoke]


def _skip_if_local_postgres_unavailable() -> None:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return
    except OSError as exc:
        pytest.skip(f"Local Postgres is unavailable for swap-repair smoke test: {exc}")


def test_swap_repair_detect_only_cli_smoke() -> None:
    _skip_if_local_postgres_unavailable()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.cli.main",
            "swap-repair",
            "--symbols",
            "BTC-USDT-SWAP",
            "--timeframes",
            "1m",
            "--start",
            "2026-04-01T00:00:00Z",
            "--end",
            "2026-04-01T00:05:00Z",
            "--mode",
            "detect-only",
            "--repair-strategy",
            "gap-repair",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert payload["mode"] == "detect-only"
    assert payload["strategy"] == "gap-repair"
    assert payload["symbol"] == "BTC-USDT-SWAP"
    assert payload["timeframe"] == "1m"
    assert payload["fetch_calls"] == 0
    assert payload["rows_written"] == 0
    assert payload["guardrail_violations"] == []
