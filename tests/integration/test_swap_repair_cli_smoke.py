from __future__ import annotations

import json
import subprocess
import sys

import pytest


@pytest.mark.integration
@pytest.mark.smoke
def test_swap_repair_detect_only_cli_smoke() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.cli.main",
            "swap-repair",
            "--start",
            "2026-04-01T00:00:00Z",
            "--end",
            "2026-04-01T00:03:00Z",
            "--mode",
            "detect-only",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)

    assert payload["mode"] == "detect-only"
    assert payload["strategy"] == "gap-repair"
    assert payload["symbol"] == "BTC-USDT-SWAP"
    assert payload["timeframe"] == "1m"
    assert payload["rows_written"] == 0
    assert payload["fetch_calls"] == 0
    assert payload["watermark_updated"] is False
