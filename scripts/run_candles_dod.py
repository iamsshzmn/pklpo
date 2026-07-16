from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_step(name: str, args: list[str], cwd: Path) -> None:
    print(f"[candles-dod] {name}")
    print(f"[candles-dod] command: {' '.join(args)}")
    result = subprocess.run(args, cwd=cwd)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run candles DoD checks")
    parser.add_argument(
        "--cov-fail-under",
        type=int,
        default=50,
        help="Coverage threshold for src/candles",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    python = sys.executable

    run_step(
        "parity gate tests",
        [python, "-m", "pytest", "-q", "-o", "addopts=", "tests/candles/test_parity_check.py"],
        repo_root,
    )
    run_step(
        "smoke import tests",
        [python, "-m", "pytest", "-q", "-o", "addopts=", "-m", "smoke", "tests/candles"],
        repo_root,
    )
    run_step(
        "candles coverage gate",
        [
            python,
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            "-m",
            "not integration",
            "--cov=src/candles",
            "--cov-report=term-missing",
            f"--cov-fail-under={args.cov_fail_under}",
            "tests/candles",
        ],
        repo_root,
    )
    print("[candles-dod] all gates passed")


if __name__ == "__main__":
    main()

