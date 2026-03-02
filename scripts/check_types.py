#!/usr/bin/env python3
"""
Скрипт для проверки типов с помощью mypy.

Использование:
    python scripts/check_types.py [путь_к_файлу_или_директории]

Если путь не указан, проверяет src/features.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def check_mypy_installed() -> bool:
    """Проверяет, установлен ли mypy."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def run_mypy(target: str = "src/features") -> int:
    """Запускает mypy для указанной цели."""
    config_file = PROJECT_ROOT / "pyproject.toml"
    cmd = [
        sys.executable,
        "-m",
        "mypy",
        target,
        "--config-file",
        str(config_file),
    ]

    print(f"Запуск mypy для {target}...")
    print(f"Команда: {' '.join(cmd)}")
    print("-" * 80)

    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    return result.returncode


def main() -> int:
    """Главная функция."""
    if not check_mypy_installed():
        print("ОШИБКА: mypy не установлен.")
        print("\nУстановите mypy:")
        print("  pip install mypy")
        print("\nИли установите все dev-зависимости:")
        print("  pip install -e '.[dev]'")
        return 1

    target = sys.argv[1] if len(sys.argv) > 1 else "src/features"
    return run_mypy(target)


if __name__ == "__main__":
    sys.exit(main())
